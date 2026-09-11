# 11 · Docker, Compose and CI

## The problem containers solve

DevPulse needs Python 3.12, PostgreSQL 16, Node 20 and a dozen libraries at
specific versions. Installing those on every machine that runs it produces
"works on my machine" — the code is identical, the environment is not.

## Images and containers

A **container** is a running program packaged with everything it needs: its
runtime, libraries and files. It shares the host's kernel, so it starts in
milliseconds rather than the seconds a virtual machine takes.

An **image** is the blueprint; a **container** is a running instance. One image,
many containers.

## Reading the backend Dockerfile

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
```

Line by line:

**`FROM python:3.12-slim`** — start from an official image with Python
pre-installed. `slim` omits tooling that is not needed at runtime.

**`PYTHONUNBUFFERED=1`** — this is not decoration. Python buffers output when
not writing to a terminal, so log lines sit in memory instead of reaching
`docker logs`. The MVP's sync output **never appeared anywhere** because of
this.

**`COPY requirements.txt` before `COPY . .`** — this ordering is the important
trick. Docker caches each step and reuses it if nothing changed. Dependencies
change rarely; source changes constantly. Copying requirements first means
editing a Python file reuses the cached `pip install` layer. Reversed, every
edit would reinstall everything.

**`ENTRYPOINT ["./entrypoint.sh"]`** — migrate, then serve, failing fast if the
migration fails.

## The frontend Dockerfile — a multi-stage build

```dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

Two `FROM` lines means two stages. The first has Node and builds the app. The
second starts fresh from nginx and copies **only** `dist/` across.

The final image contains no Node, no `node_modules`, no source — just static
files and a web server. Smaller, and a far smaller attack surface.

**`npm ci` not `npm install`** — `ci` installs exactly the versions in
`package-lock.json`. `install` may resolve newer ones, so two builds of the same
commit could differ.

## nginx and the proxy

The built frontend is static files. nginx serves them and forwards API calls:

```nginx
location /api/ {
    proxy_pass http://backend:8000;
}
location / {
    try_files $uri $uri/ /index.html;
}
```

**`try_files ... /index.html`** matters for a single-page app. Visiting
`/bottlenecks` directly asks nginx for a file that does not exist. This falls
back to `index.html`, React boots, reads the URL, and renders the right page.
Without it, refreshing any page but the home page would 404.

## Docker Compose

Three containers that must find each other. `docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    ports:
      - "55432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U devpulse"]
    volumes:
      - devpulse_pgdata:/var/lib/postgresql/data

  backend:
    build: ./backend
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql://devpulse:devpulse@db:5432/devpulse
    depends_on:
      db:
        condition: service_healthy
```

**Networking.** Compose creates a private network where each service is
reachable by name. The backend connects to `db:5432` — `db` resolves to the
database container. No IP addresses anywhere.

**`55432:5432`.** Inside the network the database is on 5432. On *your machine*
it is published as 55432, because developer machines very often already run a
local PostgreSQL on 5432 — the original mapping made the documented quickstart
fail outright.

**`depends_on: condition: service_healthy`.** Starting is not the same as being
ready. PostgreSQL accepts connections only after initialising. The healthcheck
runs `pg_isready` until it succeeds, and only then does the backend start.
Without this the backend crashes on boot roughly half the time — a race that
looks like a random bug.

**Volumes.** Containers are disposable; their filesystems vanish. A **volume**
is storage that outlives them, so `docker compose down && up` keeps your data.

**`.dockerignore`** keeps `.env` and `tests/` out of the image. Secrets must
never be baked into an image, because an image can be pushed to a registry.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request.

```yaml
jobs:
  backend-tests:
    services:
      postgres:
        image: postgres:16-alpine
        options: >-
          --health-cmd pg_isready
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements-dev.txt
      - run: python -m pytest
      - run: alembic upgrade head
      - run: alembic downgrade base
      - name: Models and migrations agree
        run: ...
```

Four distinct guarantees:

1. **Tests pass** — 218 backend, 29 frontend.
2. **Migrations apply** to an empty database.
3. **Migrations reverse** — `downgrade base` proves they are not one-way.
4. **No model drift** — autogenerate must produce an empty migration.

The `frontend-build` job type-checks, runs Vitest and builds. `docker-build`
builds both images, so a broken Dockerfile fails CI rather than deployment.

`cache: pip` / `cache: npm` reuse downloaded dependencies between runs, taking
CI from minutes to under a minute.

## A CI lesson worth remembering

At one point the suite **passed in CI and failed locally**. Settings load from
`backend/.env`, and a local `DEMO_MODE=true` flipped provider availability —
which is exactly what several tests assert about.

CI was green only because it has no `.env` file. That is the worst kind of
green: passing for a reason unrelated to the code.

The fix was an autouse fixture neutralising every environment-sensitive setting,
verified by running the suite both with and without those variables set. The
rule now lives in `testing.md`:

> **A test that depends on the machine it runs on is not a test.**

---

**Next:** [12 · Testing](12-testing.md)
