from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")

def transcribe_audio(file_path: str):
    segments, _ = model.transcribe(file_path, beam_size=5)
    return " ".join([s.text for s in segments])