from fastapi import FastAPI
from app.db.session import Base, engine
from app.api.routes import router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Meeting Recorder Personal")
app.include_router(router)