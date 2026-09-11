# 03 · Python and FastAPI

## Why Python

DevPulse's backend is mostly **statistics over time-series data**: medians,
percentiles, deviations, windowed comparisons. Python is the ordinary choice for
that kind of work, and the standard library alone covers most of what DevPulse
needs (`statistics.median`, `datetime`, `hashlib`, `hmac`).

## What a web framework does for you

Without a framework, answering a request means writing code that opens a network
socket, reads raw bytes, parses the HTTP text format, figures out which function
to call, and formats the reply. Nobody does this by hand.

A **web framework** handles all of that. You write:

> "When a `GET` arrives at `/api/repositories`, call this function."

That mapping is a **route**.

## FastAPI in one example

Here is `backend/app/api/routes_bottlenecks.py`, complete:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.bottlenecks import BottleneckResponse
from app.services.bottlenecks import detect_bottlenecks

router = APIRouter(prefix="/api/bottlenecks", tags=["bottlenecks"])


@router.get("", response_model=BottleneckResponse)
def get_bottlenecks(
    repository_id: int | None = Query(None),
    window_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> BottleneckResponse:
    """Deterministic bottleneck analysis with the evidence behind each score."""
    return detect_bottlenecks(db, repository_id=repository_id, window_days=window_days)
```

Six things are happening:

**1. `APIRouter(prefix=...)`** groups related routes. Every route in this file
starts with `/api/bottlenecks`. Routers are how a growing API stays organised —
DevPulse has twelve of them.

**2. `@router.get("")`** is a **decorator**. In Python, `@something` above a
function means "pass this function to `something` first". Here it registers the
function as the handler for `GET /api/bottlenecks`.

**3. `window_days: int = Query(30, ge=1, le=365)`** declares a query parameter —
the `?window_days=90` part of a URL. The annotations are not documentation;
FastAPI **enforces** them. A request with `window_days=9999` is rejected with
`422` before your function runs. You never write that check.

**4. `db: Session = Depends(get_db)`** is **dependency injection**, explained
below.

**5. `response_model=BottleneckResponse`** guarantees the shape of the reply.
If the function returned something that didn't match, FastAPI raises rather than
sending malformed JSON to the frontend.

**6. The docstring** becomes the description in the auto-generated API docs at
`http://localhost:8000/docs` — a live, clickable page listing every endpoint,
generated from the code itself. Nothing to maintain separately.

## Dependency injection

This is the concept worth understanding properly, because DevPulse's entire
authentication model rests on it.

A route **declares what it needs** rather than fetching it:

```python
db: Session = Depends(get_db)
```

This reads: *"before running me, call `get_db()` and give me the result."*

`get_db` lives in `backend/app/core/database.py`:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

The `yield` is the interesting part. Code before it runs **before** the route;
code after it runs **after** — even if the route raised an exception. So the
database connection is always closed. You cannot forget, because forgetting is
not something you can express.

### Why this matters for security

In `backend/app/main.py`:

```python
_protected = Depends(current_user)
for _router in (routes_metrics.router, routes_ingest.router, ...):
    app.include_router(_router, dependencies=[_protected])
```

Every data router is registered **with an authentication dependency attached at
the router level**.

The alternative is putting `Depends(current_user)` on each handler individually.
That works — until someone adds a route and forgets. That is precisely how
authentication holes appear in real systems.

Declared once at the router, **a new endpoint is protected by default**. Making
one public requires deliberately putting it in a different router — which is
exactly what `routes_webhooks.py` does, with a comment explaining why.

## Async, and why most DevPulse routes are not

You will see `async def` in FastAPI examples. It means the function can pause
while waiting for something slow (a network call) and let the server handle
other requests meanwhile.

Most DevPulse routes are plain `def`. That is deliberate: they do database work
via SQLAlchemy, which is synchronous, and FastAPI automatically runs plain `def`
handlers in a thread pool so they do not block the server.

One route *is* `async` — the webhook receiver, because it must read the raw
request body:

```python
async def github_webhook(request: Request, ...):
    raw_body = await request.body()
```

`await` means "pause here until this finishes". Reading a body is genuinely
asynchronous, so the function must be too.

**Why the raw body?** The signature GitHub sends covers the exact bytes it sent.
If you parsed the JSON and re-serialised it, you would get *equivalent* JSON with
possibly different spacing or key order — and a different signature. Verification
must happen on the original bytes.

## Background tasks

```python
@router.post("/sync", status_code=202)
def trigger_sync(background_tasks: BackgroundTasks) -> dict[str, str]:
    background_tasks.add_task(sync_all)
    return {"status": "accepted", ...}
```

The response is sent immediately; `sync_all` runs after. This is why the status
code is `202 Accepted`, not `200 OK` — the work has been *accepted*, not
completed.

This pattern caused a real bug worth knowing about. The original version returned
`200 {"status": "sync started"}` and then discarded whatever happened. An invalid
GitHub token raised a `401` inside the background task that reached **no log, no
database row, and no user**. The fix was `SyncJob` — every sync now records its
own outcome, which you can read back at `GET /api/ingest/jobs`.

## The application object

`backend/app/main.py` ties it together:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield

app = FastAPI(title="DevPulse API", version="0.1.0", lifespan=lifespan)
```

`lifespan` is startup/shutdown: before `yield` runs at boot, after `yield` runs
at shutdown. Note what is **absent** — no database table creation. That is
Alembic's job, and chapter 04 explains why that separation matters.

---

**Next:** [04 · The database layer](04-database-orm-migrations.md)
