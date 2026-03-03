"""
Tests para el Tablero de Control Administrativo (HU8)

Cubre:
    - Acceso autorizado: Solo usuarios admin pueden acceder
    - Acceso denegado: Usuarios no-admin reciben 403 Forbidden
    - Autenticación requerida: Usuarios anónimos reciben 401 Unauthorized
    - Estructura de respuesta: Validar keys requeridas en la respuesta
    - Métricas de usuarios: Validar estructura de user_statistics
    - Métricas de profesiones: Validar estructura de profession_statistics
    - Métricas de transacciones: Validar estructura de transaction_statistics
    - Rate limiting: Verificar throttling de 10 req/min
"""

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core.cache import cache
from decimal import Decimal

from users.models import WorkerProfile
from orders.models import ServiceOrder

User = get_user_model()


class TestAdminDashboard(APITestCase):
    """Test suite para el endpoint de dashboard administrativo."""

    def setUp(self):
        """
        Configuración inicial para cada test.
        Crea usuarios de prueba y limpia el caché.
        """
        # Limpiar caché antes de cada test
        cache.clear()
        
        # Crear usuario administrador
        self.admin = User.objects.create_superuser(
            email="admin@test.com",
            password="AdminPass123!",
            role="ADMIN"
        )
        
        # Crear usuario cliente (sin permisos de admin)
        self.client_user = User.objects.create_user(
            email="client@test.com",
            password="ClientPass123!",
            role="CLIENT"
        )
        
        # Crear usuario trabajador (sin permisos de admin)
        self.worker_user = User.objects.create_user(
            email="worker@test.com",
            password="WorkerPass123!",
            role="WORKER"
        )
        
        # URL del endpoint
        self.url = reverse("admin-dashboard")

    def tearDown(self):
        """Limpiar caché después de cada test."""
        cache.clear()

    # ========================================================================
    # Tests de Autorización y Autenticación
    # ========================================================================

    def test_admin_can_access_dashboard(self):
        """
        Test: Usuario administrador puede acceder al dashboard.
        Expected: 200 OK con datos de métricas.
        """
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.json(), dict)

    def test_non_admin_client_is_forbidden(self):
        """
        Test: Usuario con rol CLIENT no puede acceder al dashboard.
        Expected: 403 Forbidden.
        """
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_worker_is_forbidden(self):
        """
        Test: Usuario con rol WORKER no puede acceder al dashboard.
        Expected: 403 Forbidden.
        """
        self.client.force_authenticate(user=self.worker_user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_is_unauthorized(self):
        """
        Test: Usuario no autenticado no puede acceder al dashboard.
        Expected: 401 Unauthorized.
        """
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========================================================================
    # Tests de Estructura de Respuesta
    # ========================================================================

    def test_response_has_required_keys(self):
        """
        Test: La respuesta contiene todas las keys principales requeridas.
        Expected: user_statistics, profession_statistics, transaction_statistics.
        """
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        data = response.json()
        
        self.assertIn("user_statistics", data)
        self.assertIn("profession_statistics", data)
        self.assertIn("transaction_statistics", data)

    def test_user_statistics_structure(self):
        """
        Test: user_statistics tiene la estructura correcta.
        Expected: total, by_role, growth con last_30_days y last_7_days.
        """
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        stats = response.json()["user_statistics"]
        
        # Validar keys principales
        self.assertIn("total", stats)
        self.assertIn("by_role", stats)
        self.assertIn("growth", stats)
        
        # Validar tipos de datos
        self.assertIsInstance(stats["total"], int)
        self.assertIsInstance(stats["by_role"], dict)
        self.assertIsInstance(stats["growth"], dict)
        
        # Validar growth keys
        self.assertIn("last_30_days", stats["growth"])
        self.assertIn("last_7_days", stats["growth"])

    def test_profession_statistics_structure(self):
        """
        Test: profession_statistics es una lista con la estructura correcta.
        Expected: Lista de objetos con profession y worker_count.
        """
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        stats = response.json()["profession_statistics"]
        
        # Validar que es una lista
        self.assertIsInstance(stats, list)
        
        # Si hay profesiones, validar estructura del primer elemento
        if len(stats) > 0:
            profession = stats[0]
            self.assertIn("profession", profession)
            self.assertIn("worker_count", profession)
            self.assertIsInstance(profession["worker_count"], int)

    def test_transaction_statistics_structure(self):
        """
        Test: transaction_statistics tiene la estructura correcta.
        Expected: total_orders, by_status, revenue_trend, platform_commission_10pct.
        """
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        stats = response.json()["transaction_statistics"]
        
        # Validar keys principales
        self.assertIn("total_orders", stats)
        self.assertIn("by_status", stats)
        self.assertIn("revenue_trend", stats)
        self.assertIn("platform_commission_10pct", stats)
        
        # Validar tipos de datos
        self.assertIsInstance(stats["total_orders"], int)
        self.assertIsInstance(stats["by_status"], dict)
        self.assertIsInstance(stats["revenue_trend"], list)
        self.assertIsInstance(stats["platform_commission_10pct"], str)

    # ========================================================================
    # Tests de Lógica de Negocio
    # ========================================================================

    def test_user_count_is_accurate(self):
        """
        Test: El total de usuarios reportado es preciso.
        Expected: Debe contar todos los usuarios creados en setUp.
        """
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        stats = response.json()["user_statistics"]
        
        # En setUp creamos: 1 admin + 1 client + 1 worker = 3 usuarios
        expected_total = User.objects.count()
        self.assertEqual(stats["total"], expected_total)

    def test_user_by_role_distribution(self):
        """
        Test: La distribución de usuarios por rol es correcta.
        Expected: Debe reflejar los usuarios creados en setUp.
        """
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        by_role = response.json()["user_statistics"]["by_role"]
        
        # Validar que hay al menos un usuario de cada rol creado en setUp
        self.assertEqual(by_role.get("ADMIN", 0), 1)
        self.assertEqual(by_role.get("CLIENT", 0), 1)
        self.assertEqual(by_role.get("WORKER", 0), 1)

    def test_profession_statistics_with_workers(self):
        """
        Test: Las estadísticas de profesiones reflejan los perfiles de trabajadores.
        Expected: Debe listar las profesiones de los workers creados.
        """
        # Actualizar el perfil del worker con una profesión específica
        worker_profile = WorkerProfile.objects.get(user=self.worker_user)
        worker_profile.profession = "PLUMBER"
        worker_profile.save()
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        stats = response.json()["profession_statistics"]
        
        # Validar que aparece la profesión PLUMBER con count = 1
        plumber_stat = next(
            (s for s in stats if s["profession"] == "PLUMBER"), 
            None
        )
        self.assertIsNotNone(plumber_stat)
        self.assertEqual(plumber_stat["worker_count"], 1)

    def test_transaction_statistics_with_orders(self):
        """
        Test: Las estadísticas de transacciones reflejan las órdenes creadas.
        Expected: Debe contar correctamente las órdenes por estado.
        """
        # Crear una orden de prueba
        worker_profile = WorkerProfile.objects.get(user=self.worker_user)
        order = ServiceOrder.objects.create(
            client=self.client_user,
            worker=worker_profile,
            description="Test order",
            status="PENDING",
            agreed_price=Decimal("100.00")
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        stats = response.json()["transaction_statistics"]
        
        # Validar que el total de órdenes es correcto
        self.assertEqual(stats["total_orders"], 1)
        
        # Validar que la orden PENDING está contada
        self.assertIn("PENDING", stats["by_status"])
        self.assertEqual(stats["by_status"]["PENDING"]["count"], 1)

    # ========================================================================
    # Tests de Caché
    # ========================================================================

    def test_cache_is_used_on_subsequent_requests(self):
        """
        Test: El caché se utiliza en solicitudes subsecuentes.
        Expected: La segunda llamada debe retornar los mismos datos del caché.
        """
        self.client.force_authenticate(user=self.admin)
        
        # Primera llamada (no cached)
        response1 = self.client.get(self.url)
        data1 = response1.json()
        
        # Segunda llamada (cached)
        response2 = self.client.get(self.url)
        data2 = response2.json()
        
        # Los datos deberían ser idénticos
        self.assertEqual(data1, data2)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

    # ========================================================================
    # Tests de Rate Limiting
    # ========================================================================

    def test_rate_limiting(self):
        """
        Test: El rate limiting funciona correctamente (10 req/min).
        Expected: Después de 10 peticiones, debe retornar 429 Too Many Requests.
        
        Nota: Este test podría ser lento, considerar skip en CI/CD rápido.
        """
        self.client.force_authenticate(user=self.admin)
        
        # Hacer 10 peticiones (el límite)
        for i in range(10):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # La petición 11 debería ser throttled
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
