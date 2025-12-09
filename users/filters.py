import django_filters
from .models import WorkerProfile

class WorkerFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name='hourly_rate', lookup_expr='gte') #>=
    max_price = django_filters.NumberFilter(field_name='hourly_rate', lookup_expr='lte') #<=
    
    min_rating = django_filters.NumberFilter(field_name='average_rating', lookup_expr='gte')
    
    profession = django_filters.CharFilter(field_name='profession', lookup_expr='icontains')

    class Meta:
        model = WorkerProfile
        fields = ['profession', 'is_verified']
