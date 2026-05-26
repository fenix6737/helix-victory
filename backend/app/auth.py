from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
ingest_key_header = APIKeyHeader(name="X-Ingest-Key", auto_error=False)

ALGORITHM = "HS256"


def verify_admin_credentials(username: str, password: str) -> bool:
    return username == settings.admin_username and password == settings.admin_password


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": subject, "role": "admin", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "認証が無効です") from e


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ログインが必要です")
    payload = decode_token(credentials.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "権限がありません")
    return payload


async def require_admin_or_ingest_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ingest_key: str | None = Depends(ingest_key_header),
) -> dict:
    if ingest_key and ingest_key == settings.ingest_api_key:
        return {"role": "collector"}
    return await require_admin(credentials)
