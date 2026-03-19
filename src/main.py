#main de fast API
from fastapi import FastAPI
from src.Routes.Room.router import router as session_router
from src.DB.motor import connect_to_mongo, close_mongo_connection

app = FastAPI(title="PWA Audio API")

# Eventos de inicio y fin
@app.on_event("startup")
async def startup_db_client():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongo_connection()

# Incluir rutas
app.include_router(session_router)

@app.get("/")
async def root():
    return {"message": "API de Transcripción activa"}