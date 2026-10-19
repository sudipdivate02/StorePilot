"""
StorePilot — Auth Schemas
Pydantic models for request and response validation.
FastAPI uses these to auto-validate incoming data and
auto-generate the Swagger UI forms.
"""
from pydantic import BaseModel
from typing import Optional


# ── Request schemas (what the frontend sends) ─────────────────────────────────

class RegisterStoreRequest(BaseModel):
    store_name:  str
    owner_name:  str
    phone:       str
    password:    str

    class Config:
        json_schema_extra = {
            "example": {
                "store_name":  "Sharma General Store",
                "owner_name":  "Ramesh Sharma",
                "phone":       "9876543210",
                "password":    "mypassword123"
            }
        }


class LoginRequest(BaseModel):
    phone:    str
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "phone":    "9876543210",
                "password": "mypassword123"
            }
        }


class CreateUserRequest(BaseModel):
    """Owner uses this to create Manager or Cashier accounts."""
    name:     str
    phone:    str
    password: str
    role:     str   # "Manager" or "Cashier"


# ── Response schemas (what the API sends back) ────────────────────────────────

class AuthResponse(BaseModel):
    """Returned after successful register or login."""
    token:      str
    store_id:   int
    store_name: str
    owner_name: str
    role:       str
    message:    str


class UserResponse(BaseModel):
    """Returned when creating a new user."""
    user_id:    int
    name:       str
    phone:      str
    role:       str
    store_id:   int
    message:    str