"""Servicio de lógica de negocio para Sessions"""
from datetime import datetime
from pathlib import Path
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from bson import ObjectId

from src.DB.motor import db_instance
from src.Routes.Session.SessionModels import (
    CreateSessionRequest,
    DeleteSessionRequest,
    UpdateAllowDownloadRequest,
    UpdateComplementaryResoursesRequest,
    UpdateVisibleRequest,
)
from src.Utils.whisper_tools import transcribe_audio
from src.Utils.ollama_tools import generate_summary

# Executor para tareas sincrónicas pesadas (transcripción, etc.)
executor = ThreadPoolExecutor(max_workers=4)


class SessionService:
    """
    Servicio centralizado para operaciones de Session.
    Maneja lógica de negocio, validaciones y procesamiento en background.
    """
    
    # Rutas por defecto
    RECORDS_DIR = Path("Records")
    
    @staticmethod
    async def _verify_room_access(room_id: str, requester_email: str, require_owner: bool = False) -> dict:
        """
        Verifica que la room exista y que el usuario tenga acceso.
        
        Args:
            room_id: ID de MongoDB de la room
            requester_email: Email del usuario solicitante
            require_owner: Si True, solo el propietario tiene acceso
            
        Returns:
            dict: Documento de la room
            
        Raises:
            ValueError: Si no existe la room o el usuario no tiene acceso
        """
        try:
            room = await db_instance.db.rooms.find_one({"_id": ObjectId(room_id)})
        except Exception:
            raise ValueError(f"ID de room inválido: {room_id}")
        
        if not room:
            raise ValueError(f"Room no encontrada: {room_id}")
        
        requester_email = requester_email.lower().strip()
        
        if require_owner:
            if room.get("owner_email") != requester_email:
                raise ValueError("Solo el propietario de la room puede crear sesiones")
        else:
            # Verificar que sea miembro o que la room sea pública
            is_member = requester_email in room.get("members", [])
            is_owner = room.get("owner_email") == requester_email
            is_public = room.get("is_public", False)
            
            if not (is_member or is_owner or is_public):
                raise ValueError("No tienes acceso a esta room")
        
        return room
    
    @staticmethod
    async def _verify_room_by_code(room_code: str, requester_email: str) -> dict:
        """
        Verifica room por código en lugar de ID.
        
        Args:
            room_code: Código único de 5 caracteres de la room
            requester_email: Email del solicitante
            
        Returns:
            dict: Documento de la room
            
        Raises:
            ValueError: Si no existe la room o no hay acceso
        """
        room = await db_instance.db.rooms.find_one({"room_code": room_code.upper()})
        
        if not room:
            raise ValueError(f"Room no encontrada con código: {room_code}")
        
        requester_email = requester_email.lower().strip()
        
        # Verificar acceso
        is_member = requester_email in room.get("members", [])
        is_owner = room.get("owner_email") == requester_email
        is_public = room.get("is_public", False)
        
        if not (is_member or is_owner or is_public):
            raise ValueError("No tienes acceso a esta room")
        
        return room

    @staticmethod
    async def _verify_owner_and_get_session(room_id: str, session_id: str, owner_email: str) -> tuple[dict, dict]:
        """Verifica owner de la room y recupera la sesiÃ³n asociada."""
        room = await SessionService._verify_room_access(
            room_id,
            owner_email,
            require_owner=True
        )

        session = await db_instance.db.sessions.find_one(
            {
                "session_id": session_id,
                "room_id": room_id
            },
            {"_id": 0}
        )

        if not session:
            raise ValueError(f"SesiÃ³n no encontrada: {session_id}")

        return room, session
    
    @staticmethod
    async def create_session(
        room_id: str,
        file_content: bytes,
        session_request: CreateSessionRequest,
        background_tasks
    ) -> dict:
        """
        Crea una nueva sesión en una room y procesa el audio en background.
        
        Args:
            room_id: ID de MongoDB de la room
            file_content: Contenido del archivo de audio en bytes
            session_request: Validación de entrada con Pydantic
            background_tasks: FastAPI BackgroundTasks para ejecución async
            
        Returns:
            dict: Información de la sesión creada
            
        Raises:
            ValueError: Si hay validaciones que fallan
        """
        # Verificar acceso a la room (el creador debe ser propietario)
        room = await SessionService._verify_room_access(
            room_id,
            session_request.creator_email,
            require_owner=True
        )
        
        # Generar ID de sesión
        session_id = str(uuid.uuid4())
        
        # Crear estructura de directorios
        session_dir = SessionService.RECORDS_DIR / room_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Guardar archivo
        file_extension = ".webm"  # Por defecto webm
        session_file_path = session_dir / f"{session_id}{file_extension}"
        
        try:
            with open(session_file_path, "wb") as f:
                f.write(file_content)
        except IOError as e:
            raise ValueError(f"Error al guardar archivo: {str(e)}")
        
        # Crear documento de sesión en BD
        session_doc = {
            "session_id": session_id,
            "room_id": room_id,
            "room_code": room.get("room_code"),  # Guardar el código también
            "name": session_request.session_name,
            "creator_email": session_request.creator_email.lower(),
            "allow_download": session_request.allow_download if session_request.allow_download is not None else room.get("allow_download", False),
            "visible": session_request.visible if session_request.visible is not None else room.get("visible", False),
            "complementaryResourses": session_request.complementaryResourses,
            "record_path": str(session_file_path),
            "status": "processing",  # pending, processing, completed, failed
            "transcription": "",
            "summary": "",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "error_message": None
        }
        
        result = await db_instance.db.sessions.insert_one(session_doc)
        
        # Lanzar procesamiento en background
        background_tasks.add_task(
            SessionService._process_session_pipeline,
            session_id,
            str(session_file_path)
        )
        
        return {
            "session_id": session_id,
            "room_id": room_id,
            "name": session_request.session_name,
            "status": "processing",
            "visible": session_doc["visible"],
            "complementaryResourses": session_doc["complementaryResourses"],
            "message": "Sesión creada. El procesamiento se ejecutará en background"
        }
    
    @staticmethod
    async def _process_session_pipeline(session_id: str, file_path: str) -> None:
        """
        Pipeline de procesamiento de audio en background.
        Ejecuta: transcripción -> resumen -> actualiza BD
        
        Args:
            session_id: ID único de la sesión
            file_path: Ruta del archivo descargado
        """
        try:
            loop = asyncio.get_event_loop()
            
            # Paso 1: Transcribir (blocking, usar executor)
            transcription = await loop.run_in_executor(
                executor,
                transcribe_audio,
                file_path
            )
            
            # Paso 2: Generar resumen (blocking, usar executor)
            summary = await loop.run_in_executor(
                executor,
                generate_summary,
                transcription
            )
            
            # Paso 3: Actualizar BD con resultados
            await db_instance.db.sessions.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "transcription": transcription,
                        "summary": summary,
                        "status": "completed",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
        except Exception as e:
            # Guardar error en BD
            error_msg = f"Error procesando sesión: {str(e)}"
            await db_instance.db.sessions.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": error_msg,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
    
    @staticmethod
    async def list_sessions_by_room_id(room_id: str, requester_email: str, limit: int = 100) -> dict:
        """
        Lista todas las sesiones de una room con validación de acceso.
        
        Args:
            room_id: ID de MongoDB de la room
            requester_email: Email del solicitante
            limit: Cantidad máxima de sesiones a retornar
            
        Returns:
            dict: Información de sesiones
            
        Raises:
            ValueError: Si la room no existe o no hay acceso
        """
        # Verificar acceso
        room = await SessionService._verify_room_access(room_id, requester_email)
        
        # Obtener sesiones
        cursor = db_instance.db.sessions.find(
            {"room_id": room_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        sessions = await cursor.to_list(length=limit)
        
        return {
            "room_id": room_id,
            "room_name": room.get("name"),
            "total": len(sessions),
            "sessions": sessions
        }
    
    @staticmethod
    async def list_sessions_by_room_code(room_code: str, requester_email: str, limit: int = 100) -> dict:
        """
        Lista sesiones de una room usando su código en lugar de ID.
        
        Args:
            room_code: Código único de 5 caracteres
            requester_email: Email del solicitante
            limit: Cantidad máxima de sesiones
            
        Returns:
            dict: Información de sesiones
            
        Raises:
            ValueError: Si la room no existe o no hay acceso
        """
        # Verificar acceso por código
        room = await SessionService._verify_room_by_code(room_code, requester_email)
        
        # Obtener sesiones
        cursor = db_instance.db.sessions.find(
            {"room_code": room_code.upper()},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        sessions = await cursor.to_list(length=limit)
        
        return {
            "room_id": str(room.get("_id")),
            "room_code": room_code.upper(),
            "room_name": room.get("name"),
            "total": len(sessions),
            "sessions": sessions
        }
    
    @staticmethod
    async def get_session_status(room_id: str, session_id: str, requester_email: str) -> dict:
        """
        Obtiene el estado actual de una sesión.
        
        Args:
            room_id: ID de la room
            session_id: ID de la sesión
            requester_email: Email del solicitante
            
        Returns:
            dict: Estado de la sesión
            
        Raises:
            ValueError: Si la sesión no existe o no hay acceso
        """
        # Verificar acceso a la room
        await SessionService._verify_room_access(room_id, requester_email)
        
        # Obtener sesión
        session = await db_instance.db.sessions.find_one(
            {
                "session_id": session_id,
                "room_id": room_id
            },
            {"_id": 0}
        )
        
        if not session:
            raise ValueError(f"Sesión no encontrada: {session_id}")
        
        return {
            "session_id": session_id,
            "room_id": room_id,
            "name": session.get("name"),
            "status": session.get("status"),
            "visible": session.get("visible", True),
            "complementaryResourses": session.get("complementaryResourses"),
            "creator_email": session.get("creator_email"),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
            "progress": "En procesamiento..." if session.get("status") == "processing" else session.get("status")
        }
    
    @staticmethod
    async def get_session_details(room_id: str, session_id: str, requester_email: str) -> dict:
        """
        Obtiene detalles completos de una sesión.
        
        Args:
            room_id: ID de la room
            session_id: ID de la sesión
            requester_email: Email del solicitante
            
        Returns:
            dict: Detalles completos de la sesión
            
        Raises:
            ValueError: Si la sesión no existe o no hay acceso
        """
        # Verificar acceso
        await SessionService._verify_room_access(room_id, requester_email)
        
        # Obtener sesión
        session = await db_instance.db.sessions.find_one(
            {
                "session_id": session_id,
                "room_id": room_id
            },
            {"_id": 0}  # No incluir ruta interna del archivo
        )
        
        if not session:
            raise ValueError(f"Sesión no encontrada: {session_id}")
        
        # Si no tiene permiso de descarga, no mostrar ciertos datos
        if not session.get("allow_download", False):
            session["record_path"] = None
        
        return session

    @staticmethod
    async def update_complementary_resourses(
        room_id: str,
        session_id: str,
        request: UpdateComplementaryResoursesRequest
    ) -> dict:
        """
        Actualiza los recursos complementarios de una sesiÃ³n.

        Solo el propietario de la room puede modificar este campo.
        """
        room = await SessionService._verify_room_access(
            room_id,
            request.owner_email,
            require_owner=True
        )

        session = await db_instance.db.sessions.find_one(
            {
                "session_id": session_id,
                "room_id": room_id
            },
            {"_id": 0}
        )

        if not session:
            raise ValueError(f"SesiÃ³n no encontrada: {session_id}")

        updated_at = datetime.utcnow()
        await db_instance.db.sessions.update_one(
            {
                "session_id": session_id,
                "room_id": room_id
            },
            {
                "$set": {
                    "complementaryResourses": request.complementaryResourses,
                    "updated_at": updated_at
                }
            }
        )

        return {
            "session_id": session_id,
            "room_id": room_id,
            "room_name": room.get("name"),
            "complementaryResourses": request.complementaryResourses,
            "updated_at": updated_at,
            "message": "Recursos complementarios actualizados correctamente"
        }

    @staticmethod
    async def update_allow_download(
        room_id: str,
        session_id: str,
        request: UpdateAllowDownloadRequest
    ) -> dict:
        """Actualiza el permiso de descarga de una sesiÃ³n."""
        room, _ = await SessionService._verify_owner_and_get_session(
            room_id,
            session_id,
            request.owner_email
        )

        updated_at = datetime.utcnow()
        await db_instance.db.sessions.update_one(
            {
                "session_id": session_id,
                "room_id": room_id
            },
            {
                "$set": {
                    "allow_download": request.allow_download,
                    "updated_at": updated_at
                }
            }
        )

        return {
            "session_id": session_id,
            "room_id": room_id,
            "room_name": room.get("name"),
            "allow_download": request.allow_download,
            "updated_at": updated_at,
            "message": "Permiso de descarga actualizado correctamente"
        }

    @staticmethod
    async def update_visible(
        room_id: str,
        session_id: str,
        request: UpdateVisibleRequest
    ) -> dict:
        """Actualiza la visibilidad de una sesiÃ³n."""
        room, _ = await SessionService._verify_owner_and_get_session(
            room_id,
            session_id,
            request.owner_email
        )

        updated_at = datetime.utcnow()
        await db_instance.db.sessions.update_one(
            {
                "session_id": session_id,
                "room_id": room_id
            },
            {
                "$set": {
                    "visible": request.visible,
                    "updated_at": updated_at
                }
            }
        )

        return {
            "session_id": session_id,
            "room_id": room_id,
            "room_name": room.get("name"),
            "visible": request.visible,
            "updated_at": updated_at,
            "message": "Visibilidad actualizada correctamente"
        }

    @staticmethod
    async def delete_session(
        room_id: str,
        session_id: str,
        request: DeleteSessionRequest
    ) -> dict:
        """Elimina una sesiÃ³n y su archivo asociado si existe."""
        _, session = await SessionService._verify_owner_and_get_session(
            room_id,
            session_id,
            request.owner_email
        )

        record_path = session.get("record_path")
        file_deleted = False
        if record_path:
            path = Path(record_path)
            if path.exists() and path.is_file():
                path.unlink()
                file_deleted = True

        result = await db_instance.db.sessions.delete_one(
            {
                "session_id": session_id,
                "room_id": room_id
            }
        )

        return {
            "session_id": session_id,
            "room_id": room_id,
            "deleted_count": result.deleted_count,
            "file_deleted": file_deleted,
            "message": "SesiÃ³n eliminada correctamente"
        }
