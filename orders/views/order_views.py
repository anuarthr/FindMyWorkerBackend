"""
Service Order views.

Handles order CRUD operations and worker performance metrics.
"""
import logging
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Sum, Count, Q, Prefetch
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from users.models import WorkerProfile
from ..models import ServiceOrder, WorkHoursLog
from ..serializers import (
    ServiceOrderSerializer,
    ServiceOrderStatusSerializer,
)
from ..permissions import IsOrderParticipant, CanChangeOrderStatus

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination for list endpoints.
    - page_size: 20 items per page by default
    - max_page_size: Maximum 100 items per page
    - page_size_query_param: Allows client to specify size with ?page_size=N
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ServiceOrderCreateView(generics.CreateAPIView):
    """
    POST /api/orders/
    
    Create a new service order.
    Only authenticated users can create orders.
    """
    queryset = ServiceOrder.objects.all()
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """Automatically assign current client to the order."""
        order = serializer.save(client=self.request.user)
        logger.info(
            f"Order #{order.id} created by {self.request.user.email} "
            f"for worker {order.worker.user.email}"
        )


class ServiceOrderListView(generics.ListAPIView):
    """
    GET /api/orders/?status=PENDING
    
    List orders for the authenticated user (as client or worker).
    
    Query params:
    - status: Filter by status (PENDING, ACCEPTED, IN_ESCROW, COMPLETED, CANCELLED)
    - page: Page number
    - page_size: Items per page (max 100)
    """
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Get user's orders with query optimization."""
        user = self.request.user
        
        # Optimize with select_related and prefetch_related
        queryset = ServiceOrder.objects.filter(
            Q(client=user) | Q(worker__user=user)
        ).select_related(
            'client', 'worker', 'worker__user'
        ).prefetch_related(
            Prefetch(
                'work_hours',
                queryset=WorkHoursLog.objects.filter(approved_by_client=True)
            )
        )

        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())
            logger.debug(f"User {user.email} filtered orders by status: {status_filter}")

        return queryset.order_by('-created_at')


class ServiceOrderDetailView(generics.RetrieveAPIView):
    """
    GET /api/orders/{id}/
    
    Get details of a specific order.
    Only accessible by the client or worker of the order.
    """
    queryset = ServiceOrder.objects.select_related('client', 'worker', 'worker__user')
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant]


class ServiceOrderStatusUpdateView(generics.UpdateAPIView):
    """
    PATCH /api/orders/{id}/status/
    
    Update the status of an order.
    State transitions are controlled by permissions.
    """
    queryset = ServiceOrder.objects.select_related('client', 'worker', 'worker__user')
    serializer_class = ServiceOrderStatusSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant, CanChangeOrderStatus]

    def update(self, request, *args, **kwargs):
        """Update status and return complete order."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_status = instance.status
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        new_status = instance.status
        logger.info(
            f"Order #{instance.id} updated from {old_status} to {new_status} "
            f"by {request.user.email}"
        )

        # Return full serializer with all fields
        full_serializer = ServiceOrderSerializer(instance)
        return Response(full_serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def worker_metrics(request):
    """
    GET /api/orders/workers/me/metrics/
    
    Returns complete metrics for the authenticated worker:
    - active_jobs: Active jobs (ACCEPTED + IN_ESCROW)
    - monthly_earnings: Monthly earnings based on approved hours
    - total_earnings: Total earnings from completed orders
    - completed_jobs: Total completed jobs
    - average_rating: Worker's average rating
    
    Only accessible by users with WORKER role.
    """
    # Validate user is a worker
    if request.user.role != 'WORKER':
        logger.warning(
            f"User {request.user.email} with role {request.user.role} "
            f"attempted to access worker metrics"
        )
        return Response(
            {'detail': _('Only workers can access these metrics.')},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get worker profile
    try:
        worker_profile = WorkerProfile.objects.select_related('user').get(user=request.user)
    except WorkerProfile.DoesNotExist:
        logger.error(f"Worker profile not found for {request.user.email}")
        return Response(
            {'detail': _('Worker profile not found.')},
            status=status.HTTP_404_NOT_FOUND
        )
    
    now = timezone.now()
    current_month = now.month
    current_year = now.year
    
    # Get order metrics with a single optimized query
    order_metrics = ServiceOrder.objects.filter(
        worker=worker_profile
    ).aggregate(
        active_jobs=Count(
            'id', 
            filter=Q(status__in=['ACCEPTED', 'IN_ESCROW'])
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
    
    # Calculate current month earnings
    month_logs = WorkHoursLog.objects.filter(
        service_order__worker=worker_profile,
        approved_by_client=True,
        date__month=current_month,
        date__year=current_year
    ).select_related('service_order', 'service_order__worker')
    
    monthly_earnings = sum(log.calculated_payment for log in month_logs)
    
    metrics_data = {
        'active_jobs': order_metrics['active_jobs'] or 0,
        'monthly_earnings': float(monthly_earnings),
        'total_earnings': float(order_metrics['total_earnings'] or 0),
        'completed_jobs': order_metrics['completed_jobs'] or 0,
        'average_rating': float(worker_profile.average_rating)
    }
    
    logger.info(f"Metrics generated for worker {request.user.email}")
    return Response(metrics_data, status=status.HTTP_200_OK)
