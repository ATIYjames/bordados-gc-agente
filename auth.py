from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import config

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
security    = HTTPBearer()

# Usuarios del sistema — cambia las contraseñas antes de subir a producción
USERS = {
    "admin": {
        "password": pwd_context.hash("admin123"),
        "rol": "admin",
        "nombre": "Administrador",
    },
    "james": {
        "password": pwd_context.hash("bordados2026"),
        "rol": "admin",
        "nombre": "James Príncipe",
    },
    "empleado1": {
        "password": pwd_context.hash("emp123"),
        "rol": "empleado",
        "nombre": "Empleado G&C",
    },
}

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=8)
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return decode_token(creds.credentials)

def require_admin(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    user = decode_token(creds.credentials)
    if user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden realizar esta acción")
    return user
