FROM python:3.12-slim

# Unbuffered stdout/stderr so background-task logs reach `docker logs` in real
# time. Without this the MVP's sync output never appeared anywhere.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
