from typing import Optional
from urllib.parse import urlsplit

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days
SESSION_SALT = "web-session"


def request_origin(request) -> tuple[str, str]:
    configured = urlsplit(settings.PUBLIC_BASE_URL)
    # TLS may terminate at the platform proxy. Trust only the operator's
    # configured HTTPS origin for this host, never arbitrary forwarded headers.
    if configured.scheme == "https" and configured.netloc == request.url.netloc:
        return configured.scheme, configured.netloc
    return request.url.scheme, request.url.netloc


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt=SESSION_SALT)


def create_session_token(user_id: int) -> str:
    return _serializer().dumps({"user_id": user_id})


def read_session_token(token: str) -> Optional[int]:
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired, ValueError):
        return None
    return data.get("user_id")


def sign_export(filename: str) -> str:
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt="export-download").dumps(filename)


def valid_export_token(token: str, filename: str) -> bool:
    try:
        return URLSafeTimedSerializer(settings.SECRET_KEY, salt="export-download").loads(token, max_age=3600) == filename
    except (BadSignature, SignatureExpired, ValueError):
        return False
