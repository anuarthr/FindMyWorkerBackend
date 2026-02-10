from django.urls import path
from .views import (
    ManageUserView,
    # Sistema de Recomendación (HU2)
    WorkerRecommendationView,
    RecommendationAnalyticsView,
    RecommendationHealthView,
)
from .views.portfolio_views import (
    MyPortfolioListCreateView,
    WorkerPortfolioListView,
    PortfolioItemDetailView,
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
    
    # ============================================================================
    # ENDPOINTS DE PORTFOLIO (HU4)
    # ============================================================================
    
    # Manage authenticated worker's portfolio
    path(
        'workers/portfolio/',
        MyPortfolioListCreateView.as_view(),
        name='my-portfolio'
    ),
    
    # View specific worker's public portfolio
    path(
        'workers/<int:worker_id>/portfolio/',
        WorkerPortfolioListView.as_view(),
        name='worker-portfolio'
    ),
    
    # CRUD operations on specific portfolio item
    path(
        'workers/portfolio/<int:pk>/',
        PortfolioItemDetailView.as_view(),
        name='portfolio-item-detail'
    ),
]
