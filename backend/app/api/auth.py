import hashlib
import secrets

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.config import settings

router = APIRouter()

# Generate a stable token from the password (so it survives restarts)
def _make_token(password: str) -> str:
    return hashlib.sha256(f"thecoach:{password}".encode()).hexdigest()


@router.post("/login")
async def login(request: Request, response: Response):
    body = await request.json()
    password = body.get("password", "")

    if not settings.auth_password:
        return {"ok": True}  # No auth configured

    if not password or password != settings.auth_password:
        return JSONResponse({"ok": False, "error": "Wrong password"}, status_code=401)

    token = _make_token(settings.auth_password)
    response.set_cookie(
        key="tc_auth",
        value=token,
        max_age=365 * 24 * 3600,  # 1 year
        httponly=True,
        samesite="lax",
        secure=False,  # Works on both HTTP and HTTPS
    )
    return {"ok": True}


@router.get("/check")
async def check_auth(request: Request):
    if not settings.auth_password:
        return {"authenticated": True}

    token = request.cookies.get("tc_auth")
    expected = _make_token(settings.auth_password)
    return {"authenticated": token == expected}
