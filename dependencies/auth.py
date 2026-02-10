from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from config.database import db
import logging

logger = logging.getLogger(__name__)
auth_scheme = HTTPBearer(auto_error=False)

def _extract_token_from_header_value(val: str) -> Optional[str]:
    if not val:
        return None
    val = val.strip()
    if val.lower().startswith("bearer "):
        return val.split(" ", 1)[1].strip()
    return val

def verify_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme)
):
    token = None
    if credentials and getattr(credentials, "credentials", None):
        token = credentials.credentials
    if not token:
        auth_raw = request.headers.get("authorization") or request.headers.get("Authorization")
        token = _extract_token_from_header_value(auth_raw)
    if not token:
        token = _extract_token_from_header_value(request.headers.get("x-access-token") or "")
    if not token:
        token = _extract_token_from_header_value(request.headers.get("token") or "")
    if not token:
        raise HTTPException(status_code=403, detail="Not authenticated (missing token)")

    if not token.startswith("1|"):
        raise HTTPException(status_code=403, detail="Not authenticated (invalid token prefix)")

    parts = token.split("|")
    if len(parts) < 3:
        raise HTTPException(status_code=403, detail="Invalid token format")

    role = parts[1]
    username = parts[2] if len(parts) > 2 else "unknown"
    
    # Verifikasi role dari database
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, username, role, nama_lengkap, email, no_telepon, alamat FROM users WHERE username = %s AND role = %s LIMIT 1", (username, role))
    user = cursor.fetchone()
    cursor.close()
    connection.close()
    
    if not user:
        raise HTTPException(status_code=403, detail="Role atau username tidak valid")

    return {
        "token": token, 
        "role": role, 
        "username": user['username'],
        "user_id": user['id'],
        "user_data": user
    }

def verify_admin(token: dict = Depends(verify_token)):
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Hanya admin yang bisa mengakses")
    return token

def verify_user(token: dict = Depends(verify_token)):
    if token["role"] != "user":
        raise HTTPException(status_code=403, detail="Hanya user yang bisa mengakses")
    return token