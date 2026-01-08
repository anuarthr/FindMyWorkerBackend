from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Count, Sum
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import ServiceOrder
from .serializers import ServiceOrderSerializer, ServiceOrderStatusSerializer
from .permissions import IsOrderParticipant, CanChangeOrderStatus
from users.models import WorkerProfile

class ServiceOrderCreateView(generics.CreateAPIView):
    queryset = ServiceOrder.objects.all()
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)

class ServiceOrderListView(generics.ListAPIView):
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = ServiceOrder.objects.filter(
            Q(client=user) | Q(worker__user=user)
        ).select_related('client', 'worker', 'worker__user')

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        return queryset

class ServiceOrderDetailView(generics.RetrieveAPIView):
    queryset = ServiceOrder.objects.select_related('client', 'worker', 'worker__user')
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant]

class ServiceOrderStatusUpdateView(generics.UpdateAPIView):
    queryset = ServiceOrder.objects.select_related('client', 'worker', 'worker__user')
    serializer_class = ServiceOrderStatusSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant, CanChangeOrderStatus]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        full_serializer = ServiceOrderSerializer(instance)
        return Response(full_serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def worker_metrics(request):
    """
    GET /api/orders/workers/me/metrics/
    Devuelve métricas agregadas del trabajador autenticado.
    """
    if request.user.role != 'WORKER':
        return Response(
            {'detail': _('Solo trabajadores pueden acceder a estas métricas.')},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        worker_profile = WorkerProfile.objects.get(user=request.user)
    except WorkerProfile.DoesNotExist:
        return Response(
            {'detail': _('Perfil de trabajador no encontrado.')},
            status=status.HTTP_404_NOT_FOUND
        )
    
    now = timezone.now()
    current_month = now.month
    current_year = now.year
    
    metrics = ServiceOrder.objects.filter(
        worker=worker_profile
    ).aggregate(
        active_jobs=Count(
            'id', 
            filter=Q(status__in=['ACCEPTED', 'IN_ESCROW'])
        ),
        monthly_earnings=Sum(
            'agreed_price',
            filter=Q(
                status='COMPLETED',
                updated_at__month=current_month,
                updated_at__year=current_year
            )
        ),
        total_earnings=Sum(
            'agreed_price', 
            filter=Q(status='COMPLETED')
        ),
        completed_jobs=Count(
            'id', 
            filter=Q(status='COMPLETED')
        )
    )
    
    return Response({
        'active_jobs': metrics['active_jobs'] or 0,
        'monthly_earnings': float(metrics['monthly_earnings'] or 0),
        'total_earnings': float(metrics['total_earnings'] or 0),
        'completed_jobs': metrics['completed_jobs'] or 0,
        'average_rating': float(worker_profile.average_rating)
    }, status=status.HTTP_200_OK)
