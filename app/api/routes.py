from datetime import datetime, timedelta
import os
import shutil
import uuid

from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import JSONResponse

from app.core.config import UPLOAD_DIR
from app.db.session import SessionLocal
from app.models.meeting import Meeting
from app.services.ai_service import process_audio

router = APIRouter()


def normalize_task(task: dict) -> dict | None:
    if not isinstance(task, dict):
        return None

    text = str(task.get("task", "")).strip()
    if not text:
        return None

    owner = str(task.get("owner", "sin asignar")).strip() or "sin asignar"
    priority = str(task.get("priority", "media")).strip().lower()
    status = str(task.get("status", "pending")).strip().lower()
    due_date = task.get("due_date", None)

    if priority not in ["alta", "media", "baja"]:
        priority = "media"

    if status not in ["pending", "done"]:
        status = "pending"

    if due_date == "":
        due_date = None

    return {
        "task": text,
        "owner": owner,
        "due_date": due_date,
        "priority": priority,
        "status": status,
    }


def normalize_tasks(tasks: list) -> list:
    if not isinstance(tasks, list):
        return []

    clean = []
    seen = set()

    for task in tasks:
        normalized = normalize_task(task)
        if not normalized:
            continue

        key = (
            normalized["task"].lower(),
            normalized["owner"].lower(),
        )

        if key in seen:
            continue

        seen.add(key)
        clean.append(normalized)

    return clean


def build_meeting_title(meeting: Meeting) -> str:
    owner = "Sin asignar"

    tasks = meeting.tasks or []
    for task in tasks:
        task_owner = str(task.get("owner", "")).strip()
        if task_owner and task_owner.lower() != "sin asignar":
            owner = task_owner
            break

    if meeting.created_at:
        date_str = meeting.created_at.strftime("%d/%m/%Y")
    else:
        date_str = "sin fecha"

    return f"{owner} · {date_str}"


def cleanup_old_meetings(db):
    cutoff = datetime.utcnow() - timedelta(days=10)

    old_meetings = db.query(Meeting).filter(Meeting.created_at < cutoff).all()

    for meeting in old_meetings:
        audio_path = meeting.audio_path
        db.delete(meeting)

        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                print("No se pudo borrar audio antiguo:", e)

    db.commit()


@router.get("/")
def root():
    return {"status": "ok"}


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    db = SessionLocal()

    try:
        cleanup_old_meetings(db)

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

        tasks = normalize_tasks(analysis.get("tasks", []))

        meeting = Meeting(
            transcript=transcript,
            summary=analysis.get("summary", ""),
            topics=analysis.get("topics", []),
            tasks=tasks,
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
        cleanup_old_meetings(db)

        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()

        if not meeting:
            return JSONResponse(
                status_code=404,
                content={"error": "Meeting not found"}
            )

        return {
            "id": meeting.id,
            "title": build_meeting_title(meeting),
            "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
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


@router.delete("/meeting/{meeting_id}")
def delete_meeting(meeting_id: str):
    db = SessionLocal()

    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()

        if not meeting:
            return JSONResponse(
                status_code=404,
                content={"error": "Meeting not found"}
            )

        audio_path = meeting.audio_path

        db.delete(meeting)
        db.commit()

        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                print("No se pudo borrar el archivo de audio:", e)

        return {"ok": True, "deleted_id": meeting_id}

    finally:
        db.close()


@router.get("/tasks")
def get_tasks():
    db = SessionLocal()

    try:
        cleanup_old_meetings(db)

        meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).all()
        all_tasks = []

        for meeting in meetings:
            tasks = meeting.tasks or []
            for task in tasks:
                task_copy = dict(task)
                task_copy["meeting_id"] = meeting.id
                task_copy["meeting_title"] = build_meeting_title(meeting)
                task_copy["meeting_created_at"] = (
                    meeting.created_at.isoformat() if meeting.created_at else None
                )
                all_tasks.append(task_copy)

        return all_tasks

    finally:
        db.close()


@router.get("/reminders/today")
def reminders_today():
    db = SessionLocal()

    try:
        cleanup_old_meetings(db)

        meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).all()
        pending_tasks = []

        for meeting in meetings:
            tasks = meeting.tasks or []
            for task in tasks:
                if task.get("status", "pending") != "done":
                    task_copy = dict(task)
                    task_copy["meeting_id"] = meeting.id
                    task_copy["meeting_title"] = build_meeting_title(meeting)
                    pending_tasks.append(task_copy)

        return pending_tasks

    finally:
        db.close()


@router.get("/search")
def search(query: str = Query(default="")):
    db = SessionLocal()

    try:
        cleanup_old_meetings(db)

        meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).all()
        q = (query or "").strip().lower()

        if not q:
            return [
                {
                    "id": meeting.id,
                    "title": build_meeting_title(meeting),
                    "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
                    "summary": meeting.summary or "",
                    "transcript": meeting.transcript or "",
                    "topics": meeting.topics or [],
                    "tasks": meeting.tasks or [],
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
                        "title": build_meeting_title(meeting),
                        "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
                        "summary": meeting.summary or "",
                        "transcript": meeting.transcript or "",
                        "topics": meeting.topics or [],
                        "tasks": meeting.tasks or [],
                    }
                )

        return results

    finally:
        db.close()


@router.get("/daily-summary")
def daily_summary():
    db = SessionLocal()

    try:
        cleanup_old_meetings(db)

        meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).all()

        return {
            "count": len(meetings),
            "summaries": [m.summary for m in meetings if m.summary],
            "tasks_count": sum(len(m.tasks or []) for m in meetings),
        }

    finally:
        db.close()