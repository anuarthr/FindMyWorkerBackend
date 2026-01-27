from django.urls import path
from .views import (
    ManageUserView,
    # Sistema de Recomendación (HU2)
    WorkerRecommendationView,
    RecommendationAnalyticsView,
    RecommendationHealthView,
)

urlpatterns = [
    path('me/', ManageUserView.as_view(), name='me'),
    
    # ============================================================================
    # ENDPOINTS DEL SISTEMA DE RECOMENDACIÓN (HU2)
    # ============================================================================
    
    # Búsqueda semántica de trabajadores
    path(
        'workers/recommend/',
        WorkerRecommendationView.as_view(),
        name='worker-recommend'
    ),
    
    # Analytics y métricas del sistema
    path(
        'workers/recommendation-analytics/',
        RecommendationAnalyticsView.as_view(),
        name='recommendation-analytics'
    ),
    
    # Health check del sistema de recomendación
    path(
        'workers/recommendation-health/',
        RecommendationHealthView.as_view(),
        name='recommendation-health'
    ),
]
