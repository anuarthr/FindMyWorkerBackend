"""
Worker Recommendation views.

ML-powered semantic search for finding workers based on natural language queries.
"""
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
import logging
import time

from ..serializers import (
    RecommendationRequestSerializer,
    WorkerRecommendationSerializer,
)
from ..models import RecommendationLog
from ..services import RecommendationEngine
from ..services.recommendation_presenter import RecommendationPresenter
from ..throttles import RecommendationSearchThrottle

logger = logging.getLogger(__name__)


class WorkerRecommendationView(APIView):
    """
    POST /api/users/workers/recommend/
    
    ML-powered semantic search endpoint for worker recommendations.
    
    Features:
        - TF-IDF based semantic search
        - 3 ranking strategies: tfidf (pure ML), fallback (geo+rating), hybrid (combined)
        - Geographic and quality filters
        - Explainable AI (XAI) - provides reasoning for recommendations
        - Automatic analytics logging
        - Rate limiting: 60 requests/minute
    
    Request Body:
        {
            "query": "Plomero urgente para reparar fuga de agua",
            "strategy": "hybrid",  // optional, default: "tfidf"
            "top_n": 5,           // optional, default: 5
            "min_rating": 4.0,    // optional
            "latitude": 11.2403,  // optional
            "longitude": -74.2110, // optional
            "max_distance_km": 15  // optional
        }
    
    Response (200 OK):
        {
            "query": "...",
            "strategy_used": "hybrid",
            "total_results": 5,
            "recommendations": [
                {
                    "id": 1,
                    "user": {...},
                    "profession": "PLUMBER",
                    "recommendation_score": 0.87,
                    "matched_keywords": ["fuga", "reparar"],
                    "explanation": "87% relevante - coincide con: fuga, reparar - a 2.5km"
                }
            ],
            "performance_ms": 52.3,
            "cache_hit": true,
            "log_id": "uuid-here"
        }
    """
    
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RecommendationSearchThrottle]
    
    def post(self, request):
        start_time = time.time()
        
        # 1. Validate request
        request_serializer = RecommendationRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(
                request_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = request_serializer.validated_data
        
        # 2. Extract parameters
        query = validated_data['query']
        strategy = validated_data['strategy']
        top_n = validated_data['top_n']
        filters = self._build_filters(validated_data)
        
        try:
            # 3. Get recommendations from ML engine
            engine = RecommendationEngine()
            results = engine.get_recommendations(
                query=query,
                strategy=strategy,
                top_n=top_n,
                filters=filters
            )
            
            processed_query = engine.preprocess_text(query)
            cache_hit = engine.vectorizer is not None and engine.tfidf_matrix is not None
            
            # 4. Prepare presentation data
            recommendations_data, worker_ids = RecommendationPresenter.prepare_worker_data(results)
            
            # 5. Calculate performance metrics
            elapsed_ms = (time.time() - start_time) * 1000
            
            # 6. Log the recommendation for analytics
            log = self._create_recommendation_log(
                query=query,
                processed_query=processed_query,
                strategy=strategy,
                user=request.user if request.user.is_authenticated else None,
                filters=filters,
                worker_ids=worker_ids,
                elapsed_ms=elapsed_ms,
                cache_hit=cache_hit
            )
            
            # 7. Serialize workers
            workers_serializer = WorkerRecommendationSerializer(
                recommendations_data,
                many=True
            )
            
            # 8. Build response
            response_data = RecommendationPresenter.build_response(
                query=query,
                processed_query=processed_query,
                strategy=strategy,
                recommendations_serialized=workers_serializer.data,
                elapsed_ms=elapsed_ms,
                cache_hit=cache_hit,
                log_id=str(log.id)
            )
            
            logger.info(
                f"Recommendation: query='{query[:50]}', strategy={strategy}, "
                f"results={len(recommendations_data)}, time={elapsed_ms:.2f}ms"
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except ValueError as e:
            logger.error(f"Recommendation engine error: {e}")
            return Response(
                {
                    'error': 'Recommendation engine error',
                    'detail': str(e),
                    'hint': 'El modelo ML puede no estar entrenado. Ejecuta: python manage.py train_recommendation_model'
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        except Exception as e:
            logger.exception(f"Unexpected error in recommendation: {e}")
            return Response(
                {
                    'error': 'Internal server error',
                    'detail': 'Ocurrió un error procesando la recomendación'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _build_filters(self, validated_data: dict) -> dict:
        """Extract and build filters dict from validated request data."""
        filters = {}
        
        if validated_data.get('min_rating'):
            filters['min_rating'] = validated_data['min_rating']
        
        if validated_data.get('latitude') and validated_data.get('longitude'):
            filters['latitude'] = validated_data['latitude']
            filters['longitude'] = validated_data['longitude']
            filters['max_distance_km'] = validated_data.get('max_distance_km', 50)
        
        if validated_data.get('profession'):
            filters['profession'] = validated_data['profession']
        
        return filters
    
    def _create_recommendation_log(
        self,
        query: str,
        processed_query: str,
        strategy: str,
        user,
        filters: dict,
        worker_ids: list,
        elapsed_ms: float,
        cache_hit: bool
    ) -> RecommendationLog:
        """Create analytics log entry for this recommendation."""
        return RecommendationLog.objects.create(
            query=query,
            processed_query=processed_query,
            strategy_used=strategy,
            user=user,
            filters_applied=filters,
            results_count=len(worker_ids),
            top_worker_ids=worker_ids,
            response_time_ms=elapsed_ms,
            cache_hit=cache_hit,
            user_latitude=filters.get('latitude'),
            user_longitude=filters.get('longitude'),
        )
