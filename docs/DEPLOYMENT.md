# Despliegue - FindMyWorker Backend (Render + Supabase + S3)

Guía para desplegar el backend (Django + GeoDjango + Channels) con Docker en Render,
usando Supabase para Postgres/PostGIS y AWS S3 para media.

## Arquitectura de producción

| Componente | Servicio | Notas |
|------------|----------|-------|
| API + WebSockets | Render (Docker, uvicorn ASGI) | Sirve HTTP y `ws://` en el mismo proceso |
| Base de datos | Supabase Postgres + PostGIS | Conexión **directa** (puerto 5432) |
| Redis | Render Key Value (o Upstash) | Channels transport + cache TF-IDF |
| Media (avatars/portfolio) | AWS S3 | `USE_S3=True` |
| Static (admin) | S3 o WhiteNoise | Según `USE_S3` |

## 1. Base de datos (Supabase)

1. Crea el proyecto en Supabase.
2. En el SQL Editor, habilita PostGIS:
   ```sql
   create extension if not exists postgis;
   ```
3. Copia la cadena de conexión **directa** (Settings → Database → Connection string → URI,
   puerto **5432**, no el pooler 6543). El pooler en modo *transaction* puede romper
   migraciones y consultas GIS.
4. Úsala como `DATABASE_URL`.

## 2. Redis

- **Opción A (incluida en `render.yaml`):** servicio Key Value de Render. `REDIS_URL`
  se inyecta automáticamente vía `fromService`.
- **Opción B (Upstash):** crea una base Redis, copia la URL `rediss://...` y ponla
  manualmente en `REDIS_URL` (borra el servicio `keyvalue` del blueprint).

## 3. AWS S3

1. Crea un bucket (capa gratuita) en tu región.
2. Desbloquea acceso público de lectura para los objetos servidos (o usa CloudFront
   y define `AWS_S3_CUSTOM_DOMAIN`).
3. Crea un usuario IAM con permisos `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`
   y `s3:ListBucket` sobre ese bucket.
4. Variables: `USE_S3=True`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
   `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`.
5. Verifica la conexión (en local o en una shell del contenedor):
   ```bash
   USE_S3=True python manage.py check_s3
   ```

## 4. Render

### Con Blueprint (recomendado)
1. Sube el repo a GitHub.
2. En Render: **New → Blueprint**, apunta al repo. Detecta `render.yaml`.
3. Completa las variables `sync: false`: `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
   `CORS_ALLOWED_ORIGINS`, `DATABASE_URL`, y las de AWS.
   - `ALLOWED_HOSTS`: el host de Render, p.ej. `findmyworker-backend.onrender.com`
   - `CSRF_TRUSTED_ORIGINS`: `https://findmyworker-backend.onrender.com`
   - `CORS_ALLOWED_ORIGINS`: el dominio del frontend.
4. Deploy. El `entrypoint.sh` corre `migrate` + `collectstatic` + warm-up del modelo
   y arranca uvicorn.

### Sin Blueprint
Crea un Web Service tipo **Docker**, deja el `Dockerfile` por defecto y añade las mismas
variables de entorno manualmente.

## 5. Post-deploy

```bash
# Crear superusuario (Render Shell del servicio)
python manage.py createsuperuser

# (Opcional) Cargar datos de prueba y entrenar el modelo
python manage.py train_recommendation_model
```

## Variables de entorno

Ver `.env.example` para la lista completa y comentada. Mínimas en producción:

```
SECRET_KEY=...            # generado
DEBUG=False
ALLOWED_HOSTS=tu-app.onrender.com
CSRF_TRUSTED_ORIGINS=https://tu-app.onrender.com
CORS_ALLOWED_ORIGINS=https://tu-frontend.com
DATABASE_URL=postgresql://...:5432/postgres
REDIS_URL=redis://...     # o inyectado por Render
USE_S3=True
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=...
AWS_S3_REGION_NAME=...
```

## Notas

- **HTTPS detrás de proxy:** en producción se activa `SECURE_PROXY_SSL_HEADER`, así que
  `SECURE_SSL_REDIRECT` no entra en bucle. Si tu proxy no envía `X-Forwarded-Proto`,
  pon `SECURE_SSL_REDIRECT=False`.
- **GeoDjango:** la imagen instala GDAL/GEOS/PROJ; no necesitas configurar rutas de
  librerías manualmente en Debian bookworm.
- **WebSockets:** uvicorn sirve `ws://.../ws/chat/{order_id}/?token=<jwt>` en el mismo
  puerto que la API.
