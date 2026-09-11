from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_analysis,
    routes_auth,
    routes_anomalies,
    routes_bottlenecks,
    routes_conflicts,
    routes_health_score,
    routes_deliveries,
    routes_ingest,
    routes_metrics,
    routes_repositories,
)
from app.core.config import settings
from app.core.dependencies import current_user
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

# Browsers enforce CORS: with "*" any website a signed-in user visits could call
# this API. Configurable, and narrowing it is part of enabling auth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=settings.cors_origins != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth routes are public by necessity: you cannot present a token before you
# have one, and the UI needs /status to know whether to show a login screen.
app.include_router(routes_auth.router)

# Every data route is protected at the ROUTER level rather than per handler.
# Per-handler dependencies are the classic way an auth hole appears: someone
# adds an endpoint and forgets the decorator. Declaring it once here means a new
# route is protected by default and would have to be deliberately excluded.
_protected = Depends(current_user)
for _router in (
    routes_metrics.router,
    routes_ingest.router,
    routes_repositories.router,
    routes_deliveries.router,
    routes_bottlenecks.router,
    routes_conflicts.router,
    routes_analysis.router,
    routes_anomalies.router,
    routes_health_score.router,
):
    app.include_router(_router, dependencies=[_protected])


@app.get("/health")
def health():
    return {"status": "ok"}
