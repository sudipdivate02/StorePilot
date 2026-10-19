"""
StorePilot — Auth Router
Endpoints:
  POST /api/v1/auth/register-store  — create store + Owner account
  POST /api/v1/auth/login           — login, returns JWT
  POST /api/v1/auth/users           — Owner creates Manager/Cashier
  GET  /api/v1/auth/me              — get current user info
"""
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import Store, Role, User
from app.auth.jwt_handler import create_token
from app.auth.dependencies import get_current_user, require_owner
from app.schemas.auth import (
    RegisterStoreRequest,
    LoginRequest,
    CreateUserRequest,
    AuthResponse,
    UserResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Converts plain password to bcrypt hash."""
    return bcrypt.hashpw(
        plain.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Checks if plain password matches the stored hash."""
    return bcrypt.checkpw(
        plain.encode('utf-8'),
        hashed.encode('utf-8')
    )


# ── Role helper ───────────────────────────────────────────────────────────────

def get_or_create_role(db: Session, role_name: str) -> Role:
    """
    Gets an existing role or creates it if it doesn't exist.
    Handles Owner, Manager, Cashier roles.
    """
    role = db.query(Role).filter(Role.role_name == role_name).first()
    if not role:
        role = Role(role_name=role_name)
        db.add(role)
        db.flush()
    return role


# ── REGISTER STORE ────────────────────────────────────────────────────────────

@router.post("/register-store", response_model=AuthResponse, status_code=201)
def register_store(body: RegisterStoreRequest, db: Session = Depends(get_db)):
    """
    Creates a new store and the first Owner account.
    Called when a shopkeeper registers for the first time.
    """

    # Check if phone already registered
    existing = db.query(User).filter(User.phone == body.phone).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This phone number is already registered."
        )

    # Create store
    store = Store(
        store_name=body.store_name,
        owner_name=body.owner_name,
        phone=body.phone,
    )
    db.add(store)
    db.flush()

    # Get or create Owner role
    owner_role = get_or_create_role(db, "Owner")

    # Create owner user
    user = User(
        store_id=store.store_id,
        role_id=owner_role.role_id,
        name=body.owner_name,
        phone=body.phone,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(store)

    # Create JWT token
    token = create_token(user.user_id, store.store_id, "Owner")

    return AuthResponse(
        token=token,
        store_id=store.store_id,
        store_name=store.store_name,
        owner_name=store.owner_name,
        role="Owner",
        message="Store registered successfully. Welcome to StorePilot!"
    )


# ── LOGIN ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Logs in a user by phone number and password.
    Returns a JWT token valid for 24 hours.
    """

    # Find user by phone
    user = db.query(User).filter(
        User.phone == body.phone,
        User.is_active == True
    ).first()

    # Check user exists and password is correct
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phone number or password is wrong."
        )

    # Get store info
    store = db.query(Store).filter(
        Store.store_id == user.store_id
    ).first()

    # Get role name
    role = db.query(Role).filter(Role.role_id == user.role_id).first()
    role_name = role.role_name if role else "Owner"

    # Create token
    token = create_token(user.user_id, user.store_id, role_name)

    return AuthResponse(
        token=token,
        store_id=user.store_id,
        store_name=store.store_name if store else "",
        owner_name=store.owner_name if store else "",
        role=role_name,
        message="Login successful."
    )


# ── CREATE MANAGER / CASHIER ──────────────────────────────────────────────────

@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_owner)
):
    """
    Owner creates a Manager or Cashier account for their store.
    """

    # Validate role
    if body.role not in ["Manager", "Cashier"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be Manager or Cashier."
        )

    # Check phone not already taken
    existing = db.query(User).filter(User.phone == body.phone).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This phone number is already registered."
        )

    # Get or create role
    role = get_or_create_role(db, body.role)

    # Create user under the same store as the owner
    user = User(
        store_id=current_user["store_id"],
        role_id=role.role_id,
        name=body.name,
        phone=body.phone,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(
        user_id=user.user_id,
        name=user.name,
        phone=user.phone,
        role=body.role,
        store_id=user.store_id,
        message=f"{body.role} account created successfully."
    )


# ── GET CURRENT USER ──────────────────────────────────────────────────────────

@router.get("/me")
def get_me(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the currently logged in user's info.
    Frontend calls this on page load to get store name etc.
    """
    user = db.query(User).filter(
        User.user_id == current_user["user_id"]
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    store = db.query(Store).filter(Store.store_id == user.store_id).first()
    role  = db.query(Role).filter(Role.role_id == user.role_id).first()

    return {
        "user_id":    user.user_id,
        "name":       user.name,
        "phone":      user.phone,
        "role":       role.role_name if role else "",
        "store_id":   user.store_id,
        "store_name": store.store_name if store else "",
        "owner_name": store.owner_name if store else "",
    }

@router.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.user import User, Store
    user = db.query(User).filter(User.user_id == current_user["user_id"]).first()
    store = db.query(Store).filter(Store.store_id == current_user["store_id"]).first()
    return {
        "name": user.name,
        "phone": user.phone,
        "role": user.role.role_name if user.role else current_user["role"],
        "store_name": store.store_name if store else "",
        "gst_number": store.gst_number if store else "",
        "address": store.address if store else "",
    }