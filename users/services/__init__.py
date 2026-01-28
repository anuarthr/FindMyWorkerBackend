"""
Services Module for FindMyWorker Backend

Este módulo contiene la lógica de negocio relacionada con:
- Sistema de recomendación semántica (TF-IDF)
- Procesamiento de lenguaje natural (NLP)
- Estrategias de matching (A/B/C testing)
"""

from .recommendation_engine import RecommendationEngine

__all__ = ['RecommendationEngine']
