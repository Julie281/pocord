from fastapi import APIRouter, UploadFile, File
import shutil
import uuid
import os

from app.core.config import UPLOAD_DIR
from app.db.session import SessionLocal
from app.models.meeting import Meeting
from app.services.ai_service import analyze_transcript

router = APIRouter()

# ---------------------------
# ROOT
# ---------------------------
@router.get("/")
def root():
    return {"status": "ok"}


# ---------------------------
# UPLOAD + ANALYSIS
# ---------------------------
@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    db = SessionLocal()

    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.wav")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # ⚠️ de momento fake transcript (luego metemos OpenAI)
    transcript = "Reunión de ejemplo donde se acuerda enviar propuesta mañana"

    analysis = analyze_transcript(transcript)

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


# ---------------------------
# GET MEETING
# ---------------------------
@router.get("/meeting/{meeting_id}")
def get_meeting(meeting_id: str):
    db = SessionLocal()

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


# ---------------------------
# TASKS GLOBAL
# ---------------------------
@router.get("/tasks")
def get_tasks():
    db = SessionLocal()

    meetings = db.query(Meeting).all()

    tasks = []

    for m in meetings:
        if m.tasks:
            for t in m.tasks:
                t["meeting_id"] = m.id
                tasks.append(t)

    return tasks


# ---------------------------
# REMINDERS
# ---------------------------
@router.get("/reminders/today")
def reminders_today():
    db = SessionLocal()
    meetings = db.query(Meeting).all()

    tasks = []

    for m in meetings:
        if m.tasks:
            for t in m.tasks:
                if t.get("status", "pending") != "done":
                    tasks.append(t)

    return tasks


# ---------------------------
# SEARCH
# ---------------------------
@router.get("/search")
def search(query: str):
    db = SessionLocal()

    meetings = db.query(Meeting).all()

    results = []

    for m in meetings:
        if query.lower() in (m.transcript or "").lower():
            results.append({
                "id": m.id,
                "summary": m.summary
            })

    return results


# ---------------------------
# DAILY SUMMARY
# ---------------------------
@router.get("/daily-summary")
def daily_summary():
    db = SessionLocal()

    meetings = db.query(Meeting).all()

    summaries = [m.summary for m in meetings if m.summary]

    return {
        "count": len(meetings),
        "summaries": summaries
    }