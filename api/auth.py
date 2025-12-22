"""
Authentication and Authorization Module
========================================

Handles JWT token generation, validation, and password verification.
Uses environment variables for configuration:
- SECRET_KEY: JWT signing key (required in production)
- UI_PASSWORD: Single password for authentication (required in production)
- ACCESS_TOKEN_EXPIRE_MINUTES: Token expiration time (default: 1440 = 24 hours)
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours default
UI_PASSWORD = os.getenv("UI_PASSWORD", "")  # Empty default for development

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str) -> bool:
    """
    Verify a plain password against the UI_PASSWORD environment variable.

    Args:
        plain_password: The password to verify

    Returns:
        True if password matches, False otherwise
    """
    if not UI_PASSWORD:
        # Development mode: allow any password if UI_PASSWORD not set
        return True

    return plain_password == UI_PASSWORD


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    Dependency to get the current authenticated user from JWT token.

    Args:
        credentials: HTTP Authorization header with Bearer token

    Returns:
        User data from token payload

    Raises:
        HTTPException: If token is missing or invalid (401 Unauthorized)
    """
    # Development mode: skip auth if UI_PASSWORD not set
    if not UI_PASSWORD:
        return {"authenticated": True, "dev_mode": True}

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Optional authentication dependency.
    Returns user data if authenticated, None otherwise (no error).

    Useful for endpoints that work with or without authentication.
    """
    if not credentials:
        return None

    token = credentials.credentials
    payload = decode_access_token(token)

    return payload
