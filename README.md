# FindMyWorker Backend

Sistema de recomendación inteligente basado en IA para conectar clientes con trabajadores freelance mediante búsqueda semántica.

## Características

- 🔐 Autenticación JWT
- 📦 Gestión de órdenes de servicio
- ⏱️ Registro de horas trabajadas
- 💬 Chat en tiempo real (WebSocket)
- 📍 Búsqueda de trabajadores por ubicación
- 🤖 Sistema de recomendación con TF-IDF
- 🎯 Búsqueda semántica en lenguaje natural
- 📊 Analytics y métricas de recomendación
- 📸 Portafolio visual de evidencias con compresión automática

## Tecnologías

- Django 6.0 + Django REST Framework
- Django Channels 4.0.0 (WebSocket)
- PostgreSQL + PostGIS
- Redis 4.6.0 + django-redis 5.2.0
- scikit-learn 1.4.0+ (Machine Learning)
- NLTK 3.8.1+ (NLP español)
- joblib 1.3.2+ (Model caching)
- Pillow 12.0.0+ (Image processing)
- boto3 + django-storages (S3 storage)

## Instalación

```bash
# Clonar repositorio
git clone https://github.com/anuarthr/FindMyWorkerBackend.git
cd FindMyWorkerBackend

# Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Configurar base de datos PostgreSQL con PostGIS

# Ejecutar migraciones
python manage.py migrate

# Configurar NLP (descargar recursos NLTK español)
python manage.py setup_nlp

# Validar corpus de trabajadores (opcional)
python manage.py validate_corpus --detailed

# Entrenar modelo de recomendación
python manage.py train_recommendation_model

# Crear superusuario
python manage.py createsuperuser

# Iniciar Redis

# Ejecutar servidor
python manage.py runserver
```

## Configuración

Crear archivo `.env`:

```env
SECRET_KEY=tu-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=findmyworker
DB_USER=postgres
DB_PASSWORD=tu-password
DB_HOST=localhost
DB_PORT=5432

REDIS_HOST=127.0.0.1
REDIS_PORT=6379

CORS_ORIGINS=http://localhost:5173
```

## API Endpoints

### Autenticación
```
POST /api/users/register/
POST /api/users/token/
GET  /api/users/me/
```

### Órdenes
```
GET    /api/orders/
POST   /api/orders/
GET    /api/orders/{id}/
PATCH  /api/orders/{id}/status/

POST /api/orders/{id}/work-hours/
POST /api/orders/{id}/work-hours/{log_id}/approve/
```

### Sistema de Recomendación (HU2)
```
POST   /api/users/workers/recommend/                  # Búsqueda semántica
GET    /api/users/workers/recommendation-analytics/   # Métricas (admin)
GET    /api/users/workers/recommendation-health/      # Health check
```

### Portafolio Visual (HU4)
```
POST   /api/users/workers/portfolio/                  # Crear item de portfolio
GET    /api/users/workers/portfolio/                  # Listar portfolio propio
GET    /api/users/workers/{id}/portfolio/             # Portfolio público
PATCH  /api/users/workers/portfolio/{id}/             # Actualizar item
DELETE /api/users/workers/portfolio/{id}/             # Eliminar item
```

### WebSocket
```
ws://localhost:8000/ws/chat/{order_id}/?token=<jwt_token>
```

---

## 🤖 Sistema de Recomendación - Quick Start

### 1. Búsqueda Semántica

**Request:**
```bash
curl -X POST http://localhost:8000/api/users/workers/recommend/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "query": "Necesito plomero urgente para reparar fuga de agua",
    "strategy": "hybrid",
    "top_n": 5,
    "min_rating": 4.0,
    "latitude": 4.7110,
    "longitude": -74.0721,
    "max_distance_km": 15
  }'
```

**Response:**
```json
{
  "query": "Necesito plomero urgente para reparar fuga de agua",
  "processed_query": "necesito plomero urgente reparar fuga agua fontanero goteo",
  "strategy_used": "hybrid",
  "recommendations": [
    {
      "id": 12,
      "user": {
        "email": "juan@example.com",
        "first_name": "Juan",
        "last_name": "Pérez"
      },
      "profession": "Plomero",
      "bio": "Plomero con 10 años de experiencia. Especializado en reparaciones urgentes de fugas...",
      "rating": 4.8,
      "completed_orders": 156,
      "latitude": "4.6980",
      "longitude": "-74.0820",
      "score": 0.87,
      "relevance_percentage": 87,
      "distance_km": 2.4,
      "explanation": {
        "matched_keywords": ["plomero", "urgente", "fuga", "reparaciones"],
        "score_breakdown": {
          "tfidf_score": 0.92,
          "rating_normalized": 0.96,
          "proximity_normalized": 0.85,
          "final_score": 0.87
        }
      }
    }
  ],
  "total_results": 5,
  "performance_ms": 45,
  "log_id": 1234
}
```

### 2. Estrategias Disponibles

| Estrategia | Descripción | Cuándo usar |
|------------|-------------|-------------|
| **tfidf** | ML puro basado en similitud semántica | Query descriptiva y detallada |
| **fallback** | Geo-proximidad + rating (sin ML) | Query genérica o corpus pequeño |
| **hybrid** | 50% TF-IDF + 30% rating + 20% proximidad | Balancear relevancia + calidad + cercanía (recomendado) |

### 3. Analytics Dashboard

```bash
curl -X GET http://localhost:8000/api/users/workers/recommendation-analytics/ \
  -H "Authorization: Bearer <admin_token>"
```

**Response:**
```json
{
  "total_searches": 1523,
  "unique_users": 342,
  "avg_results_per_search": 4.2,
  "cache_hit_rate": 0.78,
  "avg_response_time_ms": 52,
  "click_through_rate": 0.34,
  "mean_reciprocal_rank": 0.68,
  "a_b_test_results": {
    "tfidf": {"searches": 507, "ctr": 0.29, "mrr": 0.65},
    "fallback": {"searches": 498, "ctr": 0.31, "mrr": 0.63},
    "hybrid": {"searches": 518, "ctr": 0.42, "mrr": 0.75}
  },
  "corpus_health": {
    "total_workers": 156,
    "workers_with_bio": 142,
    "coverage_percentage": 0.91
  }
}
```

### 4. Health Check

```bash
curl http://localhost:8000/api/users/workers/recommendation-health/
```

**Response:**
```json
{
  "status": "healthy",
  "model_trained": true,
  "cache_connected": true,
  "workers_count": 156,
  "last_training": "2026-01-26T10:30:00Z",
  "avg_response_time_ms": 48
}
```

### 5. Management Commands

```bash
# Descargar recursos NLP (stopwords español, tokenizers)
python manage.py setup_nlp

# Validar calidad del corpus
python manage.py validate_corpus --detailed

# Entrenar modelo TF-IDF (ejecutar después de agregar/actualizar trabajadores)
python manage.py train_recommendation_model

# Ver ayuda de cada comando
python manage.py <command> --help
```

### 6. Métricas y Monitoreo

**Métricas clave:**
- **CTR (Click-Through Rate):** % de búsquedas que generan clic en un trabajador
- **MRR (Mean Reciprocal Rank):** Posición promedio del trabajador clickeado (1/posición)
- **Cache Hit Rate:** % de queries servidas desde Redis cache
- **Response Time:** Latencia promedio de búsquedas

**Logs automáticos:**
Cada búsqueda se registra en `RecommendationLog` con:
- Query original + procesada
- Estrategia utilizada
- Resultados devueltos
- Performance (ms)
- User engagement (clicks, conversiones)

### 7. Producción - Reentrenamiento Automático

Agregar cronjob para reentrenar modelo diariamente:

```bash
# Editar crontab
crontab -e

# Agregar línea (reentrenar a las 2 AM)
0 2 * * * cd /path/to/project && /path/to/venv/bin/python manage.py train_recommendation_model
```

### 8. Testing

```bash
# Unit tests (motor de recomendación)
python manage.py test users.tests.test_recommendation_engine

# Integration tests (API endpoints)
python manage.py test users.tests.test_recommendation_api

# Todos los tests
python manage.py test users.tests
```

### 9. Troubleshooting

**Error: "NLTK stopwords not found"**
```bash
python manage.py setup_nlp
```

**Error: "No trained model found"**
```bash
# Entrenar modelo inicial
python manage.py train_recommendation_model

# Verificar cache
redis-cli -n 1 GET ':1:recommendation_model_data'
```

**Resultados irrelevantes:**
```bash
# Validar corpus
python manage.py validate_corpus --detailed

# Si hay bios vacías, usar --fix-empty
python manage.py validate_corpus --fix-empty
```

---

## � Portafolio Visual - Quick Start

### 1. Subir Foto de Proyecto

**Request:**
```bash
curl -X POST http://localhost:8000/api/users/workers/portfolio/ \
  -H "Authorization: Bearer <worker_token>" \
  -F "title=Remodelación de Cocina" \
  -F "description=Proyecto completo de remodelación con instalación de muebles y acabados" \
  -F "image=@foto_proyecto.jpg"
```

**Response:**
```json
{
  "id": 1,
  "title": "Remodelación de Cocina",
  "description": "Proyecto completo de remodelación con instalación de muebles y acabados",
  "image": "/media/portfolio/worker_12/remodelacion_cocina.jpg",
  "image_url": "http://localhost:8000/media/portfolio/worker_12/remodelacion_cocina.jpg",
  "created_at": "2026-02-10T15:30:00Z"
}
```

### 2. Características del Sistema

- ✅ **Compresión automática:** Imágenes >1600px se redimensionan manteniendo aspect ratio
- ✅ **Optimización de calidad:** JPEG 80%, WebP 80%, PNG optimizado
- ✅ **Validaciones robustas:** Tamaño máximo 5MB, formatos permitidos (JPG, PNG, WEBP)
- ✅ **Storage flexible:** Desarrollo local + producción S3
- ✅ **Permisos granulares:** Solo WORKER puede crear, lectura pública para todos

### 3. Ver Portfolio Público

```bash
curl http://localhost:8000/api/users/workers/12/portfolio/
```

**Response:**
```json
[
  {
    "id": 1,
    "title": "Remodelación de Cocina",
    "description": "Proyecto completo de remodelación...",
    "image_url": "http://localhost:8000/media/portfolio/worker_12/remodelacion_cocina.jpg",
    "created_at": "2026-02-10T15:30:00Z"
  },
  {
    "id": 2,
    "title": "Instalación Eléctrica Residencial",
    "description": "Cableado completo para casa de 3 pisos...",
    "image_url": "http://localhost:8000/media/portfolio/worker_12/instalacion_electrica.jpg",
    "created_at": "2026-02-08T10:15:00Z"
  }
]
```

### 4. Actualizar/Eliminar Items

**Actualizar:**
```bash
curl -X PATCH http://localhost:8000/api/users/workers/portfolio/1/ \
  -H "Authorization: Bearer <worker_token>" \
  -F "title=Remodelación Completa de Cocina Moderna"
```

**Eliminar:**
```bash
curl -X DELETE http://localhost:8000/api/users/workers/portfolio/1/ \
  -H "Authorization: Bearer <worker_token>"
```

### 5. Configuración de Storage

**Desarrollo (local):**
```python
# settings.py
USE_S3 = False
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'
```

**Producción (S3):**
```env
# .env
USE_S3=True
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=findmyworker-media
AWS_S3_REGION_NAME=us-east-1
```

### 6. Testing

```bash
# Tests completos de portfolio (24 tests)
python manage.py test users.tests.test_portfolio -v 2

# Tests específicos
python manage.py test users.tests.test_portfolio.ImageValidatorTests
python manage.py test users.tests.test_portfolio.PortfolioPermissionsTests
python manage.py test users.tests.test_portfolio.PortfolioEndpointTests
```

### 7. Estructura de Almacenamiento

```
media/
└── portfolio/
    ├── worker_12/
    │   ├── remodelacion_cocina.jpg
    │   └── instalacion_electrica.jpg
    ├── worker_45/
    │   └── proyecto_fontaneria.jpg
    └── worker_78/
        ├── pintura_exterior.jpg
        └── carpinteria_muebles.webp
```

---
## ✅ Historias de Usuario Implementadas

- [x] **HU1:** Exploración Avanzada de Trabajadores
- [x] **HU2:** Búsqueda Semántica Inteligente (IA TF-IDF)
- [x] **HU3:** Mapa Interactivo de Talentos (GeoDjango)
- [x] **HU4:** Portafolio Visual de Evidencias
- [x] **HU5:** Flujo de Contratación con Pagos
- [x] **HU6:** Chat en Tiempo Real (WebSockets)
- [x] **HU7:** Sistema de Reputación
- [ ] **HU8:** Tablero de Control Administrativo (En desarrollo)

---
## �📚 Documentación Técnica

Para detalles de arquitectura, decisiones técnicas y fundamentos teóricos:

📖 [RECOMMENDATION_ARCHITECTURE.md](docs/RECOMMENDATION_ARCHITECTURE.md) - Sistema de recomendación inteligente

📖 [FRONTEND_API_SPEC.md](docs/FRONTEND_API_SPEC.md) - Especificación completa de API para frontend

📖 [TECHNICAL_DECISIONS.md](docs/TECHNICAL_DECISIONS.md) - Decisiones técnicas y patrones aplicados

---

## 👥 Contribuidores

- Anuarth Rincon - [@anuarthr](https://github.com/anuarthr)
