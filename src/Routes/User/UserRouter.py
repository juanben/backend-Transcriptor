from fastapi import APIRouter
from src.DB.motor import db_instance

router = APIRouter(prefix="/user", tags=["User"])

@router.post("/")
async def create_user(user: dict):
    """Crea un usuario en colección 'users' con nombre, correo y password y envía código de confirmación"""
    required = ["name", "email", "password"]
    for field in required:
        if field not in user or not str(user[field]).strip():
            return {"error": f"'{field}' es requerido"}

    email = user["email"].strip().lower()
    existing = await db_instance.db.users.find_one({"email": email})
    if existing:
        return {"error": "El correo ya está registrado"}

    confirm_code = str(__import__('uuid').uuid4()).split('-')[0]
    new_user = {
        "name": user["name"].strip(),
        "email": email,
        "password": user["password"],  # En producción hashear la contraseña
        "email_verified": False,
        "confirm_code": confirm_code,
        "session_token": None,
        "token_expires": None,
        "created_at": __import__('datetime').datetime.utcnow()
    }

    result = await db_instance.db.users.insert_one(new_user)

    # Aquí deberías enviar el código por correo. Vamos a retornarlo para pruebas.
    return {
        "user_id": str(result.inserted_id),
        "name": new_user["name"],
        "email": new_user["email"],
        "confirm_code": confirm_code,
        "message": "Usa /user/confirm para verificar correo"
    }

@router.post("/confirm")
async def confirm_email(payload: dict):
    """Confirma email con código enviado"""
    if "email" not in payload or "confirm_code" not in payload:
        return {"error": "email y confirm_code son requeridos"}

    email = payload["email"].strip().lower()
    code = str(payload["confirm_code"]).strip()

    user = await db_instance.db.users.find_one({"email": email})
    if not user:
        return {"error": "Usuario no encontrado"}
    if user.get("email_verified"):
        return {"message": "Email ya verificado"}
    if user.get("confirm_code") != code:
        return {"error": "Código de confirmación inválido"}

    await db_instance.db.users.update_one(
        {"email": email},
        {"$set": {"email_verified": True}, "$unset": {"confirm_code": ""}}
    )

    return {"message": "Email verificado correctamente"}

@router.post("/login")
async def login(payload: dict):
    """Login con email/password y crea token de sesión"""
    if "email" not in payload or "password" not in payload:
        return {"error": "email y password son requeridos"}

    email = payload["email"].strip().lower()
    password = payload["password"]

    user = await db_instance.db.users.find_one({"email": email})
    if not user:
        return {"error": "Credenciales inválidas"}
    if user.get("password") != password:
        return {"error": "Credenciales inválidas"}
    if not user.get("email_verified", False):
        return {"error": "Email no verificado"}

    token = str(__import__('uuid').uuid4())
    expires_at = __import__('datetime').datetime.utcnow() + __import__('datetime').timedelta(hours=8)

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
        return {"error": "token es requerido"}

    user = await db_instance.db.users.find_one({"session_token": token})
    if not user:
        return {"error": "Token inválido"}

    if user.get("token_expires") and user["token_expires"] < __import__('datetime').datetime.utcnow():
        return {"error": "Token expirado"}

    return {
        "user_id": str(user.get("_id")),
        "name": user.get("name"),
        "email": user.get("email"),
        "email_verified": user.get("email_verified", False)
    }

