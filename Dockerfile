# Decision Harness backend — portable image (Railway today, Fly/Lightsail later).
FROM python:3.11-slim

WORKDIR /app

# Install deps first for layer caching. Uses the COMPLETE list
# (backend/requirements.txt); the root requirements.txt is a stale subset.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# App code. .dockerignore keeps .env files, the frontend, and bloat out of the image.
COPY . .

# Railway injects $PORT at runtime; default to 8000 for a local `docker run`.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
