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

echo "==> Training recommendation model (best-effort)"
python manage.py train_recommendation_model || echo "WARN: model training skipped"

PORT="${PORT:-8000}"
echo "==> Starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn core.asgi:application --host 0.0.0.0 --port "${PORT}" --proxy-headers --forwarded-allow-ips='*'
