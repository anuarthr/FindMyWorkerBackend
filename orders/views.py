from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, Q, F
from datetime import datetime
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied
from .models import ServiceOrder, WorkHoursLog
from .serializers import (
    ServiceOrderSerializer,
    ServiceOrderStatusSerializer,
    WorkHoursLogSerializer,
    WorkHoursLogUpdateSerializer,
    WorkHoursApprovalSerializer
)
from .permissions import IsOrderParticipant, CanChangeOrderStatus

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

class WorkHoursLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar registros de horas trabajadas.
    - list/create: GET/POST /api/orders/{order_id}/work-hours/
    - retrieve/update/destroy: GET/PATCH/DELETE /api/orders/{order_id}/work-hours/{id}/
    - approve: POST /api/orders/{order_id}/work-hours/{id}/approve/
    """
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant]
    serializer_class = WorkHoursLogSerializer

    def get_queryset(self):
        """Filtrar por orden específica"""
        order_id = self.kwargs.get('order_pk')
        return WorkHoursLog.objects.filter(
            service_order_id=order_id
        ).select_related('service_order', 'service_order__worker', 'service_order__worker__user')

    def get_serializer_class(self):
        """Usar serializer específico según la acción"""
        if self.action in ['update', 'partial_update']:
            return WorkHoursLogUpdateSerializer
        return WorkHoursLogSerializer

    def perform_create(self, serializer):
        """Asignar la orden automáticamente"""
        order_id = self.kwargs.get('order_pk')
        order = get_object_or_404(ServiceOrder, pk=order_id)
        
        # Verificar que el usuario es el trabajador
        if order.worker.user != self.request.user:
            raise PermissionDenied(_("Solo el trabajador puede registrar horas."))
        
        serializer.save(service_order=order)

    @action(detail=True, methods=['post'])
    def approve(self, request, order_pk=None, pk=None):
        """
        POST /api/orders/{order_id}/work-hours/{id}/approve/
        El cliente aprueba o rechaza el registro de horas.
        Body: {"approved": true}
        """
        work_log = self.get_object()
        order = work_log.service_order
        
        if order.client != request.user:
            return Response(
                {'detail': _('Solo el cliente puede aprobar horas.')},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = WorkHoursApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approved = serializer.validated_data['approved']
        work_log.approved_by_client = approved
        work_log.save()
        
        if approved:
            order.update_agreed_price()
        
        return Response({
            'id': work_log.id,
            'approved_by_client': work_log.approved_by_client,
            'calculated_payment': float(work_log.calculated_payment),
            'order_agreed_price': float(order.agreed_price) if order.agreed_price else 0,
            'message': _('Horas aprobadas exitosamente') if approved else _('Aprobación revocada')
        })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def order_price_summary(request, pk):
    """
    GET /api/orders/{id}/price-summary/
    Devuelve un resumen del precio calculado de la orden.
    """
    order = get_object_or_404(ServiceOrder, pk=pk)
    
    if order.client != request.user and order.worker.user != request.user:
        return Response(
            {'detail': _('No autorizado.')},
            status=status.HTTP_403_FORBIDDEN
        )
    
    work_hours = order.work_hours.all()
    
    total_hours_approved = sum(
        log.hours for log in work_hours if log.approved_by_client
    )
    total_hours_pending = sum(
        log.hours for log in work_hours if not log.approved_by_client
    )
    
    payment_approved = sum(
        log.calculated_payment for log in work_hours if log.approved_by_client
    )
    payment_pending = sum(
        log.calculated_payment for log in work_hours if not log.approved_by_client
    )
    
    return Response({
        'order_id': order.id,
        'worker_hourly_rate': float(order.worker.hourly_rate or 0),
        'total_hours_approved': float(total_hours_approved),
        'total_hours_pending': float(total_hours_pending),
        'payment_approved': float(payment_approved),
        'payment_pending': float(payment_pending),
        'agreed_price': float(order.agreed_price) if order.agreed_price else 0,
        'can_complete_order': order.can_transition_to_completed()
    })