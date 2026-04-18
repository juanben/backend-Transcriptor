"""Modelos Pydantic para validación de datos de Session"""
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional
from datetime import datetime


class CreateSessionRequest(BaseModel):
    """Validar solicitud de creación de sesión"""
    session_name: str = Field(..., min_length=1, max_length=255, description="Nombre de la sesión")
    creator_email: EmailStr = Field(..., description="Email del creador de la sesión")
    allow_download: Optional[bool] = Field(default=None, description="Permitir descarga del archivo")
    visible: Optional[bool] = Field(default=None, description="Hacer la sesión visible")
    complementaryResourses: Optional[str] = Field(default=None, description="Recursos complementarios de la sesión")
    
    @validator('session_name')
    def session_name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("El nombre de la sesión no puede estar vacío")
        return v.strip()
    
    @validator('creator_email')
    def creator_email_lowercase(cls, v):
        return v.lower().strip()

    @validator('complementaryResourses')
    def complementary_resourses_strip(cls, v):
        if v is None:
            return None
        value = v.strip()
        return value or None


class SessionResponse(BaseModel):
    """Respuesta estándar para operaciones de sesión"""
    session_id: str
    room_id: str
    name: str
    creator_email: str
    status: str
    transcription: Optional[str] = None
    summary: Optional[str] = None
    record_path: Optional[str] = None
    allow_download: bool
    visible: bool
    complementaryResourses: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ListSessionsResponse(BaseModel):
    """Respuesta al listar sesiones de una room"""
    room_id: str
    room_name: str
    total: int
    sessions: list[SessionResponse]


class SessionStatusResponse(BaseModel):
    """Respuesta de estado de la sesión"""
    session_id: str
    room_id: str
    status: str
    visible: bool
    complementaryResourses: Optional[str] = None
    name: str
    creator_email: str
    created_at: datetime
    progress: Optional[str] = None


class UpdateComplementaryResoursesRequest(BaseModel):
    """Validar solicitud para actualizar recursos complementarios."""
    owner_email: EmailStr = Field(..., description="Email del propietario de la room")
    complementaryResourses: Optional[str] = Field(default=None, description="Recursos complementarios de la sesiÃ³n")

    @validator('owner_email')
    def owner_email_lowercase(cls, v):
        return v.lower().strip()

    @validator('complementaryResourses')
    def complementary_resourses_strip(cls, v):
        if v is None:
            return None
        value = v.strip()
        return value or None


class UpdateAllowDownloadRequest(BaseModel):
    """Validar solicitud para actualizar permiso de descarga."""
    owner_email: EmailStr = Field(..., description="Email del propietario de la room")
    allow_download: bool = Field(..., description="Permitir descarga del archivo")

    @validator('owner_email')
    def owner_email_lowercase(cls, v):
        return v.lower().strip()


class UpdateVisibleRequest(BaseModel):
    """Validar solicitud para actualizar visibilidad de una sesiÃ³n."""
    owner_email: EmailStr = Field(..., description="Email del propietario de la room")
    visible: bool = Field(..., description="Hacer la sesiÃ³n visible")

    @validator('owner_email')
    def owner_email_lowercase(cls, v):
        return v.lower().strip()


class DeleteSessionRequest(BaseModel):
    """Validar solicitud para eliminar una sesiÃ³n."""
    owner_email: EmailStr = Field(..., description="Email del propietario de la room")

    @validator('owner_email')
    def owner_email_lowercase(cls, v):
        return v.lower().strip()


class ListSessionsByRoomCodeRequest(BaseModel):
    """Validar solicitud de listar sesiones por código de room"""
    room_code: str = Field(..., min_length=5, max_length=5, description="Código único de la room")
    requester_email: EmailStr = Field(..., description="Email del solicitante")
    
    @validator('room_code')
    def room_code_uppercase(cls, v):
        return v.upper().strip()
    
    @validator('requester_email')
    def requester_email_lowercase(cls, v):
        return v.lower().strip()
