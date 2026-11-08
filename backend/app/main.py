from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from sqlalchemy import delete  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import models  # noqa: E402, F401
from app.models.models import MetricSnapshot, utcnow  # noqa: E402
from app.api import devices, diagnostics, monitoring, tickets  # noqa: E402

METRIC_RETENTION_DAYS = 7
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Remove old metric snapshots so the SQLite file does not grow forever
    with SessionLocal() as db:
        cutoff = utcnow() - timedelta(days=METRIC_RETENTION_DAYS)
        db.execute(delete(MetricSnapshot).where(MetricSnapshot.collected_at < cutoff))
        db.commit()
    yield


app = FastAPI(title="ManaGit - IT Management Platform", version="0.1.0", lifespan=lifespan)
app.include_router(devices.router)
app.include_router(monitoring.router)
app.include_router(diagnostics.router)
app.include_router(tickets.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/admin/")


# Mounted last so they never shadow the API routes
app.mount("/admin", StaticFiles(directory=FRONTEND_DIR / "admin", html=True), name="admin")
app.mount("/portal", StaticFiles(directory=FRONTEND_DIR / "employee", html=True), name="portal")
