from fastapi import APIRouter, UploadFile, File
import shutil
import uuid
import os

from app.core.config import UPLOAD_DIR
from app.db.session import SessionLocal
from app.models.meeting import Meeting
from app.services.ai_service import process_audio

router = APIRouter()


# ---------------------------
# ROOT
# ---------------------------
@router.get("/")
def root():
    return {"status": "ok"}


# ---------------------------
# UPLOAD + IA PIPELINE
# ---------------------------
@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    db = SessionLocal()

    try:
        # generar id
        file_id = str(uuid.uuid4())

        # guardar archivo
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}.wav")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # procesar audio (transcripción + IA)
        result = process_audio(file_path)

        transcript = result["transcript"]
        analysis = result["analysis"]

        # guardar en DB
        meeting = Meeting(
            transcript=transcript,
            summary=analysis.get("summary"),
            topics=analysis.get("topics"),
            tasks=analysis.get("tasks"),
            speakers=[],
            metrics={},
            audio_path=file_path
        )

        db.add(meeting)
        db.commit()
        db.refresh(meeting)

        return {"id": meeting.id}

    except Exception as e:
        print("ERROR UPLOAD:", e)
        return {"error": str(e)}

    finally:
        db.close()


# ---------------------------
# GET MEETING
# ---------------------------
@router.get("/meeting/{meeting_id}")
def get_meeting(meeting_id: str):
    db = SessionLocal()

    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()

        if not meeting:
            return {"error": "not found"}

        return {
            "id": meeting.id,
            "transcript": meeting.transcript,
            "summary": meeting.summary,
            "topics": meeting.topics,
            "tasks": meeting.tasks,
            "metrics": meeting.metrics
        }

    finally:
        db.close()


# ---------------------------
# ALL TASKS
# ---------------------------
@router.get("/tasks")
def get_tasks():
    db = SessionLocal()

    try:
        meetings = db.query(Meeting).all()

        all_tasks = []

        for m in meetings:
            if m.tasks:
                for t in m.tasks:
                    t["meeting_id"] = m.id
                    all_tasks.append(t)

        return all_tasks

    finally:
        db.close()


# ---------------------------
# REMINDERS (pending tasks)
# ---------------------------
@router.get("/reminders/today")
def reminders_today():
    db = SessionLocal()

    try:
        meetings = db.query(Meeting).all()

        tasks = []

        for m in meetings:
            if m.tasks:
                for t in m.tasks:
                    if t.get("status", "pending") != "done":
                        tasks.append(t)

        return tasks

    finally:
        db.close()


# ---------------------------
# SEARCH IN TRANSCRIPTS
# ---------------------------
@router.get("/search")
def search(query: str):
    db = SessionLocal()

    try:
        meetings = db.query(Meeting).all()

        results = []

        for m in meetings:
            if query.lower() in (m.transcript or "").lower():
                results.append({
                    "id": m.id,
                    "summary": m.summary
                })

        return results

    finally:
        db.close()


# ---------------------------
# DAILY SUMMARY
# ---------------------------
@router.get("/daily-summary")
def daily_summary():
    db = SessionLocal()

    try:
        meetings = db.query(Meeting).all()

        summaries = [m.summary for m in meetings if m.summary]

        return {
            "count": len(meetings),
            "summaries": summaries
        }

    finally:
        db.close()