"""
Services Module for FindMyWorker Backend

Este módulo contiene la lógica de negocio relacionada con:
- Sistema de recomendación semántica (TF-IDF)
- Procesamiento de lenguaje natural (NLP)
- Estrategias de matching (A/B/C testing)
"""

"""
Business logic services for users app.

Services handle complex business logic separate from views:
    - RecommendationEngine: ML-powered worker search
    - RecommendationPresenter: Response formatting
"""

from .recommendation_engine import RecommendationEngine
from .recommendation_presenter import RecommendationPresenter

__all__ = [
    'RecommendationEngine',
    'RecommendationPresenter',
]
