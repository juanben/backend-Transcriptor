from motor.motor_asyncio import AsyncIOMotorClient
import os

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None

db_instance = MongoDB()

async def connect_to_mongo():
    db_instance.client = AsyncIOMotorClient("mongodb://localhost:27017")
    db_instance.db = db_instance.client.pwa_recordings_db

async def close_mongo_connection():
    db_instance.client.close()