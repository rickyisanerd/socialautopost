"""Session-based authentication for the SocialAutoPost dashboard."""

import hashlib
import hmac
import json
import time
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from app.core.config import settings

# Sessions last 7 days
SESSION_MAX_AGE = 7 * 24 * 60 * 60
COOKIE_NAME = "sap_session"


def _sign(payload: str) -> str:
    """Create HMAC signature for a payload."""
    return hmac.new(
        settings.secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def create_session_cookie(username: str) -> str:
    """Create a signed session cookie value."""
    payload = json.dumps({"user": username, "exp": int(time.time()) + SESSION_MAX_AGE})
    sig = _sign(payload)
    return f"{payload}|{sig}"


def verify_session(cookie_value: str) -> str | None:
    """Verify a session cookie. Returns username if valid, None otherwise."""
    if not cookie_value or "|" not in cookie_value:
        return None
    try:
        payload, sig = cookie_value.rsplit("|", 1)
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        data = json.loads(payload)
        if data.get("exp", 0) < time.time():
            return None
        return data.get("user")
    except Exception:
        return None


def check_password(username: str, password: str) -> bool:
    """Check credentials against env vars."""
    return (
        hmac.compare_digest(username, settings.admin_username)
        and hmac.compare_digest(password, settings.admin_password)
    )


def get_current_user(request: Request) -> str | None:
    """Extract authenticated user from request cookies."""
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    return verify_session(cookie)


def require_auth(request: Request) -> str:
    """Dependency: redirect to login if not authenticated."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    return user
