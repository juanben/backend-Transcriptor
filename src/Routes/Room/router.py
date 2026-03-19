from fastapi import APIRouter, UploadFile, BackgroundTasks
from src.DB.motor import db_instance
from src.Utils.whisper_tools import transcribe_audio
from src.Utils.ollama_tools import generate_summary
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/session", tags=["Session"])

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

@router.post("/user")
async def create_user(user: dict):
    """Crea un usuario en colección 'users' con nombre, correo y password"""
    # Validaciones básicas
    required = ["name", "email", "password"]
    for field in required:
        if field not in user or not str(user[field]).strip():
            return {"error": f"'{field}' es requerido"}

    existing = await db_instance.db.users.find_one({"email": user["email"].lower()})
    if existing:
        return {"error": "El correo ya está registrado"}

    new_user = {
        "name": user["name"].strip(),
        "email": user["email"].strip().lower(),
        "password": user["password"],  # En producción hashear la contraseña
        "created_at": __import__('datetime').datetime.utcnow()
    }

    result = await db_instance.db.users.insert_one(new_user)

    return {"user_id": str(result.inserted_id), "name": new_user["name"], "email": new_user["email"]}

