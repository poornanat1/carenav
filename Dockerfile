# Python 3.11 runtime (host may be older; the container is the source of truth).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Serving needs no system build deps: psycopg ships as a binary wheel and the data
# pipeline (Java/Synthea) runs offline, not in the serving image. curl is kept for
# health probing.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Install the carenav package itself (src/ layout). Runtime deps already came from
# requirements.txt above, so skip re-resolving them.
RUN pip install --no-deps -e .

EXPOSE 8000

# Serve the FastAPI app. $PORT is injected by the host (Render etc.); default 8000
# for local `docker run`. Shell form so $PORT expands.
CMD uvicorn carenav.api.app:app --host 0.0.0.0 --port ${PORT:-8000}
