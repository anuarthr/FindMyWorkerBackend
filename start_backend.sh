#!/bin/bash

echo "🚀 Iniciando FindMyWorker Backend..."
echo ""

# Verificar entorno virtual
if [ ! -d "venv" ]; then
    echo "❌ Error: No se encuentra el entorno virtual"
    echo "Ejecuta: python -m venv venv"
    exit 1
fi

# Activar entorno virtual
source venv/bin/activate

# Verificar Redis
echo "🔍 Verificando Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis no está corriendo. Iniciando..."
    redis-server --daemonize yes
    sleep 1
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis iniciado"
    else
        echo "❌ Error: No se pudo iniciar Redis"
        exit 1
    fi
else
    echo "✅ Redis corriendo"
fi

# Aplicar migraciones pendientes
echo ""
echo "🔄 Verificando migraciones..."
python manage.py migrate --check > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "⚠️  Hay migraciones pendientes. Aplicando..."
    python manage.py migrate
fi

# Iniciar servidor
echo ""
echo "✅ Todo listo. Iniciando servidor..."
echo ""
echo "📡 Backend disponible en:"
echo "   HTTP:      http://localhost:8000"
echo "   WebSocket: ws://localhost:8000/ws/chat/"
echo ""
echo "Presiona Ctrl+C para detener"
echo ""

# Iniciar con Uvicorn
uvicorn core.asgi:application --host 0.0.0.0 --port 8000 --reload
