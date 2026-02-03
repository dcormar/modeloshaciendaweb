from datetime import datetime, timedelta
from typing import Optional
import os
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

logger = logging.getLogger("auth")

# =========================
# Configuracion desde variables de entorno
# =========================
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

# Usuario(s) de demo en memoria (sin BD)
fake_users_db = {
    "demo@demo.com": {
        "username": "demo@demo.com",
        "full_name": "Demo User",
        # password en claro: "demo"
        "hashed_password": "$2b$12$ifqc0gT0cKUSs9oszgJIhulcWO4tnCoTJzkDxFiO1crBUjArglfIG",
        "disabled": False,
    }
}

# =========================
# Modelos
# =========================
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

# =========================
# Seguridad
# =========================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

router = APIRouter(prefix="/api/auth", tags=["auth"])

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def get_user(db: dict, username: str) -> Optional[UserInDB]:
    user_dict = db.get(username)
    if user_dict:
        return UserInDB(**user_dict)
    return None

def authenticate_user(db: dict, username: str, password: str) -> Optional[UserInDB]:
    user = get_user(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if user.disabled:
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    
    logger.debug(f"[AUTH] Token creado para {data.get('sub')} - expira: {expire.isoformat()} ({ACCESS_TOKEN_EXPIRE_MINUTES}min)")
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# =========================
# Dependencia reutilizable
# =========================
def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Extrae el usuario autenticado desde el JWT (Authorization: Bearer <token>).
    Lanza 401 si el token no es valido o el usuario no existe en fake_users_db.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        exp_timestamp = payload.get("exp")
        
        # Log del estado del token (solo en DEBUG)
        if exp_timestamp:
            exp_datetime = datetime.utcfromtimestamp(exp_timestamp)
            now = datetime.utcnow()
            remaining = exp_datetime - now
            remaining_sec = remaining.total_seconds()
            
            if remaining_sec < 0:
                logger.warning(f"[AUTH] Token EXPIRADO para {username} - expiro hace {abs(remaining_sec):.0f}s")
            else:
                logger.debug(f"[AUTH] Token OK para {username} - {remaining_sec:.0f}s restantes ({remaining_sec/60:.1f}min)")
        
        if username is None:
            logger.warning("[AUTH] Token sin username (sub)")
            raise credentials_exception
            
    except JWTError as e:
        logger.error(f"[AUTH] JWT Error: {type(e).__name__} - {str(e)}")
        raise credentials_exception

    user_in_db = get_user(fake_users_db, username)
    if user_in_db is None:
        logger.warning(f"[AUTH] Usuario no encontrado: {username}")
        raise credentials_exception

    return User(username=user_in_db.username, full_name=user_in_db.full_name, disabled=user_in_db.disabled)

# =========================
# Endpoints
# =========================
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login con usuario/contrasena contra fake_users_db.
    Por defecto existe:
      username: demo@demo.com
      password: demo
    """
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        logger.warning(f"[AUTH] Login fallido: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"[AUTH] Login exitoso: {form_data.username}")
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: User = Depends(get_current_user)):
    """
    Refresca el token de acceso, extendiendo la sesion por ACCESS_TOKEN_EXPIRE_MINUTES mas.
    Util para mantener la sesion activa cuando hay actividad del usuario.
    """
    logger.info(f"[AUTH] Token refrescado: {current_user.username}")
    access_token = create_access_token(
        data={"sub": current_user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}
