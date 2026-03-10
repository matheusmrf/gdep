import os
import secrets
from datetime import datetime

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
DEFAULT_USERNAME = os.getenv("GDEP_ADMIN_USERNAME", "admin")
DEFAULT_PASSWORD = os.getenv("GDEP_ADMIN_PASSWORD", "admin")

security = HTTPBearer(auto_error=False)
_issued_tokens = {}


def authenticate(username: str, password: str) -> str | None:
    if username != DEFAULT_USERNAME or password != DEFAULT_PASSWORD:
        return None

    token = secrets.token_urlsafe(32)
    _issued_tokens[token] = {"username": username, "issued_at": datetime.utcnow().isoformat()}
    return token


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not AUTH_ENABLED:
        return {"username": "anonymous", "auth_enabled": False}

    if credentials is None or credentials.credentials not in _issued_tokens:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    return _issued_tokens[credentials.credentials]
