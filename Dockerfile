# ============================================================================
# FindMyWorker Backend - Production image (GeoDjango + Channels/ASGI)
# ============================================================================
FROM python:3.12-slim-bookworm

# Python runtime behaviour
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=core.settings \
    NLTK_DATA=/usr/share/nltk_data

# System libraries required by GeoDjango (GDAL/GEOS/PROJ) + a healthcheck client.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        binutils \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching).
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Pre-download NLTK data at build time (does not import Django settings, so it
# works without env vars). Best-effort: the engine ships its own stopwords.
RUN python -m nltk.downloader -d "$NLTK_DATA" stopwords punkt wordnet || \
    echo "WARN: NLTK download skipped (not required at runtime)"

# Project source
COPY . .

# Drop privileges (and ensure the entrypoint is executable even if the git
# checkout on Windows didn't preserve the exec bit).
RUN chmod +x /app/entrypoint.sh \
    && useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/logs /app/staticfiles \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
