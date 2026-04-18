#main de fast API
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.Routes.Test.test import router as test_router
from src.Routes.Room.RoomRouter import router as room_router
from src.Routes.Session.SessionRouter import router as session_router
from src.Routes.User.UserRouter import router as user_router
from src.DB.motor import connect_to_mongo, close_mongo_connection
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="PWA Audio API")
app.mount("/Records", StaticFiles(directory="Records"), name="records")
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
app.include_router(room_router)
app.include_router(session_router)
app.include_router(user_router)
app.include_router(test_router)

@app.get("/")
async def root():
    return {"message": "API de Transcripción activa"}