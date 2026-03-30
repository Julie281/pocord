from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import JSONResponse
import shutil
import uuid
import os

from app.core.config import UPLOAD_DIR
from app.db.session import SessionLocal
from app.models.meeting import Meeting
from app.services.ai_service import process_audio

router = APIRouter()


@router.get("/")
def root():
    return {"status": "ok"}


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    db = SessionLocal()

    try:
        file_id = str(uuid.uuid4())

        original_name = file.filename or "audio.wav"
        _, ext = os.path.splitext(original_name)
        if not ext:
            ext = ".wav"

        file_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = process_audio(file_path)
        transcript = result.get("transcript", "")
        analysis = result.get("analysis", {})

        meeting = Meeting(
            transcript=transcript,
            summary=analysis.get("summary", ""),
            topics=analysis.get("topics", []),
            tasks=analysis.get("tasks", []),
            speakers=[],
            metrics={},
            audio_path=file_path,
        )

        db.add(meeting)
        db.commit()
        db.refresh(meeting)

        return {"id": meeting.id}

    except Exception as e:
        print("ERROR UPLOAD:", e)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

    finally:
        db.close()


@router.get("/meeting/{meeting_id}")
def get_meeting(meeting_id: str):
    db = SessionLocal()

    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()

        if not meeting:
            return JSONResponse(
                status_code=404,
                content={"error": "Meeting not found"}
            )

        return {
            "id": meeting.id,
            "transcript": meeting.transcript or "",
            "summary": meeting.summary or "",
            "topics": meeting.topics or [],
            "tasks": meeting.tasks or [],
            "speakers": meeting.speakers or [],
            "metrics": meeting.metrics or {},
            "audio_path": meeting.audio_path or "",
        }

    finally:
        db.close()


@router.get("/tasks")
def get_tasks():
    db = SessionLocal()

    try:
        meetings = db.query(Meeting).all()
        all_tasks = []

        for meeting in meetings:
            tasks = meeting.tasks or []
            for task in tasks:
                task_copy = dict(task)
                task_copy["meeting_id"] = meeting.id
                task_copy["meeting_summary"] = meeting.summary or ""
                all_tasks.append(task_copy)

        return all_tasks

    finally:
        db.close()


@router.get("/reminders/today")
def reminders_today():
    db = SessionLocal()

    try:
        meetings = db.query(Meeting).all()
        pending_tasks = []

        for meeting in meetings:
            tasks = meeting.tasks or []
            for task in tasks:
                if task.get("status", "pending") != "done":
                    task_copy = dict(task)
                    task_copy["meeting_id"] = meeting.id
                    task_copy["meeting_summary"] = meeting.summary or ""
                    pending_tasks.append(task_copy)

        return pending_tasks

    finally:
        db.close()


@router.get("/search")
def search(query: str = Query(default="")):
    db = SessionLocal()

    try:
        meetings = db.query(Meeting).all()
        q = (query or "").strip().lower()

        if not q:
            return [
                {
                    "id": meeting.id,
                    "summary": meeting.summary or "Sin resumen",
                    "transcript": meeting.transcript or "",
                    "topics": meeting.topics or [],
                }
                for meeting in meetings
            ]

        results = []

        for meeting in meetings:
            transcript = (meeting.transcript or "").lower()
            summary = (meeting.summary or "").lower()

            topics_text = " ".join(meeting.topics or []).lower()

            tasks_text = " ".join(
                [
                    f"{t.get('task', '')} {t.get('owner', '')} {t.get('priority', '')}"
                    for t in (meeting.tasks or [])
                ]
            ).lower()

            hay_match = (
                q in transcript
                or q in summary
                or q in topics_text
                or q in tasks_text
            )

            if hay_match:
                results.append(
                    {
                        "id": meeting.id,
                        "summary": meeting.summary or "Sin resumen",
                        "transcript": meeting.transcript or "",
                        "topics": meeting.topics or [],
                    }
                )

        return results

    finally:
        db.close()


@router.get("/daily-summary")
def daily_summary():
    db = SessionLocal()

    try:
        meetings = db.query(Meeting).all()

        return {
            "count": len(meetings),
            "summaries": [m.summary for m in meetings if m.summary],
            "tasks_count": sum(len(m.tasks or []) for m in meetings),
        }

    finally:
        db.close()