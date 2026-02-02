"""
Work Hours views.

Handles work hours logging, approval, and payment calculations.
"""
import logging
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from ..models import ServiceOrder, WorkHoursLog
from ..serializers import (
    WorkHoursLogSerializer,
    WorkHoursLogUpdateSerializer,
    WorkHoursApprovalSerializer,
)
from ..permissions import IsOrderParticipant

logger = logging.getLogger(__name__)


class WorkHoursLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing work hours logs.
    
    Endpoints:
    - list/create: GET/POST /api/orders/{order_id}/work-hours/
    - retrieve/update/destroy: GET/PATCH/DELETE /api/orders/{order_id}/work-hours/{id}/
    - approve: POST /api/orders/{order_id}/work-hours/{id}/approve/
    
    Only order participants can access.
    Only the worker can create/edit hours.
    Only the client can approve hours.
    """
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant]
    serializer_class = WorkHoursLogSerializer

    def get_queryset(self):
        """Get work hours logs for a specific order."""
        order_id = self.kwargs.get('order_pk')
        return WorkHoursLog.objects.filter(
            service_order_id=order_id
        ).select_related(
            'service_order', 'service_order__worker', 'service_order__worker__user'
        ).order_by('-date', '-created_at')

    def get_serializer_class(self):
        """Use appropriate serializer based on action."""
        if self.action in ['update', 'partial_update']:
            return WorkHoursLogUpdateSerializer
        return WorkHoursLogSerializer

    def perform_create(self, serializer):
        """Create a new work hours log. Only the worker can do this."""
        order_id = self.kwargs.get('order_pk')
        order = get_object_or_404(ServiceOrder, pk=order_id)
        
        # Validate only the worker can log hours
        if order.worker.user != self.request.user:
            logger.warning(
                f"User {self.request.user.email} attempted to log hours "
                f"on order {order_id} without being the worker"
            )
            raise PermissionDenied(_("Only the worker can log hours."))
        
        work_log = serializer.save(service_order=order)
        logger.info(
            f"Work log #{work_log.id} created for order {order_id} "
            f"by {self.request.user.email}: {work_log.hours}h on {work_log.date}"
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, order_pk=None, pk=None):
        """
        POST /api/orders/{order_id}/work-hours/{id}/approve/
        
        Client approves or rejects the work hours log.
        
        Body: {"approved": true}
        
        When approved, automatically updates the order's agreed price.
        """
        work_log = self.get_object()
        order = work_log.service_order
        
        # Validate only the client can approve
        if order.client != request.user:
            logger.warning(
                f"User {request.user.email} attempted to approve hours "
                f"on order {order_pk} without being the client"
            )
            return Response(
                {'detail': _('Only the client can approve hours.')},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate input data
        serializer = WorkHoursApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approved = serializer.validated_data['approved']
        
        # Update approval status
        work_log.approved_by_client = approved
        work_log.save(update_fields=['approved_by_client', 'updated_at'])
        
        # If approved, update order price
        if approved:
            order.update_agreed_price()
            logger.info(
                f"Hours #{work_log.id} approved by {request.user.email}. "
                f"Order price updated to ${order.agreed_price}"
            )
        else:
            logger.info(f"Hours #{work_log.id} approval revoked by {request.user.email}")
        
        return Response({
            'id': work_log.id,
            'approved_by_client': work_log.approved_by_client,
            'calculated_payment': float(work_log.calculated_payment),
            'order_agreed_price': float(order.agreed_price) if order.agreed_price else 0,
            'message': _('Hours approved successfully') if approved else _('Approval revoked')
        })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def order_price_summary(request, pk):
    """
    GET /api/orders/{id}/price-summary/
    
    Returns detailed price summary for the order:
    - Total hours (approved and pending)
    - Calculated payments (approved and pending)
    - Current agreed price
    - Indicator if order can be completed
    
    Only accessible by the client or worker of the order.
    """
    order = get_object_or_404(
        ServiceOrder.objects.select_related('worker'),
        pk=pk
    )
    
    # Validate permissions
    if order.client != request.user and order.worker.user != request.user:
        logger.warning(
            f"User {request.user.email} attempted to access price summary "
            f"for order {pk} without permissions"
        )
        return Response(
            {'detail': _('Not authorized.')},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get work hours optimized
    work_hours = order.work_hours.all()
    
    # Calculate totals
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
    
    summary = {
        'order_id': order.id,
        'worker_hourly_rate': float(order.worker.hourly_rate or 0),
        'total_hours_approved': float(total_hours_approved),
        'total_hours_pending': float(total_hours_pending),
        'payment_approved': float(payment_approved),
        'payment_pending': float(payment_pending),
        'agreed_price': float(order.agreed_price) if order.agreed_price else 0,
        'can_complete_order': order.can_transition_to_completed()
    }
    
    logger.debug(f"Price summary generated for order {pk}")
    return Response(summary)
