"""
EJEMPLOS DE USO - Servicios de Session
Este archivo contiene ejemplos de cómo usar los endpoints de sesiones
con curl, Python requests, o Postman.

Para probar: La API corre en http://localhost:8000
Documentación interactiva: http://localhost:8000/docs (Swagger)
"""

# ============================================================================
# SETUP
# ============================================================================
# Variables de ejemplo:
ROOM_ID = "507f1f77bcf86cd799439011"  # Replace with real MongoDB ObjectId
ROOM_CODE = "X7B9P"  # Replace with real room code
SESSION_ID = "550e8400-e29b-41d4-a716-446655440000"  # Replace with real UUID
USER_EMAIL = "user@example.com"
OWNER_EMAIL = "owner@example.com"


# ============================================================================
# 1. CREAR SESIÓN
# ============================================================================

# Con curl:
"""
curl -X POST "http://localhost:8000/sessions/{room_id}/create" \
  -F "file=@recording.webm" \
  -F "session_name=Mi Sesión" \
  -F "creator_email=owner@example.com" \
  -F "allow_download=true"
"""

# Con Python requests:
"""
import requests

url = f'http://localhost:8000/sessions/{ROOM_ID}/create'
files = {'file': open('recording.webm', 'rb')}
data = {
    'session_name': 'Mi Sesión',
    'creator_email': OWNER_EMAIL,
    'allow_download': True
}

response = requests.post(url, files=files, data=data)
result = response.json()
print(f"Session ID: {result['session_id']}")
print(f"Status: {result['status']}")  # "processing"
"""

# Con httpx (async):
"""
import httpx

async with httpx.AsyncClient() as client:
    with open('recording.webm', 'rb') as f:
        files = {'file': f}
        data = {
            'session_name': 'Mi Sesión',
            'creator_email': OWNER_EMAIL
        }
        
        response = await client.post(
            f'http://localhost:8000/sessions/{ROOM_ID}/create',
            files=files,
            data=data
        )
        print(response.json())
"""

# Respuesta exitosa (201 Created):
"""
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "room_id": "507f1f77bcf86cd799439011",
  "name": "Mi Sesión",
  "status": "processing",
  "message": "Sesión creada. El procesamiento se ejecutará en background"
}
"""

# Errores posibles:
"""
400 Bad Request:
{
  "detail": "El archivo está vacío"
}

400 Bad Request:
{
  "detail": "El archivo es demasiado grande (máximo 100MB)"
}

403 Forbidden:
{
  "detail": "Solo el propietario de la room puede crear sesiones"
}

404 Not Found:
{
  "detail": "Room no encontrada"
}
"""


# ============================================================================
# 2. LISTAR SESIONES POR ROOM_ID
# ============================================================================

# Con curl:
"""
curl -X GET "http://localhost:8000/sessions/{room_id}/list?requester_email=user@example.com&limit=50"
"""

# Con Python:
"""
import requests

url = f'http://localhost:8000/sessions/{ROOM_ID}/list'
params = {
    'requester_email': USER_EMAIL,
    'limit': 50
}

response = requests.get(url, params=params)
result = response.json()
print(f"Total sessions: {result['total']}")
for session in result['sessions']:
    print(f"  - {session['name']} ({session['status']})")
"""

# Respuesta exitosa (200 OK):
"""
{
  "room_id": "507f1f77bcf86cd799439011",
  "room_name": "Mi Sala de Grabaciones",
  "total": 3,
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "room_id": "507f1f77bcf86cd799439011",
      "name": "Reunión del 14/4",
      "creator_email": "owner@example.com",
      "status": "completed",
      "transcription": "Buenos días a todos...",
      "summary": "Se discutió sobre...",
      "created_at": "2026-04-14T10:30:00.000000",
      "allow_download": true
    },
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440001",
      "room_id": "507f1f77bcf86cd799439011",
      "name": "Brainstorm",
      "creator_email": "owner@example.com",
      "status": "processing",
      "transcription": "",
      "summary": "",
      "created_at": "2026-04-14T11:45:00.000000",
      "allow_download": false
    }
  ]
}
"""

# Errores posibles:
"""
403 Forbidden:
{
  "detail": "No tienes acceso a esta room"
}

404 Not Found:
{
  "detail": "Room no encontrada"
}
"""


# ============================================================================
# 3. LISTAR SESIONES POR ROOM CODE
# ============================================================================

# Con curl:
"""
curl -X GET "http://localhost:8000/sessions/by-code/list?room_code=X7B9P&requester_email=user@example.com&limit=50"
"""

# Con Python:
"""
import requests

url = 'http://localhost:8000/sessions/by-code/list'
params = {
    'room_code': ROOM_CODE,
    'requester_email': USER_EMAIL,
    'limit': 50
}

response = requests.get(url, params=params)
result = response.json()
print(f"Room: {result['room_name']} ({result['room_code']})")
print(f"Total sessions: {result['total']}")
"""

# Ventaja: Puedes compartir solo el código en lugar del ID


# ============================================================================
# 4. OBTENER ESTADO DE SESIÓN (POLLING)
# ============================================================================

# Con curl:
"""
curl -X GET "http://localhost:8000/sessions/{room_id}/{session_id}/status?requester_email=user@example.com"
"""

# Con Python (con polling):
"""
import time
import requests

url = f'http://localhost:8000/sessions/{ROOM_ID}/{SESSION_ID}/status'
params = {'requester_email': USER_EMAIL}

# Polling hasta completar
max_attempts = 60
for attempt in range(max_attempts):
    response = requests.get(url, params=params)
    status_data = response.json()
    
    print(f"Attempt {attempt+1}: {status_data['status']}")
    
    if status_data['status'] in ['completed', 'failed']:
        break
    
    time.sleep(2)  # Esperar 2 segundos antes de re-intentar

print(f"Final status: {status_data['status']}")
"""

# Respuesta mientras procesa:
"""
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "room_id": "507f1f77bcf86cd799439011",
  "name": "Reunión del 14/4",
  "status": "processing",
  "creator_email": "owner@example.com",
  "created_at": "2026-04-14T10:30:00.000000",
  "updated_at": "2026-04-14T10:30:15.000000",
  "progress": "En procesamiento..."
}
"""

# Respuesta final completada:
"""
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "room_id": "507f1f77bcf86cd799439011",
  "name": "Reunión del 14/4",
  "status": "completed",
  "creator_email": "owner@example.com",
  "created_at": "2026-04-14T10:30:00.000000",
  "updated_at": "2026-04-14T10:32:45.000000",
  "progress": "completed"
}
"""


# ============================================================================
# 5. OBTENER DETALLES COMPLETOS DE SESIÓN
# ============================================================================

# Con curl:
"""
curl -X GET "http://localhost:8000/sessions/{room_id}/{session_id}/details?requester_email=user@example.com"
"""

# Con Python:
"""
import requests

url = f'http://localhost:8000/sessions/{ROOM_ID}/{SESSION_ID}/details'
params = {'requester_email': USER_EMAIL}

response = requests.get(url, params=params)
result = response.json()

print(f"Sesión: {result['name']}")
print(f"Estado: {result['status']}")
print(f"\\nTranscripción:\\n{result['transcription']}")
print(f"\\nResumen:\\n{result['summary']}")
"""

# Respuesta completa:
"""
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "room_id": "507f1f77bcf86cd799439011",
  "room_code": "X7B9P",
  "name": "Reunión del 14/4",
  "creator_email": "owner@example.com",
  "status": "completed",
  "transcription": "Buenos días a todos. Hoy vamos a discutir los resultados del trimestre...",
  "summary": "Reunión enfocada en resultados trimestrales. Puntos clave:\\n- Ventas aumentaron 15%\\n- Proyectos nueva línea iniciaron\\n- Se necesita mejorar servicio al cliente",
  "allow_download": true,
  "created_at": "2026-04-14T10:30:00.000000",
  "updated_at": "2026-04-14T10:32:45.000000"
}
"""


# ============================================================================
# FLOW COMPLETO - EJEMPLO
# ============================================================================

"""
import requests
import time

BASE_URL = 'http://localhost:8000'
ROOM_ID = '507f1f77bcf86cd799439011'
OWNER_EMAIL = 'owner@example.com'

# Paso 1: Crear sesión con archivo
print("1. Creando sesión...")
with open('recording.webm', 'rb') as f:
    response = requests.post(
        f'{BASE_URL}/sessions/{ROOM_ID}/create',
        files={'file': f},
        data={
            'session_name': 'Video de presentación',
            'creator_email': OWNER_EMAIL
        }
    )

session_data = response.json()
session_id = session_data['session_id']
print(f"   Session ID: {session_id}")
print(f"   Status: {session_data['status']}")

# Paso 2: Esperar a que termine el procesamiento
print("\\n2. Esperando procesamiento...")
max_wait = 120  # 2 minutos máximo
start_time = time.time()

while time.time() - start_time < max_wait:
    response = requests.get(
        f'{BASE_URL}/sessions/{ROOM_ID}/{session_id}/status',
        params={'requester_email': OWNER_EMAIL}
    )
    
    status_info = response.json()
    current_status = status_info['status']
    
    print(f"   Status: {current_status}")
    
    if current_status in ['completed', 'failed']:
        break
    
    time.sleep(2)

# Paso 3: Obtener detalles completos
print("\\n3. Obteniendo detalles...")
response = requests.get(
    f'{BASE_URL}/sessions/{ROOM_ID}/{session_id}/details',
    params={'requester_email': OWNER_EMAIL}
)

details = response.json()
print(f"   Nombre: {details['name']}")
print(f"   Estado: {details['status']}")
print(f"   Transcripción: {details['transcription'][:100]}...")
print(f"   Resumen: {details['summary'][:100]}...")

# Paso 4: Listar todas las sesiones de la room
print("\\n4. Listando sesiones de la room...")
response = requests.get(
    f'{BASE_URL}/sessions/{ROOM_ID}/list',
    params={'requester_email': OWNER_EMAIL, 'limit': 10}
)

list_data = response.json()
print(f"   Total sesiones: {list_data['total']}")
for session in list_data['sessions']:
    print(f"   - {session['name']} ({session['status']})")
"""


# ============================================================================
# DEBUGGING Y TROUBLESHOOTING
# ============================================================================

"""
Si recibés error 404 "Room no encontrada":
- Verifica que el room_id sea un ObjectId válido de MongoDB
- Asegúrate de que la room existe en la BD

Si recibís error 403 "Sin permisos":
- Solo el propietario puede crear sesiones
- El email debe coincidir con owner_email de la room

Si el procesamiento se queda en "processing":
- Revisa los logs del servidor
- Verifica que whisper_tools y ollama_tools funcionan correctamente
- Chequea que los archivos se guardaron correctamente en Records/

Para ver logs en vivo:
- Terminal: tail -f backend-Transcriptor.log
- (Opcional: implementar logging module)

Para testear sin audio real:
- Crea un archivo webm vacío o pequeño para pruebas rápidas
- Usa un archivo de prueba conocido con transcripción esperada
"""
