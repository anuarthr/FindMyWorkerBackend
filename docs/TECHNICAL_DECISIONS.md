# Decisiones Técnicas - FindMyWorker Backend

Este documento registra las decisiones arquitectónicas y técnicas importantes del proyecto.

---

## TD-001: Soporte de Idioma Único (Español) en Sistema de Recomendación

**Fecha:** 2026-01-28
**Contexto:** HU2.1 - Compatibilidad con Frontend
**Estado:** ✅ Implementado

### Decisión

El sistema de recomendación basado en ML **solo soporta español** actualmente. El parámetro `language` acepta valores `"es"` y `"en"`, pero inglés retorna error 400 con mensaje descriptivo.

### Razones

1. **Corpus Monolingüe**

   - Las biografías de trabajadores están escritas en español
   - No existe contenido en inglés para entrenar el modelo TF-IDF
   - Crear corpus bilingüe requiere cambios en UI y modelo de datos
2. **Recursos NLP Limitados**

   - NLTK configurado solo con recursos en español (stopwords, stemming)
   - Inglés requiere diferentes reglas de preprocesamiento
   - Instalación: `python manage.py setup_nlp` solo descarga recursos ES
3. **Complejidad de Sinónimos**

   - No hay sistema de expansión de sinónimos implementado
   - Ejemplo necesario: `"plomero"` → `["fontanero", "gasfiter", "sanitario"]`
   - Requiere diccionarios mantenibles y validación de calidad
4. **Estrategia de Traducción No Definida**

   - **Opción A:** Traducción automática (requiere API externa, costo, latencia)
   - **Opción B:** Corpus bilingüe (requiere que trabajadores escriban en ambos idiomas)
   - **Opción C:** Búsqueda cruzada ES-EN (muy baja calidad de resultados)

### Implementación

```python
# users/serializers.py - RecommendationRequestSerializer.validate()

language = data.get('language', 'es')
if language == 'en':
    raise serializers.ValidationError({
        'language': 'Inglés no soportado actualmente. Use "es" para español. Funcionalidad en desarrollo.'
    })
```

### Consecuencias

**Positivas:**

- Error claro y descriptivo para desarrolladores frontend
- Sistema robusto con un solo idioma bien implementado
- Parámetro `language` preparado para expansión futura
- Sin dependencias de traducción externas

**Negativas:**

- Usuarios de habla inglesa no pueden usar el sistema
- Mercado limitado a regiones hispanohablantes
- Requiere feature completa futura para inglés

### Trabajo Futuro

Para implementar soporte de inglés en el futuro:

1. **Corpus Bilingüe**

   - Añadir campo `bio_en` a `WorkerProfile`
   - UI para trabajadores: escribir biografía en ambos idiomas
   - Validación: biografía en idioma del trabajador requerida
2. **Recursos NLP**

   - Actualizar `setup_nlp` command para descargar recursos EN
   - Configurar stopwords y stemmer para inglés
   - Testing de preprocesamiento en ambos idiomas
3. **Sistema de Sinónimos**

   - Base de datos o archivo JSON con sinónimos por idioma
   - Ejemplo ES: `{"plomero": ["fontanero", "gasfiter", "sanitario"]}`
   - Ejemplo EN: `{"plumber": ["plumbing", "pipe fitter", "pipefitter"]}`
   - Expansión automática de queries
4. **Entrenamiento Separado**

   - Dos modelos TF-IDF: uno para ES, otro para EN
   - Cache separado: `ml_recommendation_model_es`, `ml_recommendation_model_en`
   - Selección automática según parámetro `language`
5. **Testing**

   - Unit tests para preprocesamiento EN
   - Integration tests para búsquedas en inglés
   - Validación de calidad de resultados bilingües

### Referencias

- `users/serializers.py` - Línea ~200 (validación language)
- `users/services/recommendation_engine.py` - Línea ~50 (preprocess_text con NLTK ES)
- `docs/FRONTEND_API_SPEC.md` - Sección 4 (Sinónimos Multi-Idioma)

---

## TD-002: Campos Planos de Compatibilidad en Serializer

**Fecha:** 2026-01-28
**Contexto:** HU2.1 - Compatibilidad con Frontend
**Estado:** ✅ Implementado

### Decisión

El serializer `WorkerRecommendationSerializer` retorna tanto **campos planos** (fácil acceso para frontend) como **campos detallados** (análisis avanzado), manteniendo backward compatibility.

### Estructura de Respuesta

```python
# Campos planos (para frontend)
recommendation_score: float          # 0-1
matched_keywords: list[str]          # ["plomero", "reparaciones"]
explanation: str                     # "85% relevante - coincide con..."

# Campos detallados (para análisis)
recommendation_details: {
    semantic_similarity: float,
    relevance_percentage: float,
    distance_km: float,
    distance_factor: float,
    normalized_score: float,
    matched_terms_count: int
}
```

### Razones

1. **Simplicidad para Frontend**

   - Acceso directo sin navegación de JSON anidado
   - Campos con nombres descriptivos
   - String `explanation` generado automáticamente
2. **Backward Compatibility**

   - Mantiene información detallada para análisis
   - No rompe herramientas de monitoreo existentes
   - Preparado para features avanzadas futuras
3. **Mejor Developer Experience**

   - Frontend usa campos simples
   - Data scientists usan campos detallados
   - Documentación clara de ambos niveles

### Generación de String `explanation`

```python
# users/services/recommendation_presenter.py - RecommendationPresenter._build_explanation()

explanation_parts = []
if relevance_pct > 0:
    explanation_parts.append(f"{relevance_pct:.0f}% relevante")
if keywords:
    explanation_parts.append(f"coincide con: {', '.join(keywords[:3])}")
if distance is not None:
    explanation_parts.append(f"a {distance:.1f}km")

worker.explanation = " - ".join(explanation_parts) or "Recomendado por filtros"
```

### Consecuencias

**Positivas:**

- Frontend implementation más rápida
- Mantiene flexibilidad para análisis
- Auto-documentado (campos descriptivos)
- Fácil debugging

**Negativas:**

- Tamaño de response ligeramente mayor
- Duplicación parcial de datos
- Dos niveles de información a mantener

### Referencias

- `users/serializers.py` - Línea ~220 (WorkerRecommendationSerializer)
- `users/services/recommendation_presenter.py` - prepare_worker_data(), _build_explanation()
- `users/views/recommendation_views.py` - WorkerRecommendationView
- `docs/FRONTEND_API_SPEC.md` - Sección 2 (Response structure)

---

## TD-003: Health Status Mapping para Frontend

**Fecha:** 2026-01-28
**Contexto:** HU2.1 - Compatibilidad con Frontend
**Estado:** ✅ Implementado

### Decisión

El endpoint `/api/users/recommendation-health/` usa status `"ready"` en lugar de `"healthy"` cuando el modelo está entrenado y funcional.

### Mapeo

| Status Interno                    | Status API        | Significado            |
| --------------------------------- | ----------------- | ---------------------- |
| `model_trained=True, no_errors` | `"ready"`       | Sistema listo para uso |
| `model_trained=False`           | `"not_trained"` | Modelo sin entrenar    |
| `errors but functional`         | `"degraded"`    | Funcional con warnings |
| `critical errors`               | `"unhealthy"`   | No funcional           |

### Razones

1. **Alineación con Frontend**

   - Especificación del frontend requiere `"ready"`
   - Semántica más clara para UI
2. **Estado `"training"` Omitido**

   - El entrenamiento toma <200ms
   - Imposible capturar este estado en práctica
   - No es útil para usuarios

### Implementación

```python
# users/views.py - RecommendationHealthView.get()

health_data = {
    'status': 'ready',  # Cambió de 'healthy'
    'model_trained': model_trained,
    ...
}

if not model_trained:
    health_data['status'] = 'not_trained'  # Cambió de 'degraded'
```

### Consecuencias

**Positivas:**

- Consistencia con especificación frontend
- Status names más descriptivos
- Elimina estado imposible de observar

**Negativas:**

- Cambio breaking para clientes existentes (si los hay)
- Requiere actualizar documentación

### Referencias

- `users/views.py` - Línea ~480 (RecommendationHealthView)
- `users/serializers.py` - Línea ~340 (RecommendationHealthSerializer)
- `docs/FRONTEND_API_SPEC.md` - Sección 1 (Health endpoint)

---
