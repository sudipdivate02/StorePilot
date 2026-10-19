"""
StorePilot — JWT Handler
Creates and validates JWT tokens for authentication.
"""
import os
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY  = os.getenv("JWT_SECRET_KEY", "fallback_secret")
ALGORITHM   = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))


def create_token(user_id: int, store_id: int, role_name: str) -> str:
    """
    Creates a signed JWT token.
    Payload contains user_id, store_id, role — everything
    we need to identify who is making a request.
    """
    payload = {
        "user_id":  user_id,
        "store_id": store_id,
        "role":     role_name,
        "exp":      datetime.utcnow() + timedelta(hours=EXPIRE_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decodes and validates a JWT token.
    Returns the payload dict if valid.
    Raises an exception if expired or invalid.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired. Please login again.")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token. Please login again.")  