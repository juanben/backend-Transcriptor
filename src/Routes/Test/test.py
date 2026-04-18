from fastapi import APIRouter, UploadFile, BackgroundTasks, HTTPException, status
from src.DB.motor import db_instance
from src.Utils.whisper_tools import transcribe_audio
from src.Utils.ollama_tools import generate_summary
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import logging
import time
import os

router = APIRouter(prefix="/test", tags=["Test"])

executor = ThreadPoolExecutor(max_workers=4)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


async def process_pipeline(job_id: str, file_path: str):
    """Procesa el audio: transcribe y resume"""
    total_start = time.perf_counter()
    loop = asyncio.get_running_loop()

    try:
        logger.info(f"[{job_id}] Inicio pipeline | archivo={file_path}")

        # 1. Transcribir
        t1 = time.perf_counter()
        texto = await loop.run_in_executor(executor, transcribe_audio, file_path)
        t2 = time.perf_counter()
        logger.info(f"[{job_id}] Transcripción completada en {t2 - t1:.2f}s")

        # 2. Resumir
        t3 = time.perf_counter()
        resumen = await loop.run_in_executor(executor, generate_summary, texto)
        t4 = time.perf_counter()
        logger.info(f"[{job_id}] Resumen completado en {t4 - t3:.2f}s")

        # 3. Guardar en MongoDB
        t5 = time.perf_counter()
        await db_instance.db.recordings.update_one(
            {"job_id": job_id},
            {"$set": {
                "transcription": texto,
                "summary": resumen,
                "status": "completed"
            }}
        )
        t6 = time.perf_counter()
        logger.info(f"[{job_id}] Actualización en Mongo completada en {t6 - t5:.2f}s")

        total_end = time.perf_counter()
        logger.info(f"[{job_id}] Pipeline completado en {total_end - total_start:.2f}s")

    except Exception as e:
        total_end = time.perf_counter()
        logger.exception(f"[{job_id}] Error en pipeline tras {total_end - total_start:.2f}s: {e}")

        await db_instance.db.recordings.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "failed",
                "error": str(e)
            }}
        )


@router.post("/upload")
async def start_session(file: UploadFile, background_tasks: BackgroundTasks):
    """Endpoint para subir un audio y procesarlo"""
    request_start = time.perf_counter()
    job_id = str(uuid.uuid4())

    suffix = Path(file.filename).suffix if file.filename else ".webm"
    Path("Records").mkdir(parents=True, exist_ok=True)
    temp_path = f"Records/{job_id}{suffix}"

    try:
        logger.info(f"[{job_id}] Inicio upload | filename={file.filename}")

        # Leer archivo
        t1 = time.perf_counter()
        content = await file.read()
        t2 = time.perf_counter()
        logger.info(f"[{job_id}] Lectura de archivo completada en {t2 - t1:.2f}s | bytes={len(content)}")

        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo está vacío"
            )

        # Guardar archivo
        t3 = time.perf_counter()
        with open(temp_path, "wb") as f:
            f.write(content)
        t4 = time.perf_counter()
        logger.info(f"[{job_id}] Archivo guardado en {t4 - t3:.2f}s | ruta={temp_path}")

        # Crear registro inicial en DB
        t5 = time.perf_counter()
        await db_instance.db.recordings.insert_one({
            "job_id": job_id,
            "status": "processing",
            "transcription": "",
            "summary": "",
            "file_path": temp_path
        })
        t6 = time.perf_counter()
        logger.info(f"[{job_id}] Registro Mongo inicial creado en {t6 - t5:.2f}s")

        # Lanzar proceso en background
        background_tasks.add_task(process_pipeline, job_id, temp_path)

        request_end = time.perf_counter()
        logger.info(f"[{job_id}] Request /upload respondido en {request_end - request_start:.2f}s")

        return {"job_id": job_id, "status": "processing"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[{job_id}] Error en /upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir archivo: {str(e)}"
        )


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Consulta el estado de un trabajo de transcripción por job_id"""
    t1 = time.perf_counter()
    job = await db_instance.db.recordings.find_one({"job_id": job_id}, {"_id": 0})
    t2 = time.perf_counter()

    logger.info(f"[{job_id}] Consulta de estado en {t2 - t1:.4f}s")

    if not job:
        return {"job_id": job_id, "status": "not_found"}

    return {
        "job_id": job_id,
        "status": job.get("status", "unknown"),
        "transcription": job.get("transcription", ""),
        "summary": job.get("summary", ""),
        "error": job.get("error", "")
    }