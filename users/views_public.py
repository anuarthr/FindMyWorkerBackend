from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from .models import WorkerProfile
from .serializers import WorkerProfileSerializer
from .filters import WorkerFilter

class WorkerDiscoveryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorkerProfile.objects.filter(is_verified=True)
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
        """
        qs = super().get_queryset()
        
        # Extracción de params (usando tus nombres de variable)
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
                
                # LÓGICA HÍBRIDA:
                # Solo ordenamos por distancia si el usuario NO pidió otro orden (como precio).
                # Esto evita que 'order_by(distance)' anule al 'OrderingFilter'.
                if not user_ordering:
                    qs = qs.order_by('distance')
                
            except (ValueError, TypeError):
                # Si las coordenadas son basura, ignoramos la parte geoespacial
                pass 
        
        # Si no hay coordenadas y no hay orden específico, ordenamos por rating por defecto
        elif not user_ordering:
            qs = qs.order_by('-average_rating')

        return qs