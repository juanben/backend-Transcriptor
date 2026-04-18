"""Modelos Pydantic para validacion de datos de Room."""
from pydantic import BaseModel, EmailStr, Field, validator


class CreateRoomRequest(BaseModel):
    """Validar solicitud de creacion de room."""
    name: str = Field(..., min_length=1, max_length=255)
    owner_email: EmailStr
    is_public: bool = False
    allow_download: bool = False

    @validator("name")
    def name_not_empty(cls, value):
        if not value.strip():
            raise ValueError("El nombre de la room no puede estar vacio")
        return value.strip()

    @validator("owner_email")
    def owner_email_lowercase(cls, value):
        return value.lower().strip()


class JoinRoomRequest(BaseModel):
    """Validar solicitud para unirse a una room."""
    user_email: EmailStr

    @validator("user_email")
    def user_email_lowercase(cls, value):
        return value.lower().strip()


class JoinRoomByCodeRequest(BaseModel):
    """Validar solicitud para unirse a una room por codigo."""
    room_code: str = Field(..., min_length=5, max_length=5)
    user_email: EmailStr

    @validator("room_code")
    def room_code_uppercase(cls, value):
        return value.upper().strip()

    @validator("user_email")
    def user_email_lowercase(cls, value):
        return value.lower().strip()


class UpdateRoomNameRequest(BaseModel):
    """Validar solicitud para actualizar el nombre de una room."""
    new_name: str = Field(..., min_length=1, max_length=255)
    owner_email: EmailStr

    @validator("new_name")
    def new_name_not_empty(cls, value):
        if not value.strip():
            raise ValueError("El nuevo nombre no puede estar vacio")
        return value.strip()

    @validator("owner_email")
    def owner_email_lowercase(cls, value):
        return value.lower().strip()


class WaitlistRequest(BaseModel):
    """Validar solicitud para agregarse a la lista de espera."""
    user_email: EmailStr

    @validator("user_email")
    def user_email_lowercase(cls, value):
        return value.lower().strip()


class GetWaitlistRequest(BaseModel):
    """Validar solicitud para consultar la lista de espera."""
    owner_email: EmailStr

    @validator("owner_email")
    def owner_email_lowercase(cls, value):
        return value.lower().strip()


class AcceptWaitlistMemberRequest(BaseModel):
    """Validar solicitud para aceptar un usuario de la lista de espera."""
    owner_email: EmailStr
    user_email: EmailStr

    @validator("owner_email")
    def owner_email_lowercase(cls, value):
        return value.lower().strip()

    @validator("user_email")
    def user_email_lowercase(cls, value):
        return value.lower().strip()


class AcceptAllWaitlistRequest(BaseModel):
    """Validar solicitud para aceptar toda la lista de espera."""
    owner_email: EmailStr

    @validator("owner_email")
    def owner_email_lowercase(cls, value):
        return value.lower().strip()


class DeleteRoomRequest(BaseModel):
    """Validar solicitud para eliminar una room."""
    owner_email: EmailStr

    @validator("owner_email")
    def owner_email_lowercase(cls, value):
        return value.lower().strip()
