#main de fast API
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.Routes.Room.RoomRouter import router as session_router
from src.Routes.User.UserRouter import router as user_router
from src.DB.motor import connect_to_mongo, close_mongo_connection

app = FastAPI(title="PWA Audio API")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Eventos de inicio y fin
@app.on_event("startup")
async def startup_db_client():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongo_connection()

# Incluir rutas
app.include_router(session_router)
app.include_router(user_router)

@app.get("/")
async def root():
    return {"message": "API de Transcripción activa"}