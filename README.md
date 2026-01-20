# FindMyWorker Backend

Backend para plataforma de conexión entre clientes y trabajadores freelance.

## Características

- Autenticación JWT
- Gestión de órdenes de servicio
- Registro de horas trabajadas
- Chat en tiempo real (WebSocket)
- Búsqueda de trabajadores por ubicación

## Tecnologías

- Django 4.x + Django REST Framework
- Django Channels (WebSocket)
- PostgreSQL + PostGIS
- Redis
- Simple JWT

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

```
POST /api/users/register/
POST /api/users/token/
GET  /api/users/me/

GET    /api/orders/
POST   /api/orders/
GET    /api/orders/{id}/
PATCH  /api/orders/{id}/status/

POST /api/orders/{id}/work-hours/
POST /api/orders/{id}/work-hours/{log_id}/approve/

ws://localhost:8000/ws/chat/{order_id}/?token=<jwt_token>
```
