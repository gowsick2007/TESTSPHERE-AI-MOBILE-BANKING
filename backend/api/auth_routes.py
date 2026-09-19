"""
TestSphere AI — Authentication Routes
Endpoints for user login and role checks.
"""
from fastapi import APIRouter, HTTPException, Depends, Response, Cookie, Header, Query, Request
from typing import Optional, Any
from backend.schemas import LoginRequest, LoginResponse
from backend.security.auth import verify_password
import secrets

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Simple in-memory session store mapping token ➔ user_info
SESSIONS = {}


def get_user_from_token(
    request_or_token: Any = None,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> dict:
    """Helper/Dependency to validate token and return user details."""
    resolved_token = None
    if isinstance(request_or_token, str):
        resolved_token = request_or_token
    elif isinstance(request_or_token, Request):
        if token:
            resolved_token = token
        elif authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                resolved_token = parts[1]
            else:
                resolved_token = authorization.strip()
        elif x_token:
            resolved_token = x_token
        elif session_token:
            resolved_token = session_token
        elif "token" in request_or_token.query_params:
            resolved_token = request_or_token.query_params.get("token")
    else:
        if token:
            resolved_token = token
        elif authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                resolved_token = parts[1]
            else:
                resolved_token = authorization.strip()
        elif x_token:
            resolved_token = x_token
        elif session_token:
            resolved_token = session_token

    if not resolved_token or resolved_token not in SESSIONS:
        raise HTTPException(status_code=401, detail="Unauthorized access. Invalid or missing token.")
    return SESSIONS[resolved_token]


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response):
    user = verify_password(payload.username, payload.password)
    if not user:
        return LoginResponse(success=False, username="", role="", error="Invalid username or password credentials.")

    # Generate a simple session token
    token = secrets.token_hex(24)
    SESSIONS[token] = {
        "username": user["username"],
        "role": user["role"]
    }

    # Set cookie for easy session management
    response.set_cookie(key="session_token", value=token, path="/", httponly=True)
    return LoginResponse(success=True, username=user["username"], role=user["role"], token=token)


@router.post("/logout")
def logout(response: Response, session_token: str = Cookie(None)):
    if session_token and session_token in SESSIONS:
        del SESSIONS[session_token]
    response.delete_cookie("session_token")
    return {"success": True, "message": "Log out complete."}


@router.get("/me")
def get_me(
    request: Request = None,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
):
    try:
        user = get_user_from_token(
            request_or_token=request,
            token=token,
            authorization=authorization,
            x_token=x_token,
            session_token=session_token,
        )
        return {
            "username": user["username"],
            "role": user["role"],
            "authenticated": True
        }
    except HTTPException:
        return {"username": "Guest User", "role": "VIEWER", "authenticated": False}

