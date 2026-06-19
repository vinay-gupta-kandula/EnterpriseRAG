from pydantic import BaseModel

# Schema for what the user sends us when registering/logging in
class UserCreate(BaseModel):
    email: str
    password: str

# Schema for what we send back after they register (Notice we DON'T send the password back!)
class UserResponse(BaseModel):
    id: str
    email: str
    tenant_id: str

    class Config:
        from_attributes = True # This tells Pydantic to read data directly from our database model

# Schema for the login token
class Token(BaseModel):
    access_token: str
    token_type: str

# Schema for the response immediately after uploading a file
class DocumentResponse(BaseModel):
    document_id: str
    status: str

# Schema for checking if the file is done processing
class DocumentStatus(BaseModel):
    document_id: str
    status: str

# Schema for the user's question
class QueryRequest(BaseModel):
    query: str

# Schema for the citations/sources
class Source(BaseModel):
    document_id: str
    content: str

# Schema for the final AI answer
class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]