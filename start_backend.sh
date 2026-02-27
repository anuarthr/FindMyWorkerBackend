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

# Verificar recursos NLP (HU2: Sistema de Recomendación)
echo ""
echo "🤖 Verificando sistema de recomendación..."

# Verificar NLTK resources
echo "🔍 Comprobando recursos NLTK..."
python -c "import nltk; nltk.data.find('corpora/stopwords')" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "⚠️  Recursos NLTK no encontrados. Descargando..."
    python manage.py setup_nlp
    if [ $? -eq 0 ]; then
        echo "✅ Recursos NLTK instalados"
    else
        echo "❌ Error al instalar recursos NLTK"
        exit 1
    fi
else
    echo "✅ Recursos NLTK disponibles"
fi

# Verificar modelo TF-IDF entrenado
echo "🔍 Verificando modelo de recomendación..."

# Verificar si hay trabajadores con biografías
WORKER_COUNT=$(python manage.py shell -c "from users.models import WorkerProfile; print(WorkerProfile.objects.exclude(bio='').count())" 2>/dev/null | tail -n 1)

if [ "$WORKER_COUNT" = "0" ] || [ -z "$WORKER_COUNT" ]; then
    echo "⚠️  No hay trabajadores con biografías. El sistema de recomendación requiere datos."
    echo "   Puedes agregar trabajadores manualmente en: http://localhost:8000/admin/"
    echo "   O continuar sin recomendaciones (búsqueda básica funcionará)."
else
    # Verificar si el modelo está en Redis cache
    MODEL_EXISTS=$(redis-cli -n 1 EXISTS ':1:recommendation_model_data' 2>/dev/null)
    
    if [ "$MODEL_EXISTS" = "0" ] || [ -z "$MODEL_EXISTS" ]; then
        echo "⚠️  Modelo no encontrado en cache. Entrenando con $WORKER_COUNT trabajadores..."
        python manage.py train_recommendation_model
        
        if [ $? -eq 0 ]; then
            echo "✅ Modelo de recomendación entrenado exitosamente"
        else
            echo "❌ Error al entrenar modelo. Revisa los logs arriba."
            echo "   El sistema continuará pero las recomendaciones IA no funcionarán."
        fi
    else
        echo "✅ Modelo de recomendación disponible en cache ($WORKER_COUNT trabajadores)"
    fi
fi

# Iniciar servidor
echo ""
echo "✅ Todo listo. Iniciando servidor..."
echo ""
echo "📡 Backend disponible en:"
echo "   HTTP:      http://localhost:8000"
echo "   WebSocket: ws://localhost:8000/ws/chat/"
echo ""
echo "🤖 Endpoints de Recomendación:"
echo "   POST   /api/users/workers/recommend/"
echo "   GET    /api/users/workers/recommendation-health/"
echo ""
echo "Presiona Ctrl+C para detener"
echo ""

# Iniciar con Uvicorn
uvicorn core.asgi:application --host 0.0.0.0 --port 8000 --reload
