from fastapi import APIRouter, UploadFile, BackgroundTasks
from src.DB.motor import db_instance
from src.Utils.whisper_tools import transcribe_audio
from src.Utils.ollama_tools import generate_summary
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/room", tags=["Room"])

# Executor para correr tareas sincrónicas en background sin bloquear
executor = ThreadPoolExecutor(max_workers=4)

async def process_pipeline(job_id: str, file_path: str):
    """Procesa el audio: transcribe y resume"""
    # 1. Transcribir (corre en thread pool para no bloquear)
    loop = asyncio.get_event_loop()
    texto = await loop.run_in_executor(executor, transcribe_audio, file_path)
    
    # 2. Resumir (corre en thread pool para no bloquear)
    resumen = await loop.run_in_executor(executor, generate_summary, texto)
    
    # 3. Guardar en MongoDB
    await db_instance.db.recordings.update_one(
        {"job_id": job_id},
        {"$set": {
            "transcription": texto,
            "summary": resumen,
            "status": "completed"
        }}
    )

@router.post("/upload")
async def start_session(file: UploadFile, background_tasks: BackgroundTasks):
    """Endpoint para subir un audio y procesarlo"""
    job_id = str(uuid.uuid4())
    temp_path = f"Records/{job_id}.webm"
    
    # Guardar archivo
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    # Crear registro inicial en DB
    await db_instance.db.recordings.insert_one({
        "job_id": job_id,
        "status": "processing",
        "transcription": "",
        "summary": ""
    })
    
    # Lanzar proceso en background
    background_tasks.add_task(process_pipeline, job_id, temp_path)
    
    return {"job_id": job_id, "status": "processing"}

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Consulta el estado de un trabajo de transcripción por job_id"""
    job = await db_instance.db.recordings.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        return {"job_id": job_id, "status": "not_found"}

    # Devolver solo la información de estado + transcripción/resumen cuando esté completa
    return {
        "job_id": job_id,
        "status": job.get("status", "unknown"),
        "transcription": job.get("transcription", ""),
        "summary": job.get("summary", "")
    }

@router.post("/createRoom")
async def create_room(payload: dict):
    """Crea una room con el usuario dueño"""
    required = ["name", "owner_email"]
    for field in required:
        if field not in payload or not str(payload[field]).strip():
            return {"error": f"'{field}' es requerido"}

    room_doc = {
        "name": payload["name"].strip(),
        "owner_email": payload["owner_email"].strip().lower(),
        "is_public": bool(payload.get("is_public", False)),
        "allow_download": bool(payload.get("allow_download", False)),
        "created_at": __import__('datetime').datetime.utcnow(),
        "members": [payload["owner_email"].strip().lower()]
    }
    
    result = await db_instance.db.rooms.insert_one(room_doc)
    
    # --- LA CORRECCIÓN AQUÍ ---
    # MongoDB agrega el campo _id al diccionario 'room_doc' automáticamente
    # Necesitamos convertirlo a string para que FastAPI pueda serializarlo a JSON
    room_doc["_id"] = str(room_doc["_id"]) 
    
    return {"room_id": str(result.inserted_id), "room": room_doc}

@router.post("/room/{room_id}/join")
async def join_room(room_id: str, payload: dict):
    """Un usuario se une a una room"""
    user_email = payload.get("user_email")
    if not user_email:
        return {"error": "'user_email' es requerido"}

    room = await db_instance.db.rooms.find_one({"_id": __import__('bson').ObjectId(room_id)})
    if not room:
        return {"error": "Room no encontrada"}

    user_email = user_email.strip().lower()
    if user_email not in room.get("members", []):
        await db_instance.db.rooms.update_one(
            {"_id": room["_id"]},
            {"$push": {"members": user_email}}
        )

    return {"room_id": room_id, "joined": True, "members": room.get("members", []) + [user_email]}

from pathlib import Path

async def process_room_session(session_id: str, file_path: str):
    """Processa la session de room (transcribe+resume y actualiza el documento)"""
    loop = asyncio.get_event_loop()
    texto = await loop.run_in_executor(executor, transcribe_audio, file_path)
    resumen = await loop.run_in_executor(executor, generate_summary, texto)

    await db_instance.db.sessions.update_one(
        {"session_id": session_id},
        {"$set": {
            "transcription": texto,
            "summary": resumen,
            "status": "completed"
        }}
    )

@router.post("/room/{room_id}/session")
async def create_room_session(room_id: str, file: UploadFile, session_name: str, creator_email: str, background_tasks: BackgroundTasks, allow_download: bool = None):
    """Crea una session en una room (sube audio)"""
    room = await db_instance.db.rooms.find_one({"_id": __import__('bson').ObjectId(room_id)})
    if not room:
        return {"error": "Room no encontrada"}

    if room["owner_email"] != creator_email.strip().lower():
        return {"error": "Solo el propietario puede crear sesiones"}

    session_id = str(uuid.uuid4())
    path_dir = Path("Records") / room_id
    path_dir.mkdir(parents=True, exist_ok=True)
    temp_path = path_dir / f"{session_id}.webm"

    with open(temp_path, "wb") as f:
        f.write(await file.read())

    session_doc = {
        "session_id": session_id,
        "room_id": room_id,
        "name": session_name,
        "creator_email": creator_email.strip().lower(),
        "allow_download": room.get("allow_download", False) if allow_download is None else bool(allow_download),
        "record_path": str(temp_path),
        "status": "processing",
        "transcription": "",
        "summary": "",
        "created_at": __import__('datetime').datetime.utcnow()
    }

    await db_instance.db.sessions.insert_one(session_doc)
    background_tasks.add_task(process_room_session, session_id, str(temp_path))

    return {"session_id": session_id, "status": "processing"}

@router.get("/room/{room_id}/session/{session_id}")
async def get_room_session(room_id: str, session_id: str, requester_email: str):
    """Retorna datos de la session si el acceso está permitido"""
    room = await db_instance.db.rooms.find_one({"_id": __import__('bson').ObjectId(room_id)})
    if not room:
        return {"error": "Room no encontrada"}

    session = await db_instance.db.sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not session or session.get("room_id") != room_id:
        return {"error": "Session no encontrada"}

    requester_email = requester_email.strip().lower()
    if not room.get("is_public", False) and requester_email != room.get("owner_email"):
        return {"error": "Acceso denegado: session privada"}

    return {
        "room": room["name"],
        "session": session
    }

@router.get("/room/{room_id}/sessions")
async def list_room_sessions(room_id: str, requester_email: str):
    """Lista todas las sessions de una room con filtro de acceso"""
    room = await db_instance.db.rooms.find_one({"_id": __import__('bson').ObjectId(room_id)})
    if not room:
        return {"error": "Room no encontrada"}

    requester_email = requester_email.strip().lower()
    if not room.get("is_public", False) and requester_email != room.get("owner_email"):
        return {"error": "Acceso denegado: room privada"}

    cursor = db_instance.db.sessions.find({"room_id": room_id}, {"_id": 0})
    sesiones = await cursor.to_list(length=100)
    return {"room": room_id, "sessions": sesiones}

