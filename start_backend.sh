#!/usr/bin/env bash
# ============================================================================
# FindMyWorker Backend - dev launcher (WSL/Linux/macOS).
#
# - Levanta los servicios de docker-compose (Postgres+PostGIS, Redis).
# - Activa el venv del proyecto.
# - Aplica migraciones pendientes.
# - Asegura recursos NLTK (opcional, el engine ya trae sus propias stopwords).
# - "Warmea" el modelo TF-IDF (idempotente: si está cacheado, no reentrena).
# - Arranca uvicorn con autoreload sobre core.asgi.
# ============================================================================
set -e
cd "$(dirname "$0")"

echo "🚀 FindMyWorker Backend"
echo ""

# ---------------------------------------------------------------------------
# venv
# ---------------------------------------------------------------------------
if [ ! -d "venv" ]; then
    echo "❌ No se encuentra venv/. Crea uno con:"
    echo "   python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
# shellcheck disable=SC1091
source venv/bin/activate
echo "✅ venv activo: $(python -c 'import sys; print(sys.prefix)')"

# ---------------------------------------------------------------------------
# Servicios infra: Postgres + Redis vía docker-compose
# ---------------------------------------------------------------------------
echo ""
echo "🐳 Verificando servicios docker-compose (db + redis)..."

if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    DC=""
    echo "⚠️  Docker no disponible. Asumiendo Postgres + Redis nativos en localhost."
fi

if [ -n "$DC" ]; then
    $DC up -d db redis
    echo "⌛ Esperando a que Postgres acepte conexiones..."
    for i in $(seq 1 30); do
        if $DC exec -T db pg_isready -U postgres >/dev/null 2>&1; then
            echo "✅ Postgres listo"
            break
        fi
        sleep 1
        if [ "$i" -eq 30 ]; then
            echo "❌ Postgres no respondió en 30s. Revisa: $DC logs db"
            exit 1
        fi
    done
fi

# ---------------------------------------------------------------------------
# Migraciones
# ---------------------------------------------------------------------------
echo ""
echo "🔄 Verificando migraciones..."
if python manage.py migrate --check >/dev/null 2>&1; then
    echo "✅ Migraciones al día"
else
    echo "⚠️  Aplicando migraciones pendientes..."
    python manage.py migrate
fi

# ---------------------------------------------------------------------------
# NLTK (best-effort). El engine actual usa sus propias stopwords/sinónimos
# hardcoded, así que esto es básicamente paridad con la docs/setup_nlp.
# ---------------------------------------------------------------------------
echo ""
echo "📦 Verificando recursos NLTK..."
if python -c "import nltk; nltk.data.find('corpora/stopwords')" >/dev/null 2>&1; then
    echo "✅ NLTK listo"
else
    echo "⚠️  Descargando recursos NLTK..."
    python manage.py setup_nlp || echo "⚠️  setup_nlp falló (no crítico; el engine no lo requiere en runtime)"
fi

# ---------------------------------------------------------------------------
# Warm-up del modelo TF-IDF.
# Es idempotente: si ya está en el cache de Redis, train_model retorna sin
# reentrenar. Si no hay workers verificados con bio, falla silenciosamente
# (la app arranca igual; el endpoint /recommend/ reportará not_trained).
# ---------------------------------------------------------------------------
echo ""
echo "🤖 Warm-up del modelo de recomendación..."
python manage.py train_recommendation_model 2>&1 | tail -n 3 \
    || echo "ℹ️  Sin datos para entrenar el modelo (continúa sin recomendaciones IA)"

# ---------------------------------------------------------------------------
# Server (uvicorn ASGI, sirve HTTP + WebSockets en el mismo puerto)
# ---------------------------------------------------------------------------
echo ""
echo "✅ Todo listo. Iniciando servidor..."
echo ""
echo "📡 Backend disponible en:"
echo "   HTTP:      http://localhost:8000"
echo "   Admin:     http://localhost:8000/admin/"
echo "   WebSocket: ws://localhost:8000/ws/chat/{order_id}/?token=<jwt>"
echo ""
echo "🤖 Endpoints clave:"
echo "   POST   /api/users/workers/recommend/"
echo "   GET    /api/users/workers/recommendation-health/"
echo ""
echo "Presiona Ctrl+C para detener"
echo ""

exec uvicorn core.asgi:application --host 0.0.0.0 --port 8000 --reload
