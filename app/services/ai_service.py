import os
import json
from openai import OpenAI

from app.core.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------
# 🎤 TRANSCRIBIR AUDIO
# ---------------------------
def transcribe_audio(file_path: str) -> str:
    try:
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        return transcript.text

    except Exception as e:
        print("Error transcribing audio:", e)
        return ""


# ---------------------------
# 🧠 ANALIZAR TRANSCRIPCIÓN
# ---------------------------
def analyze_transcript(transcript: str):

    if not transcript:
        return {
            "summary": "",
            "topics": [],
            "tasks": [],
            "decisions": [],
            "questions": []
        }

    prompt = f"""
Analiza esta reunión y devuelve SOLO JSON válido:

{{
  "summary": "resumen claro y corto",
  "topics": ["temas principales"],
  "tasks": [
    {{
      "task": "acción concreta",
      "owner": "persona o 'sin asignar'",
      "due_date": "YYYY-MM-DD o null",
      "priority": "alta/media/baja",
      "status": "pending"
    }}
  ],
  "decisions": ["decisiones tomadas"],
  "questions": ["preguntas abiertas"]
}}

Reglas:
- No inventar información
- Extraer SOLO tareas reales
- Si no hay responsable → "sin asignar"
- Si no hay fecha → null
- Prioridad según contexto
- Responder SOLO JSON (sin texto extra)

Texto:
\"\"\"{transcript}\"\"\"
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un analista experto en reuniones."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        content = response.choices[0].message.content

        # Intentar parsear JSON
        try:
            return json.loads(content)
        except:
            print("Error parsing JSON, raw response:", content)
            return {
                "summary": content,
                "topics": [],
                "tasks": [],
                "decisions": [],
                "questions": []
            }

    except Exception as e:
        print("Error analyzing transcript:", e)
        return {
            "summary": "",
            "topics": [],
            "tasks": [],
            "decisions": [],
            "questions": []
        }


# ---------------------------
# 🔁 PIPELINE COMPLETO
# ---------------------------
def process_audio(file_path: str):

    transcript = transcribe_audio(file_path)

    analysis = analyze_transcript(transcript)

    return {
        "transcript": transcript,
        "analysis": analysis
    }