import time
from faster_whisper import WhisperModel

# --- CONFIGURACIÓN ---
# Opciones: "tiny", "base", "small", "medium", "large-v3"
# 'base' o 'small' suelen ser los mejores para servidores sin mucha GPU
MODEL_SIZE = "base" 
AUDIO_FILE = "audio_prueba1hora.mp3" # Cambia esto por un audio real

def run_benchmark():
    print(f"--- Iniciando prueba con modelo: {MODEL_SIZE} ---")
    
    # 1. Medir tiempo de carga del modelo (solo ocurre una vez al inicio)
    start_load = time.time()
    # Usamos 'cpu' y 'int8' para máxima velocidad en servidores comunes
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    print(f"Carga del modelo: {time.time() - start_load:.2f} segundos")

    # 2. Medir tiempo de transcripción
    start_transcribe = time.time()
    segments, info = model.transcribe(AUDIO_FILE, beam_size=5)
    
    # Consumir el generador para forzar la transcripción completa
    full_text = ""
    for segment in segments:
        full_text += segment.text + " "
        print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")

    end_transcribe = time.time()
    
    print("\n--- RESULTADOS ---")
    print(f"Duración del audio: {info.duration:.2f} segundos")
    print(f"Tiempo de transcripción: {end_transcribe - start_transcribe:.2f} segundos")
    print(f"Factor de velocidad: {info.duration / (end_transcribe - start_transcribe):.2f}x (Tiempo real / Tiempo proceso)")

if __name__ == "__main__":
    run_benchmark()