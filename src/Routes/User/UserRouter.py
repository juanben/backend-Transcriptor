from fastapi import APIRouter, HTTPException, status
from src.DB.motor import db_instance
from datetime import datetime, timedelta
import os

router = APIRouter(prefix="/user", tags=["User"])

# URL base para los enlaces de confirmación (configurable)
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

@router.post("/")
async def create_user(user: dict):
    """Crea un usuario en colección 'users' con nombre, correo y password y envía código de confirmación"""
    required = ["name", "email", "password"]
    for field in required:
        if field not in user or not str(user[field]).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{field}' es requerido"
            )

    email = user["email"].strip().lower()
    existing = await db_instance.db.users.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo ya está registrado"
        )

    confirm_code = str(__import__('uuid').uuid4()).split('-')[0]
    new_user = {
        "name": user["name"].strip(),
        "email": email,
        "password": user["password"],  # En producción hashear la contraseña
        "email_verified": False,
        "confirm_code": confirm_code,
        "session_token": None,
        "token_expires": None,
        "created_at": datetime.utcnow()
    }

    result = await db_instance.db.users.insert_one(new_user)

    # Generar URL de confirmación
    confirm_url = f"{BASE_URL}/user/confirm?email={email}&code={confirm_code}"

    # Aquí deberías enviar el código por correo. Vamos a retornarlo para pruebas.
    return {
        "user_id": str(result.inserted_id),
        "name": new_user["name"],
        "email": new_user["email"],
        "confirm_code": confirm_code,
        "confirm_url": confirm_url,
        "message": "Haz clic en el enlace para verificar tu correo"
    }

@router.post("/confirm")
async def confirm_email(payload: dict):
    """Confirma email con código enviado (vía POST)"""
    if "email" not in payload or "confirm_code" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email y confirm_code son requeridos"
        )

    email = payload["email"].strip().lower()
    code = str(payload["confirm_code"]).strip()

    user = await db_instance.db.users.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    if user.get("email_verified"):
        return {"message": "Email ya verificado"}
    if user.get("confirm_code") != code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de confirmación inválido"
        )

    await db_instance.db.users.update_one(
        {"email": email},
        {"$set": {"email_verified": True}, "$unset": {"confirm_code": ""}}
    )

    return {"message": "Email verificado correctamente"}

@router.get("/confirm")
async def confirm_email_get(email: str, code: str):
    """Confirma email con código enviado (vía GET - hacer clic en el link)"""
    if not email or not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email y code son requeridos"
        )

    email = email.strip().lower()
    code = str(code).strip()

    user = await db_instance.db.users.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    if user.get("email_verified"):
        return {"message": "Email ya verificado"}
    if user.get("confirm_code") != code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de confirmación inválido"
        )

    await db_instance.db.users.update_one(
        {"email": email},
        {"$set": {"email_verified": True}, "$unset": {"confirm_code": ""}}
    )

    return {"message": "Email verificado correctamente. Puedes cerrar esta ventana."}

@router.post("/login")
async def login(payload: dict):
    """Login con email/password y crea token de sesión"""
    if "email" not in payload or "password" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email y password son requeridos"
        )

    email = payload["email"].strip().lower()
    password = payload["password"]

    user = await db_instance.db.users.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Credenciales inválidas"
        )
    if user.get("password") != password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Credenciales inválidas"
        )
    if not user.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Email no verificado"
        )

    token = str(__import__('uuid').uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=8)

    await db_instance.db.users.update_one(
        {"email": email},
        {"$set": {"session_token": token, "token_expires": expires_at}}
    )

    return {
        "message": "Login exitoso",
        "session_token": token,
        "expires_at": expires_at.isoformat()
    }

@router.get("/me")
async def me(token: str):
    """Consulta usuario autenticado por token de sesión"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="token es requerido"
        )

    user = await db_instance.db.users.find_one({"session_token": token})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )

    if user.get("token_expires") and user["token_expires"] < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado"
        )

    return {
        "user_id": str(user.get("_id")),
        "name": user.get("name"),
        "email": user.get("email"),
        "email_verified": user.get("email_verified", False)
    }

