"""
StorePilot — Auth Dependencies
FastAPI dependencies for protecting routes.
Used as: current_user = Depends(get_current_user)
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth.jwt_handler import decode_token

# This tells FastAPI to look for "Authorization: Bearer <token>" header
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """
    Extracts and validates JWT from the Authorization header.
    Returns the token payload (user_id, store_id, role).

    Add this as a dependency to any route that requires login:
    @router.get("/something")
    def my_route(current_user = Depends(get_current_user)):
        store_id = current_user["store_id"]
    """
    token = credentials.credentials
    try:
        payload = decode_token(token)
        return payload
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_owner(current_user: dict = Depends(get_current_user)) -> dict:
    """Only allows Owner role."""
    if current_user["role"] != "Owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the store owner can perform this action."
        )
    return current_user


def require_owner_or_manager(current_user: dict = Depends(get_current_user)) -> dict:
    """Allows Owner or Manager roles."""
    if current_user["role"] not in ["Owner", "Manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Owner or Manager can perform this action."
        )
    return current_user


def require_role(allowed_roles: list):
    """
    Factory dependency — pass a list of allowed roles.
    Usage: Depends(require_role(["Owner", "Manager"]))
    """
    def _check(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to: {', '.join(allowed_roles)}."
            )
        return current_user
    return _check