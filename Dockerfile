# Python 3.11 runtime (host may be older; the container is the source of truth).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System deps: Java for Synthea, build basics for psycopg/spacy.
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# spaCy English model used by Presidio NER.
RUN python -m spacy download en_core_web_lg || python -m spacy download en_core_web_sm

COPY . .

EXPOSE 8000

# Overridden by docker-compose for day-1; this is the eventual serving default.
CMD ["uvicorn", "carenav.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
