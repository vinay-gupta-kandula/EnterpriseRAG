import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 1. We grab our database credentials from the environment variables Docker sets up
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mysecretpassword")
POSTGRES_DB = os.getenv("POSTGRES_DB", "rag_db")

# 2. This is the exact address to our PostgreSQL container (named 'db' in docker-compose)
SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@db:5432/{POSTGRES_DB}"

# 3. The 'engine' is the actual connection to the database
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 4. A 'session' is an active workspace where we add, edit, or delete data before saving it
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. All our future database tables will inherit from this Base class
Base = declarative_base()

# 6. A helper function we will use later to open a database connection and close it safely
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()