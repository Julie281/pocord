from fastapi import APIRouter, UploadFile, File
import shutil
import uuid
import os

from app.core.config import UPLOAD_DIR

router = APIRouter()

@router.get("/")
def root():
    return {"status": "ok"}


@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.wav")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"id": file_id}