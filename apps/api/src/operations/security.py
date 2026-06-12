"""JWT auth + password hashing for the /api/* information-system endpoints.

The legacy /solve and /experiment* routes stay unauthenticated — only the new
endpoints depend on ``get_current_user``.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.operations.db.base import get_session
from src.operations.db.models import User

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=24)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# tokenUrl is relative to the app root; the router is mounted at /api/auth.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> uuid.UUID | None:
    """Decode a JWT into its subject user id, or None if invalid/expired.

    Shared by the HTTP dependency (``get_current_user``) and the WebSocket
    handler, which authenticates via a query-string token because browsers
    cannot set an Authorization header on a WebSocket handshake.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            return None
        return uuid.UUID(sub)
    except (JWTError, ValueError):
        return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_token(token)
    if user_id is None:
        raise credentials_error

    user = await session.get(User, user_id)
    if user is None:
        raise credentials_error
    return user
