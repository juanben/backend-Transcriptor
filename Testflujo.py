import time
import math
from faster_whisper import WhisperModel
import ollama

# --- CONFIGURACIÓN ---
AUDIO_PATH = "la-fascinante-y-misteriosa-historia-de-mega-man-legends.mp3"
WHISPER_MODEL_SIZE = "base"
OLLAMA_MODEL = "llama3.2"

# Límite de palabras para procesar de un solo golpe (seguridad de contexto)
CHUNK_LIMIT = 2000 

def call_ollama(prompt, system_role, context_size=4096):
    """Función auxiliar para llamadas limpias a Ollama"""
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {'role': 'system', 'content': system_role},
            {'role': 'user', 'content': prompt},
        ],
        options={
            'num_ctx': context_size,
            'temperature': 0.5, # Baja para resúmenes precisos
        }
    )
    return response['message']['content']

def run_full_pipeline():
    # --- PASO 1: TRANSCRIPCIÓN ---
    print("🚀 PASO 1: Cargando Whisper...")
    whisper = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    
    print(f"🎙️ Transcribiendo audio: {AUDIO_PATH}...")
    start_whisper = time.time()
    
    segments, info = whisper.transcribe(AUDIO_PATH, beam_size=5)
    full_text = " ".join([s.text for s in segments])
    
    end_whisper = time.time()
    print(f"✅ Transcripción completada en {end_whisper - start_whisper:.2f}s")
    
    # Métricas de texto
    palabras = full_text.split()
    conteo_palabras = len(palabras)
    print(f"📊 Texto detectado: {conteo_palabras} palabras.")
    print(f"--- Final del texto ---\n...{full_text[-200:]}\n")

    # --- PASO 2: RESUMEN ADAPTATIVO ---
    print(f"🧠 PASO 2: Procesando con {OLLAMA_MODEL}...")
    start_ollama = time.time()

    if conteo_palabras <= CHUNK_LIMIT:
        # PROCESO DIRECTO (Audio corto)
        print("⚡ Procesando como bloque único...")
        prompt = f"Realiza un resumen detallado y estructurado del siguiente texto:\n\n{full_text}"
        resultado_final = call_ollama(prompt, "Eres un experto en síntesis.", contexto_size=int(conteo_palabras * 2.5))
    else:
        # PROCESO POR BLOQUES (Audio largo / 2 horas)
        num_chunks = math.ceil(conteo_palabras / CHUNK_LIMIT)
        print(f"📦 Texto largo detectado. Dividiendo en {num_chunks} bloques...")
        
        summaries = []
        for i in range(num_chunks):
            start_idx = i * CHUNK_LIMIT
            end_idx = start_idx + CHUNK_LIMIT
            chunk_text = " ".join(palabras[start_idx:end_idx])
            
            print(f"   > Analizando bloque {i+1}/{num_chunks}...")
            chunk_prompt = f"Resume los puntos clave de este fragmento:\n\n{chunk_text}"
            summary = call_ollama(chunk_prompt, "Analista de contenido.")
            summaries.append(summary)
        
        # Consolidación Final
        print("🎓 Consolidando todos los bloques en un resumen final...")
        final_prompt = f"Basado en estos resúmenes parciales, genera un informe final coherente y completo:\n\n" + "\n".join(summaries)
        resultado_final = call_ollama(final_prompt, "Redactor jefe experto.", context_size=8192)

    end_ollama = time.time()
    
    print("\n" + "="*40)
    print("📝 REPORTE GENERADO:")
    print(resultado_final)
    print("="*40)
    
    # --- MÉTRICAS FINALES ---
    print(f"\n⏱️ TIEMPOS TOTALES:")
    print(f"- Whisper: {end_whisper - start_whisper:.2f}s")
    print(f"- Ollama:  {end_ollama - start_ollama:.2f}s")
    print(f"- Total:   {end_ollama - start_whisper:.2f}s")

if __name__ == "__main__":
    run_full_pipeline()