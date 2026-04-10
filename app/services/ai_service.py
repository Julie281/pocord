import json
from typing import Any

from mistralai.client import Mistral

from app.core.config import MISTRAL_API_KEY

if not MISTRAL_API_KEY:
    raise RuntimeError("Falta MISTRAL_API_KEY en variables de entorno")

client = Mistral(api_key=MISTRAL_API_KEY)


def transcribe_audio(file_path: str) -> str:
    """
    Transcribe un archivo de audio usando Mistral Audio Transcriptions.
    Modelo recomendado en docs: voxtral-mini-latest.
    """
    try:
        file_name = file_path.split("/")[-1]

        with open(file_path, "rb") as f:
            response = client.audio.transcriptions.complete(
                model="voxtral-small-latest",
                file={
                    "content": f,
                    "file_name": file_name,
                },
                # opcionales:
                # language="es",
                # diarize=False,
                # timestamp_granularities=["segment"],
            )

        # El SDK puede devolver objeto con distintos shapes según versión.
        text = None

        if hasattr(response, "text"):
            text = response.text
        elif isinstance(response, dict):
            text = response.get("text")
        else:
            # último intento razonable
            text = getattr(response, "transcript", None)

        if not text:
            raise ValueError(f"Respuesta de transcripción sin texto: {response}")

        return text.strip()

    except Exception as e:
        print("❌ Mistral transcription error:", e)
        raise


def _extract_json(content: Any) -> dict:
    """
    Intenta extraer JSON de la respuesta del modelo.
    """
    if isinstance(content, dict):
        return content

    if not isinstance(content, str):
        content = str(content)

    content = content.strip()

    try:
        return json.loads(content)
    except Exception:
        pass

    # fallback: recorta desde primer { hasta último }
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(content[start:end + 1])
        except Exception:
            pass

    raise ValueError(f"No se pudo parsear JSON válido. Respuesta: {content}")


def analyze_transcript(transcript: str) -> dict:
    """
    Analiza la transcripción y devuelve JSON estructurado:
    - summary
    - topics
    - tasks
    - decisions
    - questions
    """
    if not transcript or not transcript.strip():
        return {
            "summary": "",
            "topics": [],
            "tasks": [],
            "decisions": [],
            "questions": []
        }

    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "meeting_analysis",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "summary": {"type": "string"},
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "task": {"type": "string"},
                                "owner": {"type": "string"},
                                "due_date": {
                                    "anyOf": [
                                        {"type": "string"},
                                        {"type": "null"}
                                    ]
                                },
                                "priority": {
                                    "type": "string",
                                    "enum": ["alta", "media", "baja"]
                                },
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "done"]
                                }
                            },
                            "required": ["task", "owner", "due_date", "priority", "status"]
                        }
                    },
                    "decisions": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "questions": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["summary", "topics", "tasks", "decisions", "questions"]
            }
        }
    }

    system_prompt = (
        "Eres un analista experto en reuniones de negocio. "
        "Devuelves solo datos estructurados y no inventas información."
    )

    user_prompt = f"""
Analiza esta reunión.

Reglas:
- Extrae SOLO información explícita o fuertemente inferible.
- En tasks, incluye solo acciones concretas y ejecutables.
- Si no hay responsable, usa "sin asignar".
- Si no hay fecha, usa null.
- La prioridad debe ser: alta, media o baja.
- El status inicial siempre debe ser "pending".

Transcript:
\"\"\"{transcript}\"\"\"
"""

    try:
        response = client.chat.complete(
            model="mistral-medium-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format=schema,
        )

        content = response.choices[0].message.content
        parsed = _extract_json(content)

        return {
            "summary": parsed.get("summary", ""),
            "topics": parsed.get("topics", []),
            "tasks": parsed.get("tasks", []),
            "decisions": parsed.get("decisions", []),
            "questions": parsed.get("questions", []),
        }

    except Exception as e:
        print("❌ Mistral analysis error:", e)
        return {
            "summary": "",
            "topics": [],
            "tasks": [],
            "decisions": [],
            "questions": []
        }


def process_audio(file_path: str) -> dict:
    transcript = transcribe_audio(file_path)
    analysis = analyze_transcript(transcript)

    return {
        "transcript": transcript,
        "analysis": analysis
    }