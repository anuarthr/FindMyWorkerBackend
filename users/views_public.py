import logging
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from .models import WorkerProfile
from .serializers import WorkerProfileSerializer
from .filters import WorkerFilter

logger = logging.getLogger(__name__)

class WorkerDiscoveryViewSet(viewsets.ReadOnlyModelViewSet):
    # Catálogo público: todos los trabajadores de cuentas activas.
    # Regla de negocio: los NO verificados no se excluyen, aparecen al final
    # (ordenamiento por defecto -is_verified). select_related evita N+1 al
    # serializar el usuario anidado.
    queryset = (
        WorkerProfile.objects
        .filter(user__is_active=True)
        .select_related('user')
    )
    serializer_class = WorkerProfileSerializer

    filter_backends = [
        DjangoFilterBackend,    # Maneja min_price, max_price, min_rating
        filters.SearchFilter,   # Maneja ?search= (Texto general)
        filters.OrderingFilter  # Maneja ?ordering= (Precio/Rating)
    ]

    # Conectamos tu clase de filtros personalizada
    filterset_class = WorkerFilter

    # Campos para búsqueda de texto (?search=)
    search_fields = ['profession', 'bio']

    # Campos permitidos para ordenamiento (?ordering=)
    ordering_fields = ['hourly_rate', 'average_rating']

    def get_queryset(self):
        """
        Combina filtrado geoespacial manual con los filtros automáticos de DRF.

        Orden por defecto: verificados primero (-is_verified), luego el criterio
        secundario (cercanía o rating). Si el cliente pide ?ordering= explícito,
        el OrderingFilter de DRF tiene prioridad.
        """
        qs = super().get_queryset()

        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        radius = self.request.query_params.get('radius', 10)

        # Detectamos si el usuario pidió un orden específico (ej: precio)
        user_ordering = self.request.query_params.get('ordering')

        if lat and lng:
            try:
                user_location = Point(float(lng), float(lat), srid=4326)

                # Anotamos la distancia y filtramos el radio
                qs = qs.annotate(
                    distance=Distance('location', user_location)
                ).filter(distance__lte=D(km=float(radius)))

                # Solo ordenamos manualmente si el usuario NO pidió otro orden,
                # para no anular al OrderingFilter.
                if not user_ordering:
                    qs = qs.order_by('-is_verified', 'distance')

            except (ValueError, TypeError):
                # Si las coordenadas son basura, ignoramos la parte geoespacial
                pass

        # Sin coordenadas ni orden explícito: verificados primero, luego rating
        elif not user_ordering:
            qs = qs.order_by('-is_verified', '-average_rating')

        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['recommendation_scores'] = getattr(self, '_recommendation_scores', {})
        return ctx

    def list(self, request, *args, **kwargs):
        search = request.query_params.get('search', '').strip()
        self._recommendation_scores = {}
        if search:
            try:
                from .services import RecommendationEngine
                engine = RecommendationEngine()
                recs = engine.get_recommendations(query=search, strategy='tfidf', top_n=200)
                self._recommendation_scores = {
                    str(r['worker'].id): r['relevance_percentage'] for r in recs
                }
            except Exception:
                logger.debug('Recommendation scoring skipped for catalog search', exc_info=True)
        return super().list(request, *args, **kwargs)