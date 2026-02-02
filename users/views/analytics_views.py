"""
Recommendation Analytics and Health views.

Admin endpoints for monitoring ML system performance and health.
"""
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Avg, Q
from django.core.cache import cache
from collections import Counter
import logging

from ..models import WorkerProfile, RecommendationLog
from ..services import RecommendationEngine
from ..throttles import (
    RecommendationAnalyticsThrottle,
    RecommendationHealthThrottle,
)

logger = logging.getLogger(__name__)


class RecommendationAnalyticsView(APIView):
    """
    GET /api/users/workers/recommendation-analytics/?days=30
    
    Admin-only analytics dashboard for recommendation system.
    
    Provides:
        - Total queries processed
        - CTR (Click-Through Rate) metrics
        - MRR (Mean Reciprocal Rank) scores
        - System performance statistics
        - A/B testing results (strategy comparison)
        - Corpus health indicators
    
    Query Parameters:
        - days (int): Analysis time range in days (default: 30)
    
    Response (200 OK):
        {
            "total_queries": 1523,
            "unique_users": 87,
            "avg_response_time_ms": 52.3,
            "cache_hit_rate": 0.78,
            "avg_ctr": 0.42,
            "avg_conversion_rate": 0.18,
            "avg_mrr": 0.76,
            "top_query_terms": [...],
            "ab_test_results": {...},
            "corpus_health": {...}
        }
    """
    
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    throttle_classes = [RecommendationAnalyticsThrottle]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        date_from = timezone.now() - timezone.timedelta(days=days)
        date_to = timezone.now()
        
        logs = RecommendationLog.objects.filter(
            created_at__gte=date_from,
            created_at__lte=date_to
        )
        
        total_queries = logs.count()
        
        if total_queries == 0:
            return Response({
                'message': 'No hay datos de recomendaciones en el rango especificado',
                'total_queries': 0,
                'date_range': {
                    'from': date_from.isoformat(),
                    'to': date_to.isoformat(),
                    'days': days
                }
            })
        
        analytics_data = {
            **self._calculate_basic_metrics(logs, total_queries),
            **self._calculate_engagement_metrics(logs, total_queries),
            'top_query_terms': self._get_top_query_terms(logs),
            'ab_test_results': self._calculate_ab_test_results(logs),
            'corpus_health': self._calculate_corpus_health(),
            'date_range': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat(),
                'days': days
            }
        }
        
        return Response(analytics_data, status=status.HTTP_200_OK)
    
    def _calculate_basic_metrics(self, logs, total_queries: int) -> dict:
        """Calculate basic system metrics."""
        unique_users = logs.filter(user__isnull=False).values('user').distinct().count()
        avg_response_time = logs.aggregate(avg=Avg('response_time_ms'))['avg'] or 0
        cache_hits = logs.filter(cache_hit=True).count()
        cache_hit_rate = cache_hits / total_queries if total_queries > 0 else 0
        avg_results = logs.aggregate(avg=Avg('results_count'))['avg'] or 0
        
        return {
            'total_queries': total_queries,
            'unique_users': unique_users,
            'avg_response_time_ms': round(avg_response_time, 2),
            'cache_hit_rate': round(cache_hit_rate, 4),
            'avg_results_per_query': round(avg_results, 2),
        }
    
    def _calculate_engagement_metrics(self, logs, total_queries: int) -> dict:
        """Calculate user engagement metrics (CTR, conversion, MRR)."""
        logs_with_click = logs.exclude(worker_clicked__isnull=True)
        ctr = logs_with_click.count() / total_queries if total_queries > 0 else 0
        
        logs_with_hire = logs.exclude(worker_hired__isnull=True)
        conversion_rate = logs_with_hire.count() / total_queries if total_queries > 0 else 0
        
        # Calculate MRR (Mean Reciprocal Rank)
        mrr_values = []
        for log in logs_with_click:
            if log.click_position is not None:
                mrr_values.append(log.reciprocal_rank)
        avg_mrr = sum(mrr_values) / len(mrr_values) if mrr_values else 0
        
        return {
            'avg_ctr': round(ctr, 4),
            'avg_conversion_rate': round(conversion_rate, 4),
            'avg_mrr': round(avg_mrr, 4),
        }
    
    def _get_top_query_terms(self, logs) -> list:
        """Extract most common query terms."""
        all_queries = logs.values_list('processed_query', flat=True)
        all_terms = []
        
        for q in all_queries:
            if q:
                all_terms.extend(q.split())
        
        term_counter = Counter(all_terms)
        return [
            {'term': term, 'count': count}
            for term, count in term_counter.most_common(10)
        ]
    
    def _calculate_ab_test_results(self, logs) -> dict:
        """Compare performance across different strategies."""
        ab_results = {}
        
        for strategy in ['tfidf', 'fallback', 'hybrid']:
            strategy_logs = logs.filter(strategy_used=strategy)
            strategy_count = strategy_logs.count()
            
            if strategy_count > 0:
                strategy_ctr = strategy_logs.exclude(worker_clicked__isnull=True).count() / strategy_count
                strategy_conversion = strategy_logs.exclude(worker_hired__isnull=True).count() / strategy_count
                strategy_avg_time = strategy_logs.aggregate(avg=Avg('response_time_ms'))['avg'] or 0
                
                ab_results[strategy] = {
                    'queries': strategy_count,
                    'avg_ctr': round(strategy_ctr, 4),
                    'avg_conversion_rate': round(strategy_conversion, 4),
                    'avg_response_time_ms': round(strategy_avg_time, 2)
                }
        
        return ab_results
    
    def _calculate_corpus_health(self) -> dict:
        """Analyze corpus quality and completeness."""
        total_workers = WorkerProfile.objects.filter(user__is_active=True).count()
        
        workers_with_bio = WorkerProfile.objects.filter(
            user__is_active=True
        ).exclude(
            Q(bio='') | Q(bio__isnull=True)
        ).count()
        
        # Calculate average bio length
        bios = WorkerProfile.objects.filter(
            user__is_active=True
        ).exclude(
            Q(bio='') | Q(bio__isnull=True)
        ).values_list('bio', flat=True)
        
        avg_bio_length = sum(len(bio) for bio in bios) / len(bios) if bios else 0
        
        workers_need_update = WorkerProfile.objects.filter(
            user__is_active=True
        ).filter(
            Q(bio='') | Q(bio__isnull=True) | Q(location__isnull=True)
        ).count()
        
        return {
            'total_workers': total_workers,
            'workers_with_bio': workers_with_bio,
            'avg_bio_length': round(avg_bio_length),
            'workers_need_update': workers_need_update,
            'health_percentage': round((workers_with_bio / total_workers * 100), 1) if total_workers > 0 else 0
        }


class RecommendationHealthView(APIView):
    """
    GET /api/users/workers/recommendation-health/
    
    Health check endpoint for recommendation system.
    
    Verifies:
        - TF-IDF model training status
        - Redis cache connectivity
        - Recent system performance
        - Corpus size and quality
    
    Response (200 OK):
        {
            "status": "ready",  // or "degraded", "unhealthy", "not_trained"
            "model_trained": true,
            "corpus_size": 127,
            "vocabulary_size": 856,
            "cache_status": "connected",
            "avg_response_time_ms": 52.3,
            "recommendations": [...]  // List of warnings/suggestions
        }
    """
    
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [RecommendationHealthThrottle]
    
    def get(self, request):
        health_data = {
            'checked_at': timezone.now(),
            'status': 'ready',
            'recommendations': []
        }
        
        # Check ML model
        self._check_model_health(health_data)
        
        # Check Redis cache
        self._check_cache_health(health_data)
        
        # Check recent performance
        self._check_performance(health_data)
        
        # Check corpus size
        self._check_corpus(health_data)
        
        # Determine HTTP status
        http_status = self._determine_http_status(health_data['status'])
        
        return Response(health_data, status=http_status)
    
    def _check_model_health(self, health_data: dict):
        """Verify TF-IDF model is trained and loaded."""
        try:
            engine = RecommendationEngine()
            model_trained = engine.vectorizer is not None and engine.tfidf_matrix is not None
            
            health_data['model_trained'] = model_trained
            
            if model_trained:
                health_data['corpus_size'] = len(engine.worker_ids)
                health_data['vocabulary_size'] = len(engine.vectorizer.vocabulary_)
                
                model_meta = cache.get('recommendation_model_metadata')
                if model_meta and 'trained_at' in model_meta:
                    health_data['model_last_trained'] = model_meta['trained_at']
            else:
                health_data['status'] = 'not_trained'
                health_data['recommendations'].append(
                    'Modelo TF-IDF no entrenado. Ejecuta: python manage.py train_recommendation_model'
                )
        except Exception as e:
            logger.error(f"Error checking model health: {e}")
            health_data['model_trained'] = False
            health_data['status'] = 'unhealthy'
            health_data['recommendations'].append(f'Error verificando modelo: {str(e)}')
    
    def _check_cache_health(self, health_data: dict):
        """Verify Redis cache is accessible."""
        try:
            cache.set('health_check_test', 'ok', 10)
            test_value = cache.get('health_check_test')
            
            if test_value == 'ok':
                health_data['cache_status'] = 'connected'
                cache_data = cache.get('recommendation_model_data')
                health_data['cache_keys_count'] = 1 if cache_data else 0
            else:
                health_data['cache_status'] = 'error'
                health_data['status'] = 'degraded'
                health_data['recommendations'].append('Cache Redis no responde correctamente')
        except Exception as e:
            logger.error(f"Error checking cache health: {e}")
            health_data['cache_status'] = 'disconnected'
            health_data['status'] = 'unhealthy'
            health_data['recommendations'].append('No se puede conectar a Redis')
    
    def _check_performance(self, health_data: dict):
        """Check recent system performance metrics."""
        try:
            recent_logs = RecommendationLog.objects.order_by('-created_at')[:100]
            
            if recent_logs.exists():
                avg_response = recent_logs.aggregate(avg=Avg('response_time_ms'))['avg']
                health_data['avg_response_time_ms'] = round(avg_response, 2)
                
                if avg_response > 200:  # > 200ms is slow
                    health_data['status'] = 'degraded'
                    health_data['recommendations'].append(
                        f'Tiempo de respuesta alto ({avg_response:.0f}ms). '
                        'Considerar reentrenar modelo o limpiar cache.'
                    )
        except Exception as e:
            logger.error(f"Error checking performance: {e}")
    
    def _check_corpus(self, health_data: dict):
        """Verify corpus has sufficient data."""
        try:
            active_workers = WorkerProfile.objects.filter(user__is_active=True).count()
            
            if active_workers < 10:
                health_data['status'] = 'degraded'
                health_data['recommendations'].append(
                    f'Corpus pequeño ({active_workers} trabajadores). '
                    'Considerar agregar más datos.'
                )
            
            # Check for recent activity
            one_day_ago = timezone.now() - timezone.timedelta(days=1)
            recent_queries = RecommendationLog.objects.filter(created_at__gte=one_day_ago).count()
            
            if recent_queries == 0:
                health_data['recommendations'].append(
                    'No hay queries recientes en las últimas 24h. El sistema puede no estar en uso.'
                )
        except Exception as e:
            logger.error(f"Error checking corpus: {e}")
    
    def _determine_http_status(self, health_status: str) -> int:
        """Map health status to HTTP status code."""
        if health_status == 'ready':
            return status.HTTP_200_OK
        elif health_status == 'degraded':
            return status.HTTP_200_OK  # 200 with warnings
        elif health_status in ['unhealthy', 'not_trained']:
            return status.HTTP_503_SERVICE_UNAVAILABLE
        return status.HTTP_200_OK
