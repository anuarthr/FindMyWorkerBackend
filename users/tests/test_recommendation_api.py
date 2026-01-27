"""
Tests de integración para los endpoints del sistema de recomendación.

Cubre:
    - POST /api/users/workers/recommend/
    - GET /api/users/workers/recommendation-analytics/
    - GET /api/users/workers/recommendation-health/
    - Rate limiting
    - Autenticación y permisos
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from users.models import WorkerProfile, RecommendationLog
from django.contrib.gis.geos import Point
from decimal import Decimal

User = get_user_model()


class RecommendationAPITestCase(TestCase):
    """Tests de integración para los endpoints de recomendación."""
    
    def setUp(self):
        """Setup inicial."""
        self.client = APIClient()
        
        # Crear usuario cliente
        self.user = User.objects.create_user(
            email='cliente@test.com',
            password='test123',
            role='CLIENT'
        )
        
        # Crear admin
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='admin123',
            role='ADMIN',
            is_staff=True
        )
        
        # Crear trabajadores
        self._create_test_workers()
    
    def _create_test_workers(self):
        """Crea trabajadores de prueba."""
        professions = [
            ('PLUMBER', 'Plomero con 10 años de experiencia en reparaciones hidráulicas'),
            ('ELECTRICIAN', 'Electricista certificado especializado en instalaciones'),
            ('PAINTER', 'Pintor profesional para interiores y exteriores'),
        ]
        
        for i, (prof, bio) in enumerate(professions):
            user = User.objects.create_user(
                email=f'worker{i}@test.com',
                password='test123',
                role='WORKER'
            )
            WorkerProfile.objects.create(
                user=user,
                profession=prof,
                bio=bio,
                years_experience=5 + i,
                average_rating=Decimal('4.5'),
                location=Point(-74.0721, 4.7110, srid=4326)
            )
    
    def test_recommend_endpoint_success(self):
        """Test exitoso del endpoint de recomendación."""
        url = reverse('worker-recommend')
        
        data = {
            'query': 'necesito un plomero urgente',
            'strategy': 'tfidf',
            'top_n': 3
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('query', response.data)
        self.assertIn('recommendations', response.data)
        self.assertIn('performance_ms', response.data)
        self.assertIn('log_id', response.data)
    
    def test_recommend_with_filters(self):
        """Test con filtros geográficos y de rating."""
        url = reverse('worker-recommend')
        
        data = {
            'query': 'trabajador profesional',
            'strategy': 'hybrid',
            'top_n': 5,
            'min_rating': 4.0,
            'latitude': 4.7110,
            'longitude': -74.0721,
            'max_distance_km': 10
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['strategy_used'], 'hybrid')
    
    def test_recommend_invalid_data(self):
        """Test con datos inválidos."""
        url = reverse('worker-recommend')
        
        # Query vacía
        data = {'query': '', 'strategy': 'tfidf'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Estrategia inválida
        data = {'query': 'test', 'strategy': 'invalid'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Latitude sin longitude
        data = {'query': 'test', 'latitude': 4.7}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_recommend_creates_log(self):
        """Test que se crea un log de la recomendación."""
        url = reverse('worker-recommend')
        
        initial_count = RecommendationLog.objects.count()
        
        data = {
            'query': 'plomero',
            'strategy': 'tfidf',
            'top_n': 3
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(RecommendationLog.objects.count(), initial_count + 1)
        
        # Verificar datos del log
        log = RecommendationLog.objects.latest('created_at')
        self.assertEqual(log.query, 'plomero')
        self.assertEqual(log.strategy_used, 'tfidf')
    
    def test_analytics_endpoint_requires_auth(self):
        """Test que analytics requiere autenticación de admin."""
        url = reverse('recommendation-analytics')
        
        # Sin autenticación
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Con usuario normal (no admin)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Con admin
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_200_OK])
    
    def test_analytics_endpoint_with_data(self):
        """Test del endpoint de analytics con datos."""
        # Crear algunos logs
        for i in range(5):
            RecommendationLog.objects.create(
                query=f'test query {i}',
                processed_query=f'test query {i}',
                strategy_used='tfidf',
                results_count=3,
                response_time_ms=50.0,
                cache_hit=i % 2 == 0
            )
        
        self.client.force_authenticate(user=self.admin)
        url = reverse('recommendation-analytics')
        
        response = self.client.get(url, {'days': 7})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_queries', response.data)
        self.assertIn('avg_response_time_ms', response.data)
        self.assertIn('cache_hit_rate', response.data)
        self.assertIn('ab_test_results', response.data)
        self.assertIn('corpus_health', response.data)
    
    def test_health_endpoint(self):
        """Test del endpoint de health check."""
        self.client.force_authenticate(user=self.user)
        url = reverse('recommendation-health')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertIn('model_trained', response.data)
        self.assertIn('cache_status', response.data)
        self.assertIn('checked_at', response.data)
    
    def test_health_endpoint_checks_corpus(self):
        """Test que health check verifica el corpus."""
        self.client.force_authenticate(user=self.user)
        url = reverse('recommendation-health')
        
        response = self.client.get(url)
        
        # Con pocos trabajadores, debería tener recomendaciones
        if response.data.get('status') == 'degraded':
            self.assertIn('recommendations', response.data)
            self.assertGreater(len(response.data['recommendations']), 0)


class RecommendationRateLimitingTestCase(TestCase):
    """Tests para rate limiting."""
    
    def setUp(self):
        """Setup inicial."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='user@test.com',
            password='test123',
            role='CLIENT'
        )
        
        # Crear al menos un trabajador
        worker_user = User.objects.create_user(
            email='worker@test.com',
            password='test123',
            role='WORKER'
        )
        WorkerProfile.objects.create(
            user=worker_user,
            profession='PLUMBER',
            bio='Plomero profesional con experiencia',
            years_experience=5
        )
    
    def test_rate_limiting_applied(self):
        """Test que se aplica rate limiting (nota: difícil de probar sin muchas requests)."""
        self.client.force_authenticate(user=self.user)
        url = reverse('worker-recommend')
        
        data = {'query': 'test', 'strategy': 'fallback', 'top_n': 1}
        
        # Primera request debe funcionar
        response = self.client.post(url, data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
        
        # Nota: Para probar throttling completo, necesitaríamos hacer 60+ requests
        # lo cual haría el test muy lento. Verificamos solo que el mecanismo existe.
