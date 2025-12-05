from rest_framework import viewsets, filters
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from .models import WorkerProfile
from .serializers import WorkerProfileSerializer

class WorkerDiscoveryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorkerProfile.objects.filter(is_verified=True)
    serializer_class = WorkerProfileSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['profession', 'bio']

    def get_queryset(self):
        qs = super().get_queryset()
        
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        radius = self.request.query_params.get('radius', 10)

        if lat and lng:
            try:
                user_location = Point(float(lng), float(lat), srid=4326)
                qs = qs.annotate(
                    distance=Distance('location', user_location)
                ).filter(distance__lte=D(km=float(radius)))
                # Ordenar del más cercano al más lejano
                qs = qs.order_by('distance')
                
            except (ValueError, TypeError):
                pass 
        
        return qs
