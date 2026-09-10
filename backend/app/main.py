from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_bottlenecks,
    routes_conflicts,
    routes_deliveries,
    routes_ingest,
    routes_metrics,
    routes_repositories,
)
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown.

    Schema creation deliberately does NOT happen here. It is owned by Alembic and
    applied by the container entrypoint before the server starts, so that schema
    changes have migration history instead of being silently inferred from the
    models at boot (rules.md 13).
    """
    configure_logging()
    yield


app = FastAPI(title="DevPulse API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_metrics.router)
app.include_router(routes_ingest.router)
app.include_router(routes_repositories.router)
app.include_router(routes_deliveries.router)
app.include_router(routes_bottlenecks.router)
app.include_router(routes_conflicts.router)


@app.get("/health")
def health():
    return {"status": "ok"}
