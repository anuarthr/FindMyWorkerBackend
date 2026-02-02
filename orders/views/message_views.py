"""
Message views.

Handles order messaging functionality.
"""
import logging
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from ..models import ServiceOrder, Message
from ..serializers import MessageSerializer

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def order_messages(request, pk):
    """
    GET /api/orders/{id}/messages/?limit=50
    
    Returns message history for a specific order.
    Only accessible by the client or worker of the order.
    
    Query params:
    - limit: Maximum number of messages to return (default: 50, max: 200)
    
    Returns messages ordered by timestamp ascending (oldest first).
    """
    order = get_object_or_404(
        ServiceOrder.objects.select_related('client', 'worker', 'worker__user'),
        pk=pk
    )
    
    # Validate permissions
    if order.client != request.user and order.worker.user != request.user:
        logger.warning(
            f"User {request.user.email} attempted to access messages "
            f"for order {pk} without permissions"
        )
        return Response(
            {'detail': _('You do not have permission to access this chat.')},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get message limit from query params
    try:
        limit = int(request.query_params.get('limit', 50))
        limit = min(max(limit, 1), 200)  # Between 1 and 200
    except (ValueError, TypeError):
        limit = 50
    
    # Get messages optimized with select_related
    messages = Message.objects.filter(
        service_order=order
    ).select_related('sender').order_by('timestamp')[:limit]
    
    serializer = MessageSerializer(messages, many=True)
    
    logger.debug(
        f"Retrieved {len(messages)} messages for order {pk} "
        f"by {request.user.email}"
    )
    
    return Response({
        'order_id': order.id,
        'total_messages': messages.count(),
        'limit_applied': limit,
        'messages': serializer.data
    }, status=status.HTTP_200_OK)
