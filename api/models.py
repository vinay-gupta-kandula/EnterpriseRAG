from sqlalchemy import Column, String, DateTime
from database import Base
import uuid
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    # The primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # This is the core of our multi-tenancy. Every user belongs to a tenant.
    tenant_id = Column(String, index=True, nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    filename = Column(String, nullable=False)
    
    # We store the tenant_id here too! This ensures users can only search their own tenant's files.
    tenant_id = Column(String, index=True, nullable=False)
    
    status = Column(String, default="processing") # Can be 'processing', 'completed', or 'failed'
    created_at = Column(DateTime, default=datetime.utcnow)