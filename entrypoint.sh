#!/usr/bin/env bash
# ============================================================================
# Runtime entrypoint. Runs DB migrations + collectstatic (env vars are present
# now, unlike at build time), warms the recommendation model, then starts the
# ASGI server (uvicorn) which serves both HTTP and WebSockets.
# ============================================================================
set -e

echo "==> Applying database migrations"
python manage.py migrate --noinput

echo "==> Collecting static files"
python manage.py collectstatic --noinput

# Best-effort model warm-up. Fails harmlessly on an empty DB (no workers yet)
# or if Redis is briefly unavailable; the app boots either way.
# Create superuser if DJANGO_SUPERUSER_EMAIL is set (one-time bootstrap)
if [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
    echo "==> Creating superuser (best-effort)"
    python manage.py createsuperuser --noinput || echo "WARN: superuser already exists or creation skipped"
fi

echo "==> Seeding demo data (best-effort)"
python manage.py seed_demo || echo "WARN: demo seed skipped"

echo "==> Training recommendation model (best-effort)"
python manage.py train_recommendation_model || echo "WARN: model training skipped"

PORT="${PORT:-8000}"
# Daphne is the Channels reference ASGI server and serves HTTP *and* WebSocket.
# (Plain uvicorn ships without a WebSocket implementation, so WS upgrades fall
# through to the HTTP app and 404 — which broke real-time chat.)
echo "==> Starting daphne on 0.0.0.0:${PORT}"
exec daphne -b 0.0.0.0 -p "${PORT}" --proxy-headers core.asgi:application
