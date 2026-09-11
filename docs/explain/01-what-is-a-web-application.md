# 01 · What a web application is

Start from nothing. No assumptions.

## Two computers having a conversation

When you open `devpulse.example.com` in a browser, two separate computers are
involved:

```text
   YOUR COMPUTER                          SOMEONE ELSE'S COMPUTER
   ┌──────────────┐                       ┌──────────────────────┐
   │   Browser    │ ──── "give me the ──► │        Server        │
   │  (Chrome…)   │       dashboard"      │  (a program that     │
   │              │ ◄─── here it is ───── │   waits for requests)│
   └──────────────┘                       └──────────────────────┘
      the CLIENT                                 the SERVER
```

The **client** asks. The **server** answers. That is the whole model. Everything
else is detail.

## What actually travels between them

A **request** is a small text message. Simplified, it looks like:

```text
GET /api/repositories HTTP/1.1
Host: devpulse.example.com
Authorization: Bearer eyJhbGciOi...
```

- `GET` is the **method** — what kind of action. `GET` reads, `POST` creates or
  triggers, `DELETE` removes.
- `/api/repositories` is the **path** — which thing you want.
- The lines after are **headers** — extra context, like who you are.

The **response** comes back with a **status code** and a body:

```text
HTTP/1.1 200 OK
Content-Type: application/json

{"repositories": [{"id": 1, "full_name": "RitvikIP27/DevPulse"}]}
```

Status codes you will see throughout DevPulse:

| Code | Meaning | Where DevPulse uses it |
|---|---|---|
| 200 | OK | Any successful read |
| 201 | Created | A new account, a new deployment rule |
| 202 | Accepted — *started, not finished* | `POST /api/ingest/sync`, `POST /api/webhooks/github` |
| 204 | Done, nothing to return | Acknowledging an anomaly |
| 401 | Not authenticated | No token, or an invalid one |
| 403 | Authenticated but not allowed | Registering when an account already exists |
| 404 | Not found | Unknown delivery id |
| 422 | Your input was malformed | A password under 12 characters |
| 503 | Not available | Webhooks with no secret configured |

**Why 202 matters in DevPulse:** syncing GitHub takes seconds. If the server
waited before replying, the caller might time out and retry, causing the same
sync to run twice. So DevPulse replies `202 Accepted` — "I have your request,
I'll work on it" — and records the outcome separately.

## JSON

The data format in the body above is **JSON** (JavaScript Object Notation). It
is just text with a strict shape: `{}` for records, `[]` for lists, quoted
strings, numbers, `true`/`false`/`null`.

```json
{
  "service": "payments",
  "deployment_frequency_per_week": 0.47,
  "lead_time_hours": null
}
```

That `null` is doing real work in DevPulse. It means **"we could not measure
this"** — distinct from `0`, which means "we measured and got zero".

## The third piece: a database

A server usually forgets everything when it restarts. A **database** is a
separate program whose only job is to remember things reliably.

DevPulse uses **PostgreSQL**. It stores data in **tables** — like spreadsheets
with strictly typed columns:

```text
  repositories
  ┌────┬─────────────────────────────┬───────────────┐
  │ id │ full_name                   │ display_name  │
  ├────┼─────────────────────────────┼───────────────┤
  │  1 │ RitvikIP27/DevPulse         │ DevPulse      │
  │  2 │ RitvikIP27/KubernesDeployment│ Kubernes…    │
  └────┴─────────────────────────────┴───────────────┘
```

## So DevPulse is three programs

```text
┌─────────────┐   HTTP    ┌─────────────┐   SQL    ┌────────────┐
│   Browser   │ ────────► │   Backend   │ ───────► │ PostgreSQL │
│  (React)    │ ◄──────── │  (FastAPI)  │ ◄─────── │            │
└─────────────┘   JSON    └─────────────┘   rows   └────────────┘
   frontend/              backend/                  the db container
```

Plus a fourth arrow pointing outward: the backend also makes its **own** requests
to GitHub, Prometheus and PagerDuty. There it is the client.

## Why split frontend and backend at all?

You could have the server send finished HTML pages. Many sites do. DevPulse
separates them because:

1. **The browser cannot be trusted.** Anything running on someone's machine can
   be modified by them. Credentials and analytics must live server-side.
2. **The same API serves many clients.** A CLI, a mobile app, or another service
   can call `/api/deliveries` without any of the UI existing.
3. **They change at different speeds.** Redesigning a page should not risk the
   correlation engine.

## What an "API" is

An **API** (Application Programming Interface) is the set of paths the server
agrees to answer, and the shape of data each returns. DevPulse's API is the 23
paths listed in chapter 06. The frontend knows *only* those paths — it has no
idea PostgreSQL exists.

That boundary is why `frontend/src/api/client.ts` is the single file allowed to
make network calls. Everything else in the UI goes through it.

---

**Next:** [02 · The problem DevPulse solves](02-the-problem.md)
