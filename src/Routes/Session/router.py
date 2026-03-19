from fastapi import APIRouter, UploadFile, BackgroundTasks
from src.DB.motor import db_instance
from src.Utils.whisper_tools import transcribe_audio
from src.Utils.ollama_tools import generate_summary # Tu lógica de bloques
import uuid

router = APIRouter(prefix="/session", tags=["Session"])

async def process_pipeline(job_id: str, file_path: str):
    # 1. Transcribir
    texto = transcribe_audio(file_path)
    # 2. Resumir (Lógica de bloques)
    resumen = generate_summary(texto)
    
    # 3. Guardar en MongoDB
    await db_instance.db.recordings.update_one(
        {"job_id": job_id},
        {"$set": {
            "transcription": texto,
            "summary": resumen,
            "status": "completed"
        }}
    )

@app.post("/upload")
async def start_session(file: UploadFile, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    temp_path = f"records/{job_id}.webm"
    
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