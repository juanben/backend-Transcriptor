"""
SETUP MONGODB - Índices y estructura recomendada
Archivo para inicializar la base de datos con los índices necesarios
"""

# ============================================================================
# SHELL DE MONGODB - Comandos para ejecutar
# ============================================================================

# Conectarse a MongoDB:
# mongosh "mongodb://localhost:27017"

# Seleccionar la base de datos:
# use pwa_recordings_db

# CREAR ÍNDICES PARA COLECCIÓN 'sessions'
# ============================================================================

db.sessions.createIndex({ "session_id": 1 }, { unique: true })
db.sessions.createIndex({ "room_id": 1, "created_at": -1 })
db.sessions.createIndex({ "room_code": 1, "created_at": -1 })
db.sessions.createIndex({ "creator_email": 1 })
db.sessions.createIndex({ "status": 1 })

# Índice compuesto para búsquedas típicas:
# db.sessions.find({ "room_id": "...", "status": "completed" })
db.sessions.createIndex({ "room_id": 1, "status": 1 })

# CREAR ÍNDICES PARA COLECCIÓN 'rooms'
# ============================================================================

db.rooms.createIndex({ "room_code": 1 }, { unique: true })
db.rooms.createIndex({ "owner_email": 1 })
db.rooms.createIndex({ "members": 1 })
db.rooms.createIndex({ "created_at": -1 })

# Índice compuesto para búsquedas por estado y dueño:
db.rooms.createIndex({ "owner_email": 1, "created_at": -1 })


# ============================================================================
# ESTRUCTURA DE DOCUMENTOS
# ============================================================================

# COLECCIÓN: sessions
"""
{
  "_id": ObjectId("..."),
  "session_id": "550e8400-e29b-41d4-a716-446655440000",  // UUID único
  "room_id": "ObjectId_string",                           // Referencia a room
  "room_code": "X7B9P",                                   // Código de acceso rápido
  "name": "Reunión del 14/4",
  "creator_email": "owner@example.com",
  "allow_download": true,
  "record_path": "Records/507f1f77bcf86cd799439011/550e8400.webm",
  "status": "completed",  // pending, processing, completed, failed
  "transcription": "Buenos días a todos...",
  "summary": "Se discutió sobre...",
  "created_at": ISODate("2026-04-14T10:30:00.000Z"),
  "updated_at": ISODate("2026-04-14T10:32:45.000Z"),
  "error_message": null
}
"""

# COLECCIÓN: rooms
"""
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "name": "Mi Sala de Grabaciones",
  "owner_email": "owner@example.com",
  "room_code": "X7B9P",
  "is_public": false,
  "allow_download": true,
  "created_at": ISODate("2026-04-14T09:00:00.000Z"),
  "members": ["owner@example.com", "user2@example.com"],
  "waitlist": []
}
"""


# ============================================================================
# SCRIPT PYTHON PARA SETUP INICIAL
# ============================================================================

"""
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "pwa_recordings_db"

async def setup_indexes():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Crear índices para sessions
    await db.sessions.create_index("session_id", unique=True)
    await db.sessions.create_index([("room_id", 1), ("created_at", -1)])
    await db.sessions.create_index([("room_code", 1), ("created_at", -1)])
    await db.sessions.create_index("creator_email")
    await db.sessions.create_index("status")
    await db.sessions.create_index([("room_id", 1), ("status", 1)])
    
    # Crear índices para rooms
    await db.rooms.create_index("room_code", unique=True)
    await db.rooms.create_index("owner_email")
    await db.rooms.create_index("members")
    await db.rooms.create_index("created_at")
    await db.rooms.create_index([("owner_email", 1), ("created_at", -1)])
    
    print("✓ Índices creados exitosamente")
    client.close()

if __name__ == "__main__":
    asyncio.run(setup_indexes())
"""


# ============================================================================
# QUERIES COMUNES OPTIMIZADAS POR ÍNDICES
# ============================================================================

# ListAr sesiones de una room ordenadas por fecha (USA: room_id, created_at)
db.sessions.find({ room_id: "..." }).sort({ created_at: -1 }).limit(100)

# Buscar sesión específica (USA: session_id único)
db.sessions.findOne({ session_id: "550e8400-..." })

# Buscar sesiones por código (USA: room_code, created_at)
db.sessions.find({ room_code: "X7B9P" }).sort({ created_at: -1 })

# Buscar sesiones completadas de una room (USA: room_id, status)
db.sessions.find({ room_id: "...", status: "completed" })

# Obtener todas las rooms de un usuario (USA: owner_email)
db.rooms.find({ owner_email: "user@example.com" })


# ============================================================================
# MONITOREO DE PERFORMANCE
# ============================================================================

# Ver información de índices:
db.sessions.getIndexes()

# Ver estadísticas de colección:
db.sessions.stats()

# Explicar ejecución de query:
db.sessions.find({ room_id: "..." }).explain("executionStats")

# Resultado esperado: "executionStage": "IXSCAN" (indica que usa índice)
#                    "totalDocsExamined": igual a "nReturned" (bueno)

# Si ve "COLLSCAN": la query está escaneando toda la colección (malo)


# ============================================================================
# LIMPIEZA Y MANTENIMIENTO
# ============================================================================

# Borrar sesiones fallidas antiguas (más de 30 días):
db.sessions.deleteMany({
  status: "failed",
  created_at: { $lt: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000) }
})

# Borrar archivos de sesiones completadas sin descargas:
db.sessions.deleteMany({
  allow_download: false,
  status: "completed",
  created_at: { $lt: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000) }
})

# Agregar un campo a todas las sesiones (migración):
db.sessions.updateMany(
  {},
  { $set: { "processed_at": new Date() } }
)


# ============================================================================
# BACKUP Y RESTORE
# ============================================================================

"""
Backup:
mongodump --uri="mongodb://localhost:27017/pwa_recordings_db" --out=./backup

Restore:
mongorestore --uri="mongodb://localhost:27017/pwa_recordings_db" ./backup/pwa_recordings_db
"""


# ============================================================================
# RECOMENDACIONES DE SHARDING (para producción a gran escala)
# ============================================================================

"""
Si el volumen crece mucho:

Shard key recomendado para sessions:
db.sessions.createIndex({ "room_code": 1, "_id": 1 })

Para rooms:
db.rooms.createIndex({ "owner_email": 1, "_id": 1 })

Beneficios:
- Distribuye datos entre múltiples servidores
- Mejora performance en lectura/escritura
- Evita que una colección sea demasiado grande
"""
