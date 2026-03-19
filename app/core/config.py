import os
from dotenv import load_dotenv
from app.core.config import DATABASE_URL

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DATA_DIR = os.getenv("DATA_DIR", "/data")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DATA_DIR}/meetings.db"
)

UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)