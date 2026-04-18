"""
Router de Sesiones - Endpoints para gestionar sesiones de grabación en rooms.
Cada sesión representa una grabación de audio dentro de una room específica.
"""
from fastapi import APIRouter, UploadFile, BackgroundTasks, HTTPException, status, Query, Form
from typing import Optional

from src.Routes.Session.SessionService import SessionService
from src.Routes.Session.SessionModels import (
    CreateSessionRequest,
    DeleteSessionRequest,
    ListSessionsResponse,
    SessionStatusResponse,
    ListSessionsByRoomCodeRequest,
    UpdateAllowDownloadRequest,
    UpdateComplementaryResoursesRequest,
    UpdateVisibleRequest,
)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


# ==================== CREAR SESIÓN ====================

@router.post("/{room_id}/create", status_code=status.HTTP_201_CREATED)
async def create_session(
    room_id: str,
    file: UploadFile,
    session_name: str = Form(..., min_length=1, max_length=255, description="Nombre de la sesión"),
    creator_email: str = Form(..., description="Email del creador"),
    allow_download: Optional[bool] = Form(None, description="Permitir descarga"),
    visible: Optional[bool] = Form(None, description="Hacer la sesión visible"),
    complementaryResourses: Optional[str] = Form(None, description="Recursos complementarios"),
    background_tasks: BackgroundTasks = None
):
    """
    Crear una nueva sesión en una room.
    
    - **room_id**: ID de MySQL de la room destino
    - **file**: Archivo de audio (webm, mp3, wav, etc.)
    - **session_name**: Nombre descriptivo de la sesión
    - **creator_email**: Email del usuario que crea la sesión (debe ser propietario de la room)
    - **allow_download**: Permitir descarga (opcional, hereda de room si no se especifica)
    - **complementaryResourses**: Recursos complementarios asociados a la sesión
    
    Nota: El procesamiento de transcripción y resumen se ejecuta en background.
    """
    try:
        # Leer contenido del archivo
        file_content = await file.read()
        
        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo está vacío"
            )
        
        if len(file_content) > 100 * 1024 * 1024:  # Límite 100MB
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="El archivo es demasiado grande (máximo 100MB)"
            )
        
        # Crear request validado
        session_request = CreateSessionRequest(
            session_name=session_name,
            creator_email=creator_email,
            allow_download=allow_download,
            visible=visible,
            complementaryResourses=complementaryResourses
        )
        
        # Crear sesión
        result = await SessionService.create_session(
            room_id=room_id,
            file_content=file_content,
            session_request=session_request,
            background_tasks=background_tasks
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando sesión: {str(e)}"
        )


# ==================== LISTAR SESIONES ====================

@router.get("/{room_id}/list")
async def list_sessions(
    room_id: str,
    requester_email: str = Query(..., description="Email del solicitante para validar acceso"),
    limit: int = Query(100, ge=1, le=1000, description="Cantidad máxima de sesiones")
):
    """
    Lista todas las sesiones de una room.
    
    - **room_id**: ID de MongoDB de la room
    - **requester_email**: Email del usuario (necesario para validación de acceso)
    - **limit**: Cantidad máxima de resultados (máx 1000)
    
    Nota: Solo puedes ver sesiones de rooms en las que eres miembro, propietario, o que son públicas.
    """
    try:
        result = await SessionService.list_sessions_by_room_id(
            room_id=room_id,
            requester_email=requester_email,
            limit=limit
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listando sesiones: {str(e)}"
        )


@router.get("/list/by-code")
async def list_sessions_by_code(
    room_code: str = Query(..., min_length=5, max_length=5, description="Código único de la room (5 caracteres)"),
    requester_email: str = Query(..., description="Email del solicitante"),
    limit: int = Query(100, ge=1, le=1000, description="Cantidad máxima de sesiones")
):
    """
    Lista sesiones de una room usando su código en lugar de ID.
    
    - **room_code**: Código de la room (5 caracteres, ej: X7B9P)
    - **requester_email**: Email del solicitante
    - **limit**: Máximo de resultados
    
    Ventaja: Permite acceder a sesiones compartiendo solo el código de la room.
    """
    try:
        result = await SessionService.list_sessions_by_room_code(
            room_code=room_code,
            requester_email=requester_email,
            limit=limit
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listando sesiones: {str(e)}"
        )


# ==================== ESTADO DE SESIÓN ====================

@router.get("/{room_id}/{session_id}/status")
async def get_session_status(
    room_id: str,
    session_id: str,
    requester_email: str = Query(..., description="Email del solicitante")
):
    """
    Obtiene el estado actual de una sesión (útil para polling del progreso).
    
    Estados posibles:
    - **pending**: Esperando procesamiento
    - **processing**: Transcribiendo y resumiendo
    - **completed**: Listo (con transcripción y resumen)
    - **failed**: Error durante el procesamiento
    """
    try:
        result = await SessionService.get_session_status(
            room_id=room_id,
            session_id=session_id,
            requester_email=requester_email
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado: {str(e)}"
        )


# ==================== DETALLES DE SESIÓN ====================

@router.get("/{room_id}/{session_id}/details")
async def get_session_details(
    room_id: str,
    session_id: str,
    requester_email: str = Query(..., description="Email del solicitante")
):
    """
    Obtiene detalles completos de una sesión incluyendo transcripción y resumen.
    
    Devuelve:
    - Información completa de la sesión
    - Transcripción del audio
    - Resumen generado
    - Metadata (creador, fecha, etc.)
    """
    try:
        result = await SessionService.get_session_details(
            room_id=room_id,
            session_id=session_id,
            requester_email=requester_email
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo detalles: {str(e)}"
        )


@router.put("/{room_id}/{session_id}/complementary-resourses")
async def update_complementary_resourses(
    room_id: str,
    session_id: str,
    payload: UpdateComplementaryResoursesRequest
):
    """
    Actualiza los recursos complementarios de una sesiÃ³n.

    Solo el propietario de la room puede actualizar este campo.
    """
    try:
        return await SessionService.update_complementary_resourses(
            room_id=room_id,
            session_id=session_id,
            request=payload
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando recursos complementarios: {str(e)}"
        )


@router.put("/{room_id}/{session_id}/allow-download")
async def update_allow_download(
    room_id: str,
    session_id: str,
    payload: UpdateAllowDownloadRequest
):
    """
    Actualiza el permiso de descarga de una sesiÃ³n.

    Solo el propietario de la room puede actualizar este campo.
    """
    try:
        return await SessionService.update_allow_download(
            room_id=room_id,
            session_id=session_id,
            request=payload
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando permiso de descarga: {str(e)}"
        )


@router.put("/{room_id}/{session_id}/visible")
async def update_visible(
    room_id: str,
    session_id: str,
    payload: UpdateVisibleRequest
):
    """
    Actualiza la visibilidad de una sesiÃ³n.

    Solo el propietario de la room puede actualizar este campo.
    """
    try:
        return await SessionService.update_visible(
            room_id=room_id,
            session_id=session_id,
            request=payload
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando visibilidad: {str(e)}"
        )


@router.delete("/{room_id}/{session_id}")
async def delete_session(
    room_id: str,
    session_id: str,
    payload: DeleteSessionRequest
):
    """
    Elimina una sesiÃ³n.

    Solo el propietario de la room puede eliminar sesiones.
    """
    try:
        return await SessionService.delete_session(
            room_id=room_id,
            session_id=session_id,
            request=payload
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error eliminando sesiÃ³n: {str(e)}"
        )
