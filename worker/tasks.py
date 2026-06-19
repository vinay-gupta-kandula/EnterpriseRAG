import os
import uuid
from celery import Celery
from sqlalchemy import create_engine, text
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

# THIS IS THE FIXED LINE (underscore instead of dot):
from langchain_text_splitters import RecursiveCharacterTextSplitter 

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

# 1. Setup Connections (Redis, Database, and Qdrant)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("worker", broker=REDIS_URL, backend=REDIS_URL)

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mysecretpassword")
POSTGRES_DB = os.getenv("POSTGRES_DB", "rag_db")
DB_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@db:5432/{POSTGRES_DB}"
engine = create_engine(DB_URL)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
qdrant = QdrantClient(url=QDRANT_URL)

# 2. Load the AI Embedding Model (Converts text to math)
print("🍳 CHEF: Downloading/Loading AI Model (This takes a minute on the first run)...")
model = SentenceTransformer('all-MiniLM-L6-v2') 

# 3. Create the Qdrant Collection if it doesn't exist
COLLECTION_NAME = "enterprise_docs"
try:
    qdrant.get_collection(COLLECTION_NAME)
except:
    print("🍳 CHEF: Creating new Qdrant Vector database collection...")
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )

# --- THE MAIN TASK ---

@celery_app.task
def process_document_task(document_id: str, tenant_id: str, file_path: str):
    print(f"🍳 CHEF: Starting to process document {document_id}")
    
    try:
       
        # STEP A: Read the File
        if file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        elif file_path.endswith(".docx"):
            loader = Docx2txtLoader(file_path)
        else:
            loader = TextLoader(file_path)
            
        documents = loader.load()
        print(f"🍳 CHEF DEBUG: Loaded {len(documents)} raw document pages/objects.")
        
        # STEP B: Chop it into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = text_splitter.split_documents(documents)
        print(f"🍳 CHEF DEBUG: Split text into {len(chunks)} total chunks.")
        
        # STEP C: Convert to Embeddings and package them for Qdrant
        points = []
        for chunk in chunks:
            text_content = chunk.page_content
            # Convert the paragraph into 384 numbers
            vector = model.encode(text_content).tolist() 
            
            # Package it up with our multi-tenant security tags!
            points.append(PointStruct(
                id=str(uuid.uuid4()), 
                vector=vector,
                payload={
                    "document_id": document_id,
                    "tenant_id": tenant_id, # STRICT DATA ISOLATION
                    "text": text_content
                }
            ))
        
        # STEP D: Upload all chunks to the Vector Database
        if points:
            qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
        
        # STEP E: Tell the main API that we finished successfully!
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE documents SET status = 'completed' WHERE id = :id"),
                {"id": document_id}
            )
            
        print(f"🍳 CHEF: Document {document_id} completely processed and stored in Qdrant!")
        return "SUCCESS"
        
    except Exception as e:
        print(f"❌ CHEF ERROR: {e}")
        # If it fails, update the database so the user knows
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE documents SET status = 'failed' WHERE id = :id"),
                {"id": document_id}
            )
        return "FAILED"