from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.core.cache import cache
from datetime import timedelta
import logging

from users.models import User, WorkerProfile
from orders.models import ServiceOrder

logger = logging.getLogger(__name__)

CACHE_TTL = 60 * 5  # 5 minutos


class DashboardService:
    """
    Servicio que encapsula todas las queries de métricas del admin.
    Principio SRP: una clase, una responsabilidad (métricas del dashboard).
    """

    CACHE_KEY = "admin_dashboard_metrics"

    @classmethod
    def get_full_metrics(cls) -> dict:
        """
        Punto de entrada principal para obtener todas las métricas del dashboard.
        
        Returns:
            dict: Diccionario con tres categorías de métricas:
                - user_statistics: Métricas de usuarios
                - profession_statistics: Profesiones más demandadas
                - transaction_statistics: Métricas de órdenes y transacciones
        """
        cached = cache.get(cls.CACHE_KEY)
        if cached:
            logger.debug("Dashboard metrics retrieved from cache")
            return cached

        logger.info("Generating fresh dashboard metrics")
        metrics = {
            "user_statistics": cls._get_user_statistics(),
            "profession_statistics": cls._get_profession_statistics(),
            "transaction_statistics": cls._get_transaction_statistics(),
        }

        cache.set(cls.CACHE_KEY, metrics, CACHE_TTL)
        return metrics

    @staticmethod
    def _get_user_statistics() -> dict:
        """
        Calcula estadísticas de usuarios registrados.
        
        Returns:
            dict: Total de usuarios, distribución por rol, y crecimiento temporal
        """
        now = timezone.now()
        by_role = User.objects.values("role").annotate(count=Count("id"))

        return {
            "total": User.objects.count(),
            "by_role": {entry["role"]: entry["count"] for entry in by_role},
            "growth": {
                "last_30_days": User.objects.filter(
                    date_joined__gte=now - timedelta(days=30)
                ).count(),
                "last_7_days": User.objects.filter(
                    date_joined__gte=now - timedelta(days=7)
                ).count(),
            },
        }

    @staticmethod
    def _get_profession_statistics() -> list:
        """
        Obtiene las profesiones más populares ordenadas por número de trabajadores.
        
        Returns:
            list: Top 10 profesiones con su conteo de trabajadores
        """
        return list(
            WorkerProfile.objects.values("profession")
            .annotate(worker_count=Count("id"))
            .order_by("-worker_count")[:10]
        )

    @staticmethod
    def _get_transaction_statistics() -> dict:
        """
        Calcula métricas de órdenes de servicio y transacciones.
        
        Incluye:
            - Total de órdenes por estado
            - Ingresos por estado
            - Tendencia mensual de órdenes e ingresos (últimos 6 meses)
            - Estimación de comisión de plataforma (10% de órdenes completadas)
        
        Returns:
            dict: Métricas completas de transacciones
        """
        now = timezone.now()
        by_status = ServiceOrder.objects.values("status").annotate(
            count=Count("id"),
            total_revenue=Sum("agreed_price"),
        )

        # Tendencia mensual: últimos 6 meses
        revenue_trend = []
        for i in range(5, -1, -1):
            # Calcular inicio del mes
            month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            # Calcular inicio del siguiente mes
            month_end = (month_start + timedelta(days=31)).replace(day=1)
            
            agg = ServiceOrder.objects.filter(
                created_at__gte=month_start, created_at__lt=month_end
            ).aggregate(orders=Count("id"), revenue=Sum("agreed_price"))
            
            revenue_trend.append(
                {
                    "month": month_start.strftime("%Y-%m"),
                    "orders": agg["orders"] or 0,
                    "revenue": str(agg["revenue"] or "0.00"),
                }
            )

        # Calcular comisión de plataforma (10% de órdenes completadas)
        platform_commission = (
            ServiceOrder.objects.filter(status="COMPLETED").aggregate(
                total=Sum("agreed_price")
            )["total"]
            or 0
        )

        return {
            "total_orders": ServiceOrder.objects.count(),
            "by_status": {
                entry["status"]: {
                    "count": entry["count"],
                    "revenue": str(entry["total_revenue"] or "0.00"),
                }
                for entry in by_status
            },
            "revenue_trend": revenue_trend,
            "platform_commission_10pct": str(round(platform_commission / 10, 2)),
        }

    @classmethod
    def invalidate_cache(cls):
        """
        Invalida el caché de métricas del dashboard.
        Debe ser llamado cuando se crean/actualizan usuarios u órdenes.
        """
        try:
            cache.delete(cls.CACHE_KEY)
            logger.info("Dashboard cache invalidated successfully")
        except Exception as e:
            logger.warning(f"Failed to invalidate dashboard cache: {e}")
