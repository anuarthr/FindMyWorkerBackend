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
from django.db.models import Count

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


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_chat_read(request, pk):
    """
    POST /api/orders/{id}/chat/mark-read/

    Marks all unread messages in the order as read for the authenticated user.
    Only accessible by the client or worker of the order.

    Response:
        {"marked_read": 3}
    """
    order = get_object_or_404(
        ServiceOrder.objects.select_related('client', 'worker__user'),
        pk=pk
    )

    if order.client != request.user and order.worker.user != request.user:
        return Response(
            {'detail': _('You do not have permission to access this chat.')},
            status=status.HTTP_403_FORBIDDEN
        )

    count = (
        Message.objects
        .filter(service_order=order, is_read=False)
        .exclude(sender=request.user)
        .update(is_read=True)
    )

    logger.debug(f"Marked {count} messages as read in order {pk} for {request.user.email}")
    return Response({'marked_read': count})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def chat_unread(request):
    """
    GET /api/orders/chat/unread/

    Returns total unread message count and a per-order breakdown for the
    authenticated user (works for both clients and workers).

    Response:
        {
            "total": 5,
            "orders": [
                {"order_id": 12, "unread_count": 3},
                {"order_id": 7,  "unread_count": 2}
            ]
        }
    """
    user = request.user

    # All orders where the user is a participant
    participant_order_ids = list(
        ServiceOrder.objects.filter(client=user).values_list('id', flat=True)
    ) + list(
        ServiceOrder.objects.filter(worker__user=user).values_list('id', flat=True)
    )

    rows = (
        Message.objects
        .filter(service_order_id__in=participant_order_ids, is_read=False)
        .exclude(sender=user)
        .values('service_order_id')
        .annotate(unread_count=Count('id'))
    )

    result = {row['service_order_id']: row['unread_count'] for row in rows}

    return Response({
        'total': sum(result.values()),
        'orders': [
            {'order_id': order_id, 'unread_count': count}
            for order_id, count in result.items()
        ]
    })
