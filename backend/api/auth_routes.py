"""
TestSphere AI — Authentication Routes
Endpoints for user login and role checks.
"""
from fastapi import APIRouter, HTTPException, Depends, Response, Cookie
from backend.schemas import LoginRequest, LoginResponse
from backend.security.auth import verify_password
import secrets

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Simple in-memory session store mapping token ➔ user_info
SESSIONS = {}


def get_user_from_token(token: str) -> dict:
    """Helper to validate token and return user details."""
    if not token or token not in SESSIONS:
        raise HTTPException(status_code=401, detail="Unauthorized access. Invalid or missing token.")
    return SESSIONS[token]


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
def get_me(session_token: str = Cookie(None)):
    if not session_token or session_token not in SESSIONS:
        # For simplicity in local execution, return default guest if no session
        return {"username": "Guest User", "role": "VIEWER", "authenticated": False}
    user = SESSIONS[session_token]
    return {
        "username": user["username"],
        "role": user["role"],
        "authenticated": True
    }
