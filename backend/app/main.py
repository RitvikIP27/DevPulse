from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import Base, engine
from app.models import events  # noqa: F401 — registers models on Base.metadata
from app.api import routes_metrics, routes_ingest

app = FastAPI(title="DevPulse API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_metrics.router)
app.include_router(routes_ingest.router)


@app.on_event("startup")
def on_startup():
    # For a real project use Alembic migrations instead of create_all.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}
