from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.models import models  # noqa: E402, F401
from app.api import devices  # noqa: E402

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ManaGit - IT Management Platform", version="0.1.0")
app.include_router(devices.router)


@app.get("/health")
def health():
    return {"status": "ok"}
