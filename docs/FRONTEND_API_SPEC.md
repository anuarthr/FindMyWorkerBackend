# FindMyWorker - Frontend API Documentation

Esta es la documentación completa de la API REST para su uso en el frontend. Incluye todos los endpoints disponibles, estructuras de datos, ejemplos de uso, y códigos de error.

**Base URL:** `http://localhost:8000` (desarrollo) | `https://api.findmyworker.com` (producción)

**Última actualización:** 2026-02-23

---

## 📑 Tabla de Contenidos

1. [Autenticación](#1-autenticación)
2. [Usuarios](#2-usuarios)
3. [Trabajadores (Búsqueda Pública)](#3-trabajadores-búsqueda-pública)
4. [Portafolio Visual](#4-portafolio-visual)
5. [Sistema de Recomendación IA](#5-sistema-de-recomendación-ia)
6. [Órdenes de Servicio](#6-órdenes-de-servicio)
7. [Registro de Horas](#7-registro-de-horas)
8. [Mensajería](#8-mensajería)
9. [Reseñas](#9-reseñas)
10. [WebSockets (Chat en Tiempo Real)](#10-websockets)
11. [Códigos de Error](#11-códigos-de-error)
12. [Rate Limiting](#12-rate-limiting)
13. [Paginación](#13-paginación)
14. [Notas Importantes](#14-notas-importantes)
15. [Contacto y Soporte](#15-contacto-y-soporte)

---

## 1. Autenticación

Todos los endpoints (excepto los marcados como públicos) requieren autenticación JWT.

### 1.1 Registro de Usuario

```http
POST /api/auth/register/
```

**Request Body:**

```json
{
  "email": "usuario@example.com",
  "password": "contraseña_segura",
  "first_name": "Juan",
  "last_name": "Pérez",
  "role": "CLIENT"  // "CLIENT" | "WORKER"
}
```

**Response (201 Created):**

```json
{
  "email": "usuario@example.com",
  "first_name": "Juan",
  "last_name": "Pérez",
  "role": "CLIENT",
  "worker_profile": null  // ID del perfil si role=WORKER
}
```

---

### 1.2 Login (Obtener Token)

```http
POST /api/auth/login/
```

**Request Body:**

```json
{
  "email": "usuario@example.com",
  "password": "contraseña"
}
```

**Response (200 OK):**

```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Uso del Token:**

```javascript
fetch('/api/users/me/', {
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
});
```

---

### 1.3 Refresh Token

```http
POST /api/auth/refresh/
```

**Request Body:**

```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**

```json
{
  "access": "nuevo_access_token..."
}
```

---

### 1.4 Cambiar Contraseña

```http
POST /api/auth/change-password/
```

**Headers:** `Authorization: Bearer {token}` (requiere autenticación)

**Request Body:**

```json
{
  "old_password": "contraseña_actual",
  "new_password": "nueva_contraseña_segura",
  "confirm_password": "nueva_contraseña_segura"
}
```

**Response (200 OK):**

```json
{
  "detail": "Contraseña actualizada exitosamente."
}
```

**Errores comunes:**

- **400 Bad Request** - Contraseña actual incorrecta:

  ```json
  {
    "old_password": ["La contraseña actual es incorrecta."]
  }
  ```
- **400 Bad Request** - Contraseñas no coinciden:

  ```json
  {
    "confirm_password": ["Las contraseñas no coinciden."]
  }
  ```
- **400 Bad Request** - Nueva contraseña igual a la actual:

  ```json
  {
    "new_password": ["La nueva contraseña debe ser diferente a la actual."]
  }
  ```
- **400 Bad Request** - Contraseña muy corta:

  ```json
  {
    "new_password": ["Ensure this field has at least 8 characters."]
  }
  ```

---

### 1.5 Solicitar Reset de Contraseña

```http
POST /api/auth/password-reset/
```

**Público** - No requiere autenticación

**Request Body:**

```json
{
  "email": "usuario@example.com"
}
```

**Response (200 OK):**

```json
{
  "detail": "Si el email existe, recibirás instrucciones para resetear tu contraseña.",
  "dev_token": "abc123...",  // SOLO EN DESARROLLO - Remover en producción
  "dev_uid": "MQ"             // SOLO EN DESARROLLO - Remover en producción
}
```

**Notas importantes:**

- Por seguridad, siempre retorna 200 OK aunque el email no exista
- En producción, el token se envía por email (pendiente de implementación)
- `dev_token` y `dev_uid` solo aparecen en desarrollo para testing

---

### 1.6 Confirmar Reset de Contraseña

```http
POST /api/auth/password-reset-confirm/
```

**Público** - No requiere autenticación

**Request Body:**

```json
{
  "token": "token_recibido_por_email",
  "new_password": "nueva_contraseña_segura",
  "confirm_password": "nueva_contraseña_segura"
}
```

**Response (200 OK):**

```json
{
  "detail": "Contraseña restablecida exitosamente."
}
```

**Errores comunes:**

- **400 Bad Request** - Token inválido o expirado:

  ```json
  {
    "detail": "Token inválido o expirado."
  }
  ```
- **400 Bad Request** - Contraseñas no coinciden:

  ```json
  {
    "confirm_password": ["Las contraseñas no coinciden."]
  }
  ```

**Notas:**

- El token solo es válido una vez
- Los tokens expiran cuando el usuario cambia su contraseña
- Usuarios desactivados no pueden resetear contraseña

---

## 2. Usuarios

### 2.1 Obtener Perfil Actual

```http
GET /api/users/me/
```

**Headers:** `Authorization: Bearer {token}`

**Response (200 OK):**

```json
{
  "id": 1,
  "email": "usuario@example.com",
  "first_name": "Juan",
  "last_name": "Pérez",
  "role": "CLIENT",
  "avatar": "http://example.com/media/avatars/juan.jpg",
  "phone_number": "+52 333 123 4567",
  "address": "Calle Principal 123",
  "city": "Guadalajara",
  "state": "Jalisco",
  "country": "México",
  "postal_code": "44100"
}
```

**Nuevos campos de contacto (todos opcionales):**

- `phone_number` (string): Número de teléfono
- `address` (string): Dirección física
- `city` (string): Ciudad
- `state` (string): Estado/Provincia
- `country` (string): País (default: "México")
- `postal_code` (string): Código postal

---

### 2.2 Actualizar Perfil

```http
PUT /api/users/me/
PATCH /api/users/me/
```

**Headers:** `Authorization: Bearer {token}`

**Request Body (PATCH ejemplo):**

```json
{
  "first_name": "Juan Carlos",
  "last_name": "Pérez López",
  "phone_number": "+52 333 123 4567",
  "address": "Calle Principal 123, Apt 5B",
  "city": "Guadalajara",
  "state": "Jalisco",
  "country": "México",
  "postal_code": "44100"
}
```

**Response (200 OK):** Mismo formato que GET

**Campos de solo lectura (no se pueden modificar):**

- `id`
- `email`
- `role`

**Notas:**

- Todos los campos de contacto son opcionales
- Puedes actualizar solo los campos que necesites con PATCH
- El avatar se puede subir como archivo multipart/form-data

---

### 2.3 Perfil de Trabajador

```http
GET /api/workers/me/
PUT /api/workers/me/
```

**Headers:** `Authorization: Bearer {token}` (solo usuarios con role=WORKER)

**GET Response:**

```json
{
  "id": 5,
  "user": {
    "id": 1,
    "email": "trabajador@example.com",
    "first_name": "María",
    "last_name": "González",
    "role": "WORKER",
    "avatar": null
  },
  "profession": "PLUMBER",
  "bio": "Plomera con 8 años de experiencia...",
  "years_experience": 8,
  "hourly_rate": "350.00",
  "is_verified": true,
  "average_rating": 4.7,
  "latitude": -12.046373,
  "longitude": -77.042754
}
```

**PUT Request:**

```json
{
  "profession": "ELECTRICIAN",
  "bio": "Nueva biografía...",
  "years_experience": 10,
  "hourly_rate": "400.00",
  "latitude": -12.046373,
  "longitude": -77.042754
}
```

**Profesiones disponibles:**

- `PLUMBER` - Plomería
- `ELECTRICIAN` - Electricista
- `CARPENTER` - Carpintería
- `PAINTER` - Pintura
- `MASON` - Albañilería
- `PAINTER` - Pintura
- `CARPENTER` - Carpintería
- `OTHER` - Otro

---

## 3. Trabajadores (Búsqueda Pública)

### 3.1 Listar Trabajadores

```http
GET /api/workers/
```

**Público** - No requiere autenticación

**Query Parameters:**

- `search` (string): Búsqueda por nombre o profesión
- `profession` (string): Filtrar por profesión (PLUMBER, ELECTRICIAN, etc.)
- `min_rating` (float): Rating mínimo (0-5)
- `page` (int): Número de página
- `page_size` (int): Resultados por página (default: 10, max: 100)

**Ejemplo:**

```
GET /api/workers/?profession=PLUMBER&min_rating=4.0&page=1&page_size=20
```

**Response (200 OK):**

```json
{
  "count": 45,
  "next": "http://api.../workers/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "user": {
        "first_name": "Juan",
        "last_name": "Pérez",
        "avatar": null
      },
      "profession": "PLUMBER",
      "bio": "Plomero certificado...",
      "years_experience": 5,
      "hourly_rate": "300.00",
      "average_rating": 4.5,
      "latitude": -12.046373,
      "longitude": -77.042754
    }
  ]
}
```

---

### 3.2 Detalle de Trabajador

```http
GET /api/workers/{id}/
```

**Público**

**Response (200 OK):** Mismo formato que item en lista

---

## 4. Portafolio Visual

Sistema de gestión de portafolio fotográfico para trabajadores. Permite subir imágenes de proyectos con compresión automática, validación de formatos y almacenamiento optimizado. **NUEVO:** Soporta asociación con órdenes completadas de la plataforma para verificación de trabajos.

### 4.1 Crear Item de Portafolio

```http
POST /api/users/workers/portfolio/
```

**Requiere autenticación:** ✅ (Solo rol WORKER)

**Content-Type:** `multipart/form-data`

**Request Body (Form Data):**

| Campo           | Tipo    | Requerido | Descripción                                                    |
| --------------- | ------- | --------- | --------------------------------------------------------------- |
| `title`       | string  | ✅        | Título del proyecto (max 255 caracteres)                       |
| `description` | string  | ❌        | Descripción detallada del proyecto                             |
| `image`       | file    | ✅        | Imagen del proyecto (max 5MB, JPG/PNG/WEBP)                     |
| `order`       | integer | ❌        | ID de orden completada (solo órdenes COMPLETED del trabajador) |

**Ejemplo con JavaScript (Fetch):**

```javascript
// Opción 1: Trabajo externo (sin asociar orden)
const formData = new FormData();
formData.append('title', 'Remodelación de Cocina');
formData.append('description', 'Proyecto completo de remodelación con instalación de muebles y acabados');
formData.append('image', fileInput.files[0]);

// Opción 2: Trabajo de la plataforma (con orden asociada)
// formData.append('order', orderId); // ID de orden COMPLETED

fetch('http://localhost:8000/api/users/workers/portfolio/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`
  },
  body: formData
})
.then(res => res.json())
.then(data => console.log(data));
```

**Response (201 Created):**

```json
// Trabajo externo (sin orden asociada)
{
  "id": 1,
  "title": "Remodelación de Cocina",
  "description": "Proyecto completo de remodelación con instalación de muebles y acabados",
  "image": "/media/portfolio/worker_12/remodelacion_cocina.jpg",
  "image_url": "http://localhost:8000/media/portfolio/worker_12/remodelacion_cocina.jpg",
  "order": null,
  "is_external_work": true,
  "order_info": null,
  "created_at": "2026-02-10T15:30:00Z"
}

// Trabajo de la plataforma (con orden asociada) - ¡VERIFICADO! ✓
{
  "id": 2,
  "title": "Reparación de Tubería",
  "description": "Trabajo completado para cliente de la plataforma",
  "image_url": "http://localhost:8000/media/portfolio/worker_12/tuberia.jpg",
  "order": 45,
  "is_external_work": false,
  "order_info": {
    "id": 45,
    "client_name": "María García",
    "description": "Reparación urgente de fuga en baño",
    "status": "COMPLETED",
    "updated_at": "2026-02-09T18:30:00Z"
  },
  "created_at": "2026-02-10T15:30:00Z"
}
```

**Validaciones:**

- ✅ Título no vacío (sin solo espacios)
- ✅ Imagen máximo 5MB
- ✅ Formatos permitidos: JPG, PNG, WEBP
- ✅ Compresión automática si width > 1600px
- ✅ Solo rol WORKER puede crear
- ✅ Orden (si provista) debe estar COMPLETED
- ✅ Orden (si provista) debe pertenecer al trabajador
- ✅ `is_external_work` se auto-establece (false si hay orden, true si no)

**Errores comunes:**

```json
// 400 - Título vacío
{
  "title": ["El título no puede estar vacío o contener solo espacios."]
}

// 400 - Imagen muy grande
{
  "image": ["El archivo no debe exceder 5.0 MB."]
}

// 400 - Formato no permitido
{
  "image": ["Extensión de archivo no permitida: .gif. Use: .jpg, .png o .webp"]
}

// 400 - Orden no completada
{
  "order": ["Solo puedes asociar órdenes con estado COMPLETED."]
}

// 400 - Orden de otro trabajador
{
  "order": ["Solo puedes asociar tus propias órdenes."]
}

// 403 - Usuario no es WORKER
{
  "detail": "No tienes permiso para realizar esta acción."
}
```

---

### 4.2 Listar Portfolio Propio

```http
GET /api/users/workers/portfolio/
```

**Requiere autenticación:** ✅ (Solo rol WORKER)

**Response (200 OK):**

```json
[
  {
    "id": 1,
    "title": "Remodelación de Cocina",
    "description": "Proyecto completo de remodelación...",
    "image": "/media/portfolio/worker_12/remodelacion_cocina.jpg",
    "image_url": "http://localhost:8000/media/portfolio/worker_12/remodelacion_cocina.jpg",
    "order": null,
    "is_external_work": true,
    "order_info": null,
    "created_at": "2026-02-10T15:30:00Z"
  },
  {
    "id": 2,
    "title": "Instalación Eléctrica Residencial",
    "description": "Cableado completo para casa de 3 pisos...",
    "image_url": "http://localhost:8000/media/portfolio/worker_12/instalacion_electrica.jpg",
    "order": 52,
    "is_external_work": false,
    "order_info": {
      "id": 52,
      "client_name": "Carlos Mendoza",
      "status": "COMPLETED"
    },
    "created_at": "2026-02-08T10:15:00Z"
  }
]
```

**Ordenamiento:** Por fecha de creación (más reciente primero)

---

### 4.3 Ver Portfolio Público de Trabajador

```http
GET /api/users/workers/{worker_id}/portfolio/
```

**Público:** ✅ (No requiere autenticación)

**Path Parameters:**

| Param         | Tipo    | Descripción         |
| ------------- | ------- | -------------------- |
| `worker_id` | integer | ID del WorkerProfile |

**Response (200 OK):** Mismo formato que 4.2

**Ejemplo:**

```javascript
// Ver portfolio del trabajador con ID 12
fetch('http://localhost:8000/api/users/workers/12/portfolio/')
  .then(res => res.json())
  .then(portfolio => {
    portfolio.forEach(item => {
      console.log(item.title, item.image_url);
    });
  });
```

---

### 4.4 Actualizar Item de Portafolio

```http
PATCH /api/users/workers/portfolio/{id}/
```

**Requiere autenticación:** ✅ (Solo dueño WORKER)

**Content-Type:** `multipart/form-data`

**Request Body (Form Data):** Todos los campos son opcionales

| Campo           | Tipo   | Descripción                         |
| --------------- | ------ | ------------------------------------ |
| `title`       | string | Nuevo título                        |
| `description` | string | Nueva descripción                   |
| `image`       | file   | Nueva imagen (reemplaza la anterior) |

**Response (200 OK):**

```json
{
  "id": 1,
  "title": "Remodelación Completa de Cocina Moderna",
  "description": "Proyecto completo de remodelación...",
  "image_url": "http://localhost:8000/media/portfolio/worker_12/remodelacion_cocina.jpg",
  "created_at": "2026-02-10T15:30:00Z"
}
```

**Errores:**

```json
// 403 - No es el dueño
{
  "detail": "No tienes permiso para realizar esta acción."
}

// 404 - Item no existe
{
  "detail": "No encontrado."
}
```

---

### 4.5 Eliminar Item de Portafolio

```http
DELETE /api/users/workers/portfolio/{id}/
```

**Requiere autenticación:** ✅ (Solo dueño WORKER)

**Response (204 No Content):** Sin body

**Ejemplo:**

```javascript
fetch('http://localhost:8000/api/users/workers/portfolio/1/', {
  method: 'DELETE',
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
})
.then(res => {
  if (res.status === 204) {
    console.log('Item eliminado exitosamente');
  }
});
```

---

### 4.6 Obtener Órdenes Completadas Sin Portfolio

```http
GET /api/orders/workers/me/completed-without-portfolio/
```

**Requiere autenticación:** ✅ (Solo rol WORKER)

**Descripción:** Retorna las órdenes completadas del trabajador que aún no tienen un item de portfolio asociado. Útil para mostrar un dropdown/selector al crear portfolio.

**Response (200 OK):**

```json
[
  {
    "id": 45,
    "client_name": "María García",
    "description": "Reparación urgente de fuga en baño",
    "status": "COMPLETED",
    "updated_at": "2026-02-09T18:30:00Z"
  },
  {
    "id": 48,
    "client_name": "Pedro López",
    "description": "Instalación de sistema de riego",
    "status": "COMPLETED",
    "updated_at": "2026-02-07T14:20:00Z"
  }
]
```

**Ejemplo de uso (React):**

```javascript
function PortfolioUploadModal() {
  const [availableOrders, setAvailableOrders] = useState([]);
  const [selectedOrder, setSelectedOrder] = useState(null);

  useEffect(() => {
    // Cargar órdenes disponibles
    fetch('http://localhost:8000/api/orders/workers/me/completed-without-portfolio/', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(data => setAvailableOrders(data));
  }, []);

  const handleSubmit = () => {
    const formData = new FormData();
    formData.append('title', title);
    formData.append('description', description);
    formData.append('image', imageFile);
  
    // Asociar orden si se seleccionó (trabajo verificado)
    if (selectedOrder) {
      formData.append('order', selectedOrder.id);
    }
  
    // POST request...
  };

  return (
    <div>
      <input type="text" placeholder="Título" />
      <textarea placeholder="Descripción" />
      <input type="file" accept="image/*" />
    
      {/* Selector de orden (opcional) */}
      <select onChange={(e) => setSelectedOrder(availableOrders[e.target.value])}>
        <option value="">Trabajo externo (no verificado)</option>
        {availableOrders.map((order, idx) => (
          <option key={order.id} value={idx}>
            {order.client_name} - {order.description}
          </option>
        ))}
      </select>
    
      <button onClick={handleSubmit}>Subir</button>
    </div>
  );
}
```

**Filtros aplicados automáticamente:**

- ✅ Solo órdenes del trabajador autenticado
- ✅ Solo órdenes con estado `COMPLETED`
- ✅ Solo órdenes sin portfolio asociado
- 📅 Ordenadas por fecha de actualización (más recientes primero)

---

### 4.7 Notas de Implementación

**Compresión Automática:**

- Imágenes >1600px de ancho se redimensionan automáticamente
- Mantiene aspect ratio original
- Calidad: JPEG 80%, WebP 80%, PNG optimizado
- Conversión RGBA → RGB para compatibilidad

**Storage:**

- **Desarrollo:** Archivos en `/media/portfolio/worker_{id}/`
- **Producción:** S3 bucket configurado en `settings.py`

**Permisos:**

- **POST:** Solo WORKER autenticado
- **GET (propio):** Solo WORKER autenticado
- **GET (público):** Cualquiera (sin autenticación)
- **PATCH/DELETE:** Solo dueño WORKER

**Badge Verificado UI:**

Mostrar badge "✓ Verificado" cuando `is_external_work === false`:

```javascript
function PortfolioCard({ item }) {
  return (
    <div className="portfolio-card">
      <img src={item.image_url} alt={item.title} />
      <h3>
        {item.title}
        {!item.is_external_work && (
          <span className="verified-badge">✓ Verificado</span>
        )}
      </h3>
      {item.order_info && (
        <p className="client-info">
          Cliente: {item.order_info.client_name}
        </p>
      )}
    </div>
  );
}
```

**Ejemplo de Galería UI:**

```javascript
// Cargar portfolio al ver perfil de trabajador
async function loadWorkerPortfolio(workerId) {
  const response = await fetch(
    `http://localhost:8000/api/users/workers/${workerId}/portfolio/`
  );
  const portfolio = await response.json();
  
  const gallery = document.getElementById('portfolio-gallery');
  portfolio.forEach(item => {
    const card = `
      <div class="portfolio-card">
        <img src="${item.image_url}" alt="${item.title}" />
        <h3>${item.title}</h3>
        <p>${item.description}</p>
        <small>${new Date(item.created_at).toLocaleDateString()}</small>
      </div>
    `;
    gallery.innerHTML += card;
  });
}
```

---

## 5. Sistema de Recomendación IA

Sistema de búsqueda semántica basado en Machine Learning (TF-IDF) que analiza biografías de trabajadores.

### 5.1 Búsqueda Semántica

```http
POST /api/users/workers/recommend/
```

**Público** (opcional: autenticado para tracking)

**Request Body:**

```json
{
  "query": "necesito un plomero urgente para reparar fuga de agua",
  "language": "es",
  "strategy": "hybrid",
  "top_n": 5,
  
  "latitude": -12.046373,
  "longitude": -77.042754,
  "max_distance_km": 20,
  "min_rating": 4.0,
  "profession": "PLUMBER"
}
```

**Parámetros:**

| Campo               | Tipo   | Requerido | Default | Descripción                               |
| ------------------- | ------ | --------- | ------- | ------------------------------------------ |
| `query`           | string | ✅        | -       | Consulta en lenguaje natural (min 3 chars) |
| `language`        | string | ❌        | "es"    | "es" o "en" (solo "es" funcional)          |
| `strategy`        | string | ❌        | "tfidf" | "tfidf", "fallback", "hybrid"              |
| `top_n`           | int    | ❌        | 5       | Cantidad de resultados (1-20)              |
| `latitude`        | float  | ❌        | null    | Latitud del usuario                        |
| `longitude`       | float  | ❌        | null    | Longitud del usuario                       |
| `max_distance_km` | float  | ❌        | 50      | Radio de búsqueda en km                   |
| `min_rating`      | float  | ❌        | null    | Rating mínimo (0-5)                       |
| `profession`      | string | ❌        | null    | Filtrar por profesión                     |

**Response (200 OK):**

```json
{
  "query": "necesito un plomero urgente para reparar fuga de agua",
  "processed_query": "necesito plomero urgente reparar fuga agua",
  "strategy_used": "hybrid",
  "total_results": 3,
  
  "recommendations": [
    {
      "id": 1,
      "user": {
        "id": 45,
        "email": "juan@example.com",
        "first_name": "Juan",
        "last_name": "Pérez",
        "role": "WORKER",
        "avatar": null
      },
      "profession": "PLUMBER",
      "bio": "Plomero con 8 años de experiencia en reparaciones urgentes...",
      "years_experience": 8,
      "hourly_rate": "350.00",
      "is_verified": true,
      "average_rating": 4.7,
      "latitude": -12.0789,
      "longitude": -77.0234,
  
      // Campos de recomendación (planos para frontend)
      "recommendation_score": 0.8534,
      "matched_keywords": ["plomero", "reparaciones", "urgente", "fuga"],
      "explanation": "85% relevante - coincide con: plomero, reparaciones, urgente - a 4.7km",
  
      // Detalles completos (opcional, para análisis avanzado)
      "recommendation_details": {
        "semantic_similarity": 0.8534,
        "relevance_percentage": 85.34,
        "distance_km": 4.72,
        "distance_factor": 0.9156,
        "normalized_score": 0.7821,
        "matched_terms_count": 4
      }
    }
  ],
  
  "performance_ms": 52.3,
  "cache_hit": true,
  "log_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Errores Comunes:**

**400 Bad Request - Query muy corto:**

```json
{
  "query": ["La búsqueda debe tener al menos 3 caracteres"]
}
```

**400 Bad Request - Idioma no soportado:**

```json
{
  "language": ["Inglés no soportado actualmente. Use \"es\" para español. Funcionalidad en desarrollo."]
}
```

**503 Service Unavailable - Modelo no entrenado:**

```json
{
  "error": "Recommendation engine error",
  "detail": "Modelo no entrenado",
  "hint": "El modelo ML puede no estar entrenado. Ejecuta: python manage.py train_recommendation_model"
}
```

---

### 5.2 Health Check del Sistema IA

```http
GET /api/users/workers/recommendation-health/
```

**Público**

**Response (200 OK):**

```json
{
  "status": "ready",
  "model_trained": true,
  "corpus_size": 156,
  "vocabulary_size": 487,
  "model_last_trained": "2026-01-28T08:30:15Z",
  "cache_status": "connected",
  "avg_response_time_ms": 52.3,
  "recent_errors_count": 0,
  "recommendations": [],
  "checked_at": "2026-01-28T14:22:10Z"
}
```

**Estados Posibles:**

- `"ready"` - Sistema listo para uso (200)
- `"not_trained"` - Modelo sin entrenar (200)
- `"degraded"` - Funcional con warnings (200)
- `"unhealthy"` - Sistema con errores críticos (503)

---

### 5.3 Analytics (Solo Admins)

```http
GET /api/users/workers/recommendation-analytics/?days=30
```

**Headers:** `Authorization: Bearer {token}` (IsAdminUser)

**Query Parameters:**

- `days` (int): Rango de días para análisis (default: 30)

**Response (200 OK):**

```json
{
  "total_queries": 1523,
  "unique_users": 87,
  "avg_response_time_ms": 52.3,
  "cache_hit_rate": 0.78,
  "avg_results_per_query": 8.4,
  "avg_ctr": 0.42,
  "avg_conversion_rate": 0.18,
  "avg_mrr": 0.76,
  "top_query_terms": [
    {"term": "plomero", "count": 245},
    {"term": "electricista", "count": 189}
  ],
  "ab_test_results": {...},
  "corpus_health": {...},
  "date_range": {
    "from": "2025-12-29",
    "to": "2026-01-28"
  }
}
```

---

## 6. Órdenes de Servicio

### 6.1 Crear Orden

```http
POST /api/orders/
```

**Headers:** `Authorization: Bearer {token}` (role=CLIENT)

**Request Body:**

```json
{
  "worker": 5,
  "description": "Reparación de fuga en baño principal"
}
```

**Response (201 Created):**

```json
{
  "id": 42,
  "client": 1,
  "client_email": "cliente@example.com",
  "worker": 5,
  "worker_name": "María González",
  "worker_hourly_rate": "350.00",
  "description": "Reparación de fuga en baño principal",
  "status": "PENDING",
  "status_display": "Pending",
  "agreed_price": null,
  "created_at": "2026-01-28T10:30:00Z",
  "updated_at": "2026-01-28T10:30:00Z"
}
```

**Status Values:**

- `PENDING` - Pendiente (creada)
- `ACCEPTED` - Aceptada por trabajador
- `IN_ESCROW` - En depósito de garantía
- `COMPLETED` - Completada
- `CANCELLED` - Cancelada

---

### 6.2 Listar Órdenes

```http
GET /api/orders/list/
```

**Headers:** `Authorization: Bearer {token}`

**Query Parameters:**

- `status` (string): Filtrar por estado
- `role` (string): "client" | "worker" (auto-detectado por el token)
- `page` (int)
- `page_size` (int)

**Response:** Paginado similar a trabajadores

---

### 6.3 Detalle de Orden

```http
GET /api/orders/{id}/
```

**Headers:** `Authorization: Bearer {token}`

**Response:** Objeto completo de orden

---

### 6.4 Actualizar Estado

```http
PATCH /api/orders/{id}/status/
```

**Headers:** `Authorization: Bearer {token}`

**Request Body:**

```json
{
  "status": "IN_PROGRESS"
}
```

**Permisos:**

- Cliente: `PENDING` → `CANCELLED`
- Trabajador: `PENDING` → `ACCEPTED`, `ACCEPTED` → `IN_PROGRESS`, `IN_PROGRESS` → `COMPLETED`

---

### 6.5 Resumen de Precio

```http
GET /api/orders/{id}/price-summary/
```

**Headers:** `Authorization: Bearer {token}`

**Response (200 OK):**

```json
{
  "order_id": 42,
  "hourly_rate": "350.00",
  "total_hours": 5.5,
  "subtotal": "1925.00",
  "platform_fee": "96.25",
  "total": "2021.25",
  "currency": "PEN"
}
```

---

## 7. Registro de Horas

### 7.1 Listar Horas de una Orden

```http
GET /api/orders/{order_id}/work-hours/
```

**Headers:** `Authorization: Bearer {token}`

**Response (200 OK):**

```json
[
  {
    "id": 1,
    "order": 42,
    "date": "2026-01-28",
    "hours_worked": 3.5,
    "description": "Reparación de tubería principal",
    "status": "PENDING",
    "created_at": "2026-01-28T15:30:00Z"
  }
]
```

**Status Values:** `"PENDING"`, `"APPROVED"`, `"REJECTED"`

---

### 7.2 Registrar Horas

```http
POST /api/orders/{order_id}/work-hours/
```

**Headers:** `Authorization: Bearer {token}` (role=WORKER)

**Request Body:**

```json
{
  "date": "2026-01-28",
  "hours": 3.5,
  "description": "Reparación de tubería principal"
}
```

---

### 7.3 Aprobar Horas

```http
POST /api/orders/{order_id}/work-hours/{id}/approve/
```

**Headers:** `Authorization: Bearer {token}` (role=CLIENT, dueño de la orden)

**Response (200 OK):**

```json
{
  "id": 1,
  "status": "APPROVED",
  ...
}
```

---

## 8. Mensajería

### 8.1 Listar Mensajes de Orden

```http
GET /api/orders/{order_id}/messages/
```

**Headers:** `Authorization: Bearer {token}`

**Response (200 OK):**

```json
[
  {
    "id": 1,
    "order": 42,
    "sender": {
      "id": 1,
      "first_name": "Juan",
      "last_name": "Pérez"
    },
    "content": "Hola, ¿cuándo puedes venir?",
    "timestamp": "2026-01-28T10:35:00Z",
    "is_read": true
  }
]
```

---

### 8.2 Enviar Mensaje

```http
POST /api/orders/{order_id}/messages/
```

**Headers:** `Authorization: Bearer {token}`

**Request Body:**

```json
{
  "content": "Puedo ir mañana a las 10am"
}
```

**Nota:** Para chat en tiempo real, usa WebSockets (ver sección 9)

---

## 9. Reseñas

### 9.1 Crear Reseña

```http
POST /api/orders/{order_id}/review/
```

**Headers:** `Authorization: Bearer {token}` (role=CLIENT)

**Request Body:**

```json
{
  "rating": 5,
  "comment": "Excelente trabajo, muy profesional y puntual"
}
```

**Validaciones:**

- Rating: 1-5
- Solo se puede crear una reseña por orden
- La orden debe estar en estado `COMPLETED`

**Response (201 Created):**

```json
{
  "id": 10,
  "order": 42,
  "client": {...},
  "worker": {...},
  "rating": 5,
  "comment": "Excelente trabajo, muy profesional y puntual",
  "created_at": "2026-01-28T18:00:00Z"
}
```

---

### 9.2 Listar Reseñas de Trabajador

```http
GET /api/orders/workers/{worker_id}/reviews/
```

**Público**

**Query Parameters:**

- `page` (int)
- `page_size` (int)

**Response (200 OK):**

```json
{
  "count": 23,
  "average_rating": 4.7,
  "results": [
    {
      "id": 10,
      "client": {
        "first_name": "María",
        "last_name": "L."
      },
      "rating": 5,
      "comment": "Excelente trabajo...",
      "created_at": "2026-01-28T18:00:00Z"
    }
  ]
}
```

---

### 9.3 Obtener Reseña de Orden

```http
GET /api/orders/{order_id}/review/
```

**Headers:** `Authorization: Bearer {token}`

**Response (200 OK):** Objeto de reseña o `404` si no existe

---

### 9.4 Listar Todas las Reseñas (Público)

```http
GET /api/reviews/
```

**Público**

**Query Parameters:**

- `worker` (int): Filtrar por worker_id
- `min_rating` (int): Rating mínimo
- `page`, `page_size`

---

## 10. WebSockets

Para chat en tiempo real entre cliente y trabajador en una orden.

### 10.1 Conectar a Chat de Orden

```
ws://localhost:8000/ws/chat/{order_id}/
```

**Autenticación:** Token JWT en query parameter

```
ws://localhost:8000/ws/chat/42/?token=eyJhbGci...
```

**Ejemplo (JavaScript):**

```javascript
const orderId = 42;
const token = localStorage.getItem('access_token');
const ws = new WebSocket(
  `ws://localhost:8000/ws/chat/${orderId}/?token=${token}`
);

ws.onopen = () => {
  console.log('Conectado al chat');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Mensaje recibido:', data);
  // { type: 'chat_message', message: {...} }
};

// Enviar mensaje
ws.send(JSON.stringify({
  type: 'chat_message',
  message: 'Hola, ¿cómo estás?'
}));
```

**Mensajes Recibidos:**

```json
{
  "type": "chat_message",
  "message": {
    "id": 15,
    "sender": {
      "id": 1,
      "first_name": "Juan",
      "last_name": "Pérez"
    },
    "content": "Hola, ¿cómo estás?",
    "timestamp": "2026-01-28T10:35:00Z"
  }
}
```

**Errores de Conexión:**

- Token inválido → Cierra conexión
- Usuario no es parte de la orden → Cierra conexión
- Orden no existe → Cierra conexión

---

## 11. Códigos de Error

| Código | Significado           | Solución                             |
| ------- | --------------------- | ------------------------------------- |
| 400     | Bad Request           | Validar request body/params           |
| 401     | Unauthorized          | Token inválido/expirado, hacer login |
| 403     | Forbidden             | Sin permisos para este recurso        |
| 404     | Not Found             | Recurso no existe                     |
| 429     | Too Many Requests     | Rate limit excedido, esperar          |
| 500     | Internal Server Error | Error del servidor, reportar          |
| 503     | Service Unavailable   | Servicio temporalmente no disponible  |

**Formato de Error:**

```json
{
  "detail": "Descripción del error",
  "field_name": ["Error específico del campo"]
}
```

---

## 12. Rate Limiting

| Endpoint                               | Límite      | Periodo  |
| -------------------------------------- | ------------ | -------- |
| `/auth/login/`                       | 5 requests   | 1 minuto |
| `/auth/register/`                    | 3 requests   | 1 minuto |
| `/workers/recommend/`                | 60 requests  | 1 minuto |
| `/workers/recommendation-analytics/` | 10 requests  | 1 minuto |
| `/workers/recommendation-health/`    | 30 requests  | 1 minuto |
| Otros endpoints                        | 100 requests | 1 minuto |

**Error 429:**

```json
{
  "detail": "Request was throttled. Expected available in 45 seconds."
}
```

---

## 13. Paginación

Endpoints que retornan listas usan paginación estándar:

**Response:**

```json
{
  "count": 150,
  "next": "http://api.../endpoint/?page=2",
  "previous": null,
  "results": [...]
}
```

**Query Parameters:**

- `page` (int): Número de página (default: 1)
- `page_size` (int): Resultados por página (default: 10, max: 100)

---

## 14. Notas Importantes

### Idioma en Sistema de Recomendación

- **Solo español funcional actualmente**
- Parámetro `language` acepta `"es"` y `"en"`, pero inglés retorna error 400
- Razón: No hay corpus bilingüe, requiere traducción o biografías en ambos idiomas
- Ver: `docs/TECHNICAL_DECISIONS.md` TD-001

### Sinónimos NO Implementados

- El sistema NO expande sinónimos automáticamente
- "plomero" NO busca "fontanero", "gasfiter"
- Funcionalidad planificada para el futuro

### Campos Planos vs Detallados

- Endpoint de recomendación retorna ambos formatos
- **Usar campos planos** para UI simple: `recommendation_score`, `matched_keywords`, `explanation`
- **Usar `recommendation_details`** para análisis avanzado

---

## 15. Contacto y Soporte

**Repositorio:** https://github.com/anuarthr/FindMyWorkerBackend
**Branch principal:** `master`
**Documentación técnica:** `docs/`

**Para preguntas sobre:**

- Arquitectura ML → `docs/RECOMMENDATION_ARCHITECTURE.md`
- Decisiones técnicas (IA) → `docs/TECHNICAL_DECISIONS.md`
- Esta API → `docs/FRONTEND_API_SPEC.md` (este archivo)
