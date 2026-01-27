"""
Custom throttling classes para el sistema de recomendación.

Define rate limits específicos para endpoints de ML para prevenir:
    - Abuso del sistema de recomendación
    - Sobrecarga del modelo TF-IDF
    - Queries excesivas que pueden degradar performance

Rates configurados:
    - RecommendationSearchThrottle: 60 req/min (búsquedas)
    - RecommendationAnalyticsThrottle: 30 req/min (analytics)
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class RecommendationSearchThrottle(UserRateThrottle):
    """
    Throttle para el endpoint de búsqueda de recomendaciones.
    
    Rate: 60 requests/minuto para usuarios autenticados
    
    Este es el endpoint más usado y crítico, por lo que tiene un límite
    moderado para prevenir abuso pero permitir uso normal.
    """
    scope = 'recommendation_search'


class RecommendationSearchAnonThrottle(AnonRateThrottle):
    """
    Throttle para búsquedas de usuarios anónimos (si se permite).
    
    Rate: 20 requests/minuto para usuarios no autenticados
    
    Más restrictivo que el de usuarios autenticados para prevenir scraping.
    """
    scope = 'recommendation_search_anon'


class RecommendationAnalyticsThrottle(UserRateThrottle):
    """
    Throttle para el endpoint de analytics/métricas.
    
    Rate: 30 requests/minuto
    
    Más restrictivo ya que las consultas de analytics son más pesadas
    (agregaciones sobre todo el histórico de logs).
    """
    scope = 'recommendation_analytics'


class RecommendationHealthThrottle(UserRateThrottle):
    """
    Throttle para el endpoint de health check.
    
    Rate: 10 requests/minuto
    
    Muy restrictivo ya que health checks deberían ser poco frecuentes
    (típicamente desde monitoring systems).
    """
    scope = 'recommendation_health'
