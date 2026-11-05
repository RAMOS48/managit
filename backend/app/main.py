from fastapi import FastAPI
from app.database import Base, engine
from app.models import models  # noqa: F401  (registers the tables)
from app.api import devices

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ManaGit - IT Management Platform", version="0.1.0")
app.include_router(devices.router)


@app.get("/health")
def health():
    return {"status": "ok"}
