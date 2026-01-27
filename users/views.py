from django.shortcuts import render
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from .serializers import (
    UserSerializer, 
    UserRegistrationSerializer,
    WorkerProfileSerializer,
    WorkerProfileUpdateSerializer,
    CustomTokenObtainPairSerializer,
    # Serializers del sistema de recomendación
    RecommendationRequestSerializer,
    RecommendationResponseSerializer,
    WorkerRecommendationSerializer,
    RecommendationAnalyticsSerializer,
    RecommendationHealthSerializer,
)
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from .models import WorkerProfile, RecommendationLog
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView
from .throttles import (
    RecommendationSearchThrottle,
    RecommendationAnalyticsThrottle,
    RecommendationHealthThrottle,
)
from .services import RecommendationEngine
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Avg, Count, Q
from decimal import Decimal
import logging
import time

logger = logging.getLogger(__name__)

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegistrationSerializer

class ManageUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class ManageWorkerProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, created = WorkerProfile.objects.get_or_create(user=self.request.user)
        return profile
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return WorkerProfileSerializer
        return WorkerProfileUpdateSerializer


class WorkerAdminViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'])
    def pending(self, request):
        pending_workers = WorkerProfile.objects.filter(is_verified=False)
        serializer = self.get_serializer(pending_workers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        worker = self.get_object()
        worker.is_verified = True
        worker.save()
        return Response({'status': 'approved', 'id': worker.id})

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# ============================================================================
# VIEWS DEL SISTEMA DE RECOMENDACIÓN (HU2)
# ============================================================================

class WorkerRecommendationView(APIView):
    """
    POST /api/workers/recommend/
    
    Endpoint principal para obtener recomendaciones de trabajadores usando ML.
    
    Características:
        - Búsqueda semántica con TF-IDF
        - 3 estrategias: tfidf, fallback, hybrid
        - Filtros geográficos y de calidad
        - Explicabilidad (XAI) de resultados
        - Logging automático para analytics
        - Rate limiting: 60 req/min
    
    Request Body:
        {
            "query": "Plomero urgente para reparar fuga de agua",
            "strategy": "hybrid",
            "top_n": 5,
            "min_rating": 4.0,
            "latitude": 11.2403,
            "longitude": -74.2110,
            "max_distance_km": 15
        }
    
    Response:
        {
            "query": "...",
            "strategy_used": "hybrid",
            "recommendations": [...],
            "performance_ms": 52.3,
            "log_id": "uuid"
        }
    """
    
    permission_classes = [permissions.AllowAny]  # Puede ser público o autenticado según necesidad
    throttle_classes = [RecommendationSearchThrottle]
    
    def post(self, request):
        start_time = time.time()
        
        # Validar request
        request_serializer = RecommendationRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(
                request_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = request_serializer.validated_data
        query = validated_data['query']
        strategy = validated_data['strategy']
        top_n = validated_data['top_n']
        
        # Preparar filtros
        filters = {}
        if validated_data.get('min_rating'):
            filters['min_rating'] = validated_data['min_rating']
        if validated_data.get('latitude') and validated_data.get('longitude'):
            filters['latitude'] = validated_data['latitude']
            filters['longitude'] = validated_data['longitude']
            filters['max_distance_km'] = validated_data.get('max_distance_km', 50)
        if validated_data.get('profession'):
            filters['profession'] = validated_data['profession']
        
        try:
            # Obtener recomendaciones del engine
            engine = RecommendationEngine()
            results = engine.get_recommendations(
                query=query,
                strategy=strategy,
                top_n=top_n,
                filters=filters
            )
            
            # Extraer processed query
            processed_query = engine.preprocess_text(query)
            
            # Verificar si vino de cache (heurística)
            cache_hit = engine.vectorizer is not None and engine.tfidf_matrix is not None
            
            # Preparar resultados para serialización
            recommendations_data = []
            worker_ids = []
            
            for result in results:
                worker = result['worker']
                worker_ids.append(str(worker.id))
                
                # Agregar campos de recomendación al worker
                worker.score = result['score']
                worker.relevance_percentage = result['relevance_percentage']
                worker.explanation = result['explanation']
                
                # Agregar distancia si está disponible
                if 'distance_km' in result['explanation']:
                    worker.distance_km = result['explanation']['distance_km']
                
                recommendations_data.append(worker)
            
            # Calcular tiempo total
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Crear log de la recomendación
            log = RecommendationLog.objects.create(
                query=query,
                processed_query=processed_query,
                strategy_used=strategy,
                user=request.user if request.user.is_authenticated else None,
                filters_applied=filters,
                results_count=len(recommendations_data),
                top_worker_ids=worker_ids,
                response_time_ms=elapsed_ms,
                cache_hit=cache_hit,
                user_latitude=filters.get('latitude'),
                user_longitude=filters.get('longitude'),
            )
            
            # Serializar trabajadores
            workers_serializer = WorkerRecommendationSerializer(
                recommendations_data,
                many=True
            )
            
            # Preparar respuesta
            response_data = {
                'query': query,
                'processed_query': processed_query,
                'strategy_used': strategy,
                'total_results': len(recommendations_data),
                'recommendations': workers_serializer.data,
                'performance_ms': round(elapsed_ms, 2),
                'cache_hit': cache_hit,
                'log_id': str(log.id),
            }
            
            logger.info(
                f"Recommendation request: query='{query[:50]}', "
                f"strategy={strategy}, results={len(recommendations_data)}, "
                f"time={elapsed_ms:.2f}ms"
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except ValueError as e:
            # Error de validación del engine (ej: modelo no entrenado)
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
            # Error inesperado
            logger.exception(f"Unexpected error in recommendation: {e}")
            return Response(
                {
                    'error': 'Internal server error',
                    'detail': 'Ocurrió un error procesando la recomendación'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RecommendationAnalyticsView(APIView):
    """
    GET /api/workers/recommendation-analytics/
    
    Endpoint para métricas y analytics del sistema de recomendación.
    
    Retorna:
        - Total de queries procesadas
        - CTR (Click-Through Rate)
        - MRR (Mean Reciprocal Rank)
        - Performance del sistema
        - Resultados de A/B testing
        - Salud del corpus
    
    Query Params:
        - days: Rango de días para el análisis (default: 30)
    
    Response:
        {
            "total_queries": 1523,
            "avg_ctr": 0.42,
            "avg_response_time_ms": 52.3,
            "ab_test_results": {...},
            "corpus_health": {...}
        }
    """
    
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    throttle_classes = [RecommendationAnalyticsThrottle]
    
    def get(self, request):
        # Parámetros
        days = int(request.query_params.get('days', 30))
        
        # Rango de fechas
        date_from = timezone.now() - timezone.timedelta(days=days)
        date_to = timezone.now()
        
        # Logs en el rango
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
        
        # Usuarios únicos
        unique_users = logs.filter(user__isnull=False).values('user').distinct().count()
        
        # Performance
        avg_response_time = logs.aggregate(avg=Avg('response_time_ms'))['avg'] or 0
        cache_hits = logs.filter(cache_hit=True).count()
        cache_hit_rate = cache_hits / total_queries if total_queries > 0 else 0
        avg_results = logs.aggregate(avg=Avg('results_count'))['avg'] or 0
        
        # Engagement metrics
        logs_with_click = logs.exclude(worker_clicked__isnull=True)
        ctr = logs_with_click.count() / total_queries if total_queries > 0 else 0
        
        logs_with_hire = logs.exclude(worker_hired__isnull=True)
        conversion_rate = logs_with_hire.count() / total_queries if total_queries > 0 else 0
        
        # MRR (Mean Reciprocal Rank)
        mrr_values = []
        for log in logs_with_click:
            if log.click_position is not None:
                mrr_values.append(log.reciprocal_rank)
        avg_mrr = sum(mrr_values) / len(mrr_values) if mrr_values else 0
        
        # Top query terms (análisis simple de palabras más comunes)
        from collections import Counter
        all_queries = logs.values_list('processed_query', flat=True)
        all_terms = []
        for q in all_queries:
            if q:
                all_terms.extend(q.split())
        
        term_counter = Counter(all_terms)
        top_terms = [
            {'term': term, 'count': count}
            for term, count in term_counter.most_common(20)
        ]
        
        # A/B Testing results
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
        
        # Corpus health
        total_workers = WorkerProfile.objects.filter(user__is_active=True).count()
        workers_with_bio = WorkerProfile.objects.filter(
            user__is_active=True
        ).exclude(
            Q(bio='') | Q(bio__isnull=True)
        ).count()
        
        # Promedio de longitud de bio
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
        
        corpus_health = {
            'total_workers': total_workers,
            'workers_with_bio': workers_with_bio,
            'avg_bio_length': round(avg_bio_length),
            'workers_need_update': workers_need_update,
            'health_percentage': round((workers_with_bio / total_workers * 100), 1) if total_workers > 0 else 0
        }
        
        # Respuesta
        analytics_data = {
            'total_queries': total_queries,
            'unique_users': unique_users,
            'avg_response_time_ms': round(avg_response_time, 2),
            'cache_hit_rate': round(cache_hit_rate, 4),
            'avg_results_per_query': round(avg_results, 2),
            'avg_ctr': round(ctr, 4),
            'avg_conversion_rate': round(conversion_rate, 4),
            'avg_mrr': round(avg_mrr, 4),
            'top_query_terms': top_terms[:10],  # Top 10
            'ab_test_results': ab_results,
            'corpus_health': corpus_health,
            'date_range': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat(),
                'days': days
            }
        }
        
        return Response(analytics_data, status=status.HTTP_200_OK)


class RecommendationHealthView(APIView):
    """
    GET /api/workers/recommendation-health/
    
    Health check del sistema de recomendación.
    
    Verifica:
        - Estado del modelo TF-IDF
        - Conexión a Redis cache
        - Performance reciente
        - Errores recientes
    
    Response:
        {
            "status": "healthy",
            "model_trained": true,
            "corpus_size": 127,
            "cache_status": "connected",
            "avg_response_time_ms": 52.3
        }
    """
    
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [RecommendationHealthThrottle]
    
    def get(self, request):
        health_data = {
            'checked_at': timezone.now(),
            'status': 'healthy',
            'recommendations': []
        }
        
        # 1. Verificar modelo TF-IDF
        try:
            engine = RecommendationEngine()
            model_trained = engine.vectorizer is not None and engine.tfidf_matrix is not None
            
            health_data['model_trained'] = model_trained
            
            if model_trained:
                health_data['corpus_size'] = len(engine.worker_ids)
                health_data['vocabulary_size'] = len(engine.vectorizer.vocabulary_)
                
                # Intentar obtener timestamp del modelo
                model_meta = cache.get('recommendation_model_metadata')
                if model_meta and 'trained_at' in model_meta:
                    health_data['model_last_trained'] = model_meta['trained_at']
            else:
                health_data['status'] = 'degraded'
                health_data['recommendations'].append(
                    'Modelo TF-IDF no entrenado. Ejecuta: python manage.py train_recommendation_model'
                )
        
        except Exception as e:
            logger.error(f"Error checking model health: {e}")
            health_data['model_trained'] = False
            health_data['status'] = 'unhealthy'
            health_data['recommendations'].append(f'Error verificando modelo: {str(e)}')
        
        # 2. Verificar cache Redis
        try:
            cache.set('health_check_test', 'ok', 10)
            test_value = cache.get('health_check_test')
            
            if test_value == 'ok':
                health_data['cache_status'] = 'connected'
                
                # Contar keys relacionadas con ML
                # Nota: No hay método directo en Django cache, usar heurística
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
        
        # 3. Performance reciente (últimas 100 queries)
        try:
            recent_logs = RecommendationLog.objects.order_by('-created_at')[:100]
            
            if recent_logs.exists():
                avg_response = recent_logs.aggregate(avg=Avg('response_time_ms'))['avg']
                health_data['avg_response_time_ms'] = round(avg_response, 2)
                
                # Warning si el tiempo promedio es muy alto
                if avg_response > 200:  # > 200ms
                    health_data['status'] = 'degraded'
                    health_data['recommendations'].append(
                        f'Tiempo de respuesta alto ({avg_response:.0f}ms). Considerar reentrenar modelo o limpiar cache.'
                    )
        
        except Exception as e:
            logger.error(f"Error checking performance: {e}")
        
        # 4. Errores recientes (últimas 24h)
        try:
            # Esto requeriría un modelo ErrorLog separado, por ahora usar heurística simple
            one_day_ago = timezone.now() - timezone.timedelta(days=1)
            recent_queries = RecommendationLog.objects.filter(created_at__gte=one_day_ago).count()
            
            # Si hay pocas queries recientes, puede indicar un problema
            if recent_queries == 0:
                health_data['recommendations'].append(
                    'No hay queries recientes en las últimas 24h. El sistema puede no estar en uso.'
                )
            
            health_data['recent_errors_count'] = 0  # Placeholder
        
        except Exception as e:
            logger.error(f"Error checking recent errors: {e}")
        
        # 5. Verificar corpus
        try:
            active_workers = WorkerProfile.objects.filter(user__is_active=True).count()
            
            if active_workers < 10:
                health_data['status'] = 'degraded'
                health_data['recommendations'].append(
                    f'Corpus pequeño ({active_workers} trabajadores). Considerar agregar más datos.'
                )
        
        except Exception as e:
            logger.error(f"Error checking corpus: {e}")
        
        # Determinar status HTTP según health status
        http_status = status.HTTP_200_OK
        if health_data['status'] == 'degraded':
            http_status = status.HTTP_200_OK  # 200 pero con warnings
        elif health_data['status'] == 'unhealthy':
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        
        return Response(health_data, status=http_status)
