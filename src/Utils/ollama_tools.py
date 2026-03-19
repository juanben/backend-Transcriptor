import math
import ollama

# --- CONFIGURACIÓN ---
OLLAMA_MODEL = "llama3.2"
CHUNK_LIMIT = 2000  # Límite de palabras para procesar de un solo golpe

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
            'temperature': 0.5,  # Baja para resúmenes precisos
        }
    )
    return response['message']['content']

def generate_summary(full_text: str) -> str:
    """
    Genera un resumen del texto usando Ollama.
    Si el texto es corto: resume directamente.
    Si es largo: divide en bloques, resume cada uno, luego consolida.
    """
    
    palabras = full_text.split()
    conteo_palabras = len(palabras)
    
    if conteo_palabras <= CHUNK_LIMIT:
        # PROCESO DIRECTO (Texto corto)
        prompt = f"Realiza un resumen detallado y estructurado del siguiente texto:\n\n{full_text}"
        resultado_final = call_ollama(prompt, "Eres un experto en síntesis.", context_size=int(conteo_palabras * 2.5))
    else:
        # PROCESO POR BLOQUES (Texto largo)
        num_chunks = math.ceil(conteo_palabras / CHUNK_LIMIT)
        
        summaries = []
        for i in range(num_chunks):
            start_idx = i * CHUNK_LIMIT
            end_idx = start_idx + CHUNK_LIMIT
            chunk_text = " ".join(palabras[start_idx:end_idx])
            
            chunk_prompt = f"Resume los puntos clave de este fragmento:\n\n{chunk_text}"
            summary = call_ollama(chunk_prompt, "Analista de contenido.")
            summaries.append(summary)
        
        # Consolidación Final
        final_prompt = f"Basado en estos resúmenes parciales, genera un informe final coherente y completo:\n\n" + "\n".join(summaries)
        resultado_final = call_ollama(final_prompt, "Redactor jefe experto.", context_size=8192)
    
    return resultado_final
