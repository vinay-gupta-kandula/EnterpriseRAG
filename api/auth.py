import os
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt

# Get our secret keys from the environment variables, or use defaults
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "my_super_secret_jwt_key")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # Token expires in 1 hour

# Set up the password hashing tool (bcrypt is the industry standard)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Takes a plain text password and returns a scrambled hash."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Checks if the typed password matches the scrambled hash in the database."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    """Creates the digital VIP pass (JWT) for the user to stay logged in."""
    to_encode = data.copy()
    
    # Add an expiration time to the token
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    # Generate the actual token string
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt