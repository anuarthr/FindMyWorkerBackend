"""
Admin Dashboard Views para FindMyWorker

Endpoints administrativos para el tablero de control.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.throttling import UserRateThrottle
from rest_framework import status
import logging

from users.services.dashboard_service import DashboardService
from users.serializers import DashboardMetricsSerializer

logger = logging.getLogger(__name__)


class AdminDashboardThrottle(UserRateThrottle):
    """Rate limiting para el endpoint de dashboard: 10 peticiones por minuto."""
    rate = "10/min"


class AdminDashboardView(APIView):
    """
    GET /api/users/admin/dashboard/
    
    Devuelve métricas clave para el tablero de control administrativo.
    
    Métricas incluidas:
        - Total de usuarios registrados por rol
        - Crecimiento de usuarios (últimos 7 y 30 días)
        - Top 10 profesiones más demandadas
        - Volumen de órdenes por estado
        - Tendencia de ingresos (últimos 6 meses)
        - Estimación de comisión de plataforma
    
    Acceso:
        - Requiere autenticación
        - Solo usuarios con role=ADMIN (is_staff=True)
        - Rate limit: 10 peticiones/minuto
    
    Response (200 OK):
        {
            "user_statistics": {
                "total": 1523,
                "by_role": {
                    "CLIENT": 987,
                    "WORKER": 512,
                    "ADMIN": 24
                },
                "growth": {
                    "last_30_days": 143,
                    "last_7_days": 28
                }
            },
            "profession_statistics": [
                {
                    "profession": "PLUMBER",
                    "worker_count": 156
                },
                ...
            ],
            "transaction_statistics": {
                "total_orders": 3421,
                "by_status": {
                    "COMPLETED": {
                        "count": 2145,
                        "revenue": "234567.50"
                    },
                    ...
                },
                "revenue_trend": [
                    {
                        "month": "2026-01",
                        "orders": 245,
                        "revenue": "32456.00"
                    },
                    ...
                ],
                "platform_commission_10pct": "23456.75"
            }
        }
    
    Error Responses:
        - 401 Unauthorized: Usuario no autenticado
        - 403 Forbidden: Usuario autenticado pero sin permisos de admin
        - 429 Too Many Requests: Rate limit excedido
        - 500 Internal Server Error: Error al generar métricas
    """

    permission_classes = [IsAdminUser]
    throttle_classes = [AdminDashboardThrottle]

    def get(self, request):
        """
        Endpoint GET para obtener métricas del dashboard.
        
        Flujo:
            1. Validar permisos (automático via permission_classes)
            2. Llamar al servicio de negocio
            3. Serializar respuesta
            4. Retornar datos
        """
        try:
            # Llamar a la capa de servicio (lógica de negocio pura)
            metrics = DashboardService.get_full_metrics()
            
            # Serializar y validar estructura de datos
            serializer = DashboardMetricsSerializer(metrics)
            
            logger.info(
                f"Dashboard metrics retrieved successfully by admin {request.user.email}"
            )
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Error generating dashboard metrics for {request.user.email}: {str(e)}",
                exc_info=True
            )
            return Response(
                {
                    "error": "No se pudieron generar las métricas del dashboard",
                    "detail": "Error interno del servidor. Por favor, contacte al administrador."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
