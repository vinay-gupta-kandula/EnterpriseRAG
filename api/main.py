from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import engine, Base, get_db
import models
import schemas
import auth
import uuid
import jwt
import os
import json

from celery import Celery
import redis
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

# --- CONFIGURATION & CONNECTIONS ---

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("api", broker=REDIS_URL, backend=REDIS_URL)

# Create a direct connection to Redis for our Caching layer
redis_cache = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Connect to the Vector Database
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
qdrant = QdrantClient(url=QDRANT_URL)

print("🧠 API: Loading AI Embedding Model (CPU Mode)...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Create the PostgreSQL database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="EnterpriseRAG API")
from prometheus_fastapi_instrumentator import Instrumentator

# This automatically tracks request latency, counts, and errors!
Instrumentator().instrument(app).expose(app)

# --- SECURITY BOUNCER ---
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    return user

@app.get("/health")
def health_check():
    return {"status": "ok"}

# --- AUTHENTICATION ENDPOINTS ---

@app.post("/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = auth.get_password_hash(user.password)
    new_tenant_id = f"tenant_{uuid.uuid4().hex[:8]}"
    new_user = models.User(email=user.email, hashed_password=hashed_password, tenant_id=new_tenant_id)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/auth/login", response_model=schemas.Token)
def login_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    access_token = auth.create_access_token(data={"sub": db_user.email, "tenant_id": db_user.tenant_id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

# --- DOCUMENT MANAGEMENT ---

@app.post("/api/v1/documents", response_model=schemas.DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
def upload_document(file: UploadFile = File(...), current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_doc = models.Document(filename=file.filename, tenant_id=current_user.tenant_id, status="processing")
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    file_path = f"shared_data/{new_doc.id}_{file.filename}"
    os.makedirs("shared_data", exist_ok=True)
    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())
        
    celery_app.send_task("tasks.process_document_task", args=[new_doc.id, current_user.tenant_id, file_path])
    return {"document_id": new_doc.id, "status": "processing"}

@app.get("/api/v1/documents/{document_id}/status", response_model=schemas.DocumentStatus)
def get_document_status(document_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(models.Document.id == document_id, models.Document.tenant_id == current_user.tenant_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document_id": doc.id, "status": doc.status}

# --- GENERATIVE AI QUERY ENGINE ---

def call_llm(query: str, context: str) -> str:
    """An abstracted LLM call. You can swap this with OpenAI or Langchain later!"""
    return f"Based on your private documents, here is the context I found:\n\n\"{context[:300]}...\"\n\nSynthesized Answer for '{query}'"

@app.post("/api/v1/query", response_model=schemas.QueryResponse)
def query_rag(
    request: schemas.QueryRequest, 
    response: Response, # Allows us to inject custom Cache Headers
    current_user: models.User = Depends(get_current_user)
):
    """Searches the vector database and generates an answer."""
    
    # 1. Check Redis Cache First
    cache_key = f"rag:{current_user.tenant_id}:{request.query}"
    cached_data = redis_cache.get(cache_key)
    
    if cached_data:
        # CACHE HIT! Return instantly and skip all the heavy math.
        response.headers["X-Cache-Hit"] = "true"
        return json.loads(cached_data)

    # 2. Embed the Question into Math
    query_vector = embedding_model.encode(request.query).tolist()

    # 3. Search Qdrant using the new query_points API!
    search_response = qdrant.query_points(
        collection_name="enterprise_docs",
        query=query_vector,
        query_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="tenant_id",
                    match=qmodels.MatchValue(value=current_user.tenant_id)
                )
            ]
        ),
        limit=3 # Get top 3 most relevant paragraphs
    )

    # 4. Extract the Context & Sources from the '.points' array
    context_texts = []
    sources = []
    for hit in search_response.points:
        text = hit.payload.get("text", "")
        doc_id = hit.payload.get("document_id", "")
        context_texts.append(text)
        sources.append({"document_id": doc_id, "content": text})

    # 5. Check if we found anything
    if not context_texts:
        final_answer = "I don't have any information in your documents to answer that."
    else:
        # Format the context and ask the LLM to answer
        combined_context = "\n---\n".join(context_texts)
        final_answer = call_llm(request.query, combined_context)

    # Prepare final payload
    result = {
        "answer": final_answer,
        "sources": sources
    }

    # 6. Save to Redis Cache (TTL = 3600 seconds / 1 hour)
    redis_cache.setex(cache_key, 3600, json.dumps(result))

    response.headers["X-Cache-Hit"] = "false"
    return result