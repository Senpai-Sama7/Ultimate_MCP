"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..auth.jwt_handler import JWTHandler
from ..auth.rbac import Role
from ..config import config

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In a real application, this would be a database lookup.
# For this example, we'll use a hardcoded user.
DUMMY_USERS_DB = {
    "admin": {
        "password": "admin_password",
        "roles": [Role.ADMIN, Role.DEVELOPER, Role.VIEWER],
    },
    "developer": {
        "password": "dev_password",
        "roles": [Role.DEVELOPER, Role.VIEWER],
    },
    "viewer": {
        "password": "viewer_password",
        "roles": [Role.VIEWER],
    },
}

jwt_handler = JWTHandler(
    secret_key=config.security.secret_key.get_secret_value() if config.security.secret_key else "",
    algorithm=config.security.jwt_algorithm,
)

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2-compatible endpoint to generate a JWT access token.
    """
    user = DUMMY_USERS_DB.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = jwt_handler.create_token(
        user_id=form_data.username,
        roles=user["roles"],
        expires_in_hours=config.security.jwt_expiration_hours,
    )
    return {"access_token": access_token, "token_type": "bearer"}
