"""
Review views.

Handles review creation and listing for completed orders.
"""
import logging
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from users.models import WorkerProfile
from ..models import ServiceOrder, Review
from ..serializers import (
    ReviewSerializer,
    ReviewCreateSerializer,
    ReviewListSerializer,
)
from ..permissions import IsOrderClient, IsOrderParticipantReadOnly
from ..pagination import ReviewPagination
from ..throttles import ReviewCreateThrottle

logger = logging.getLogger(__name__)


class CreateReviewView(generics.CreateAPIView):
    """
    POST /api/orders/{order_id}/review/
    
    Create a review for a completed order.
    
    **Throttling**: 10 requests/hour per user.
    
    **Restrictions**:
    - Only the order's client can create the review
    - Order must be in COMPLETED status
    - Only one review per order allowed (OneToOneField)
    - Rating must be between 1 and 5 stars
    - Comment must be at least 10 characters
    
    **Request Body**:
    ```json
    {
        "rating": 5,
        "comment": "Excellent work, very professional and punctual"
    }
    ```
    
    **Errors**:
    - 400: Order not completed / Duplicate review / Validation failed
    - 403: User is not the order's client
    - 404: Order not found
    - 429: Rate limit exceeded (more than 10 reviews/hour)
    """
    serializer_class = ReviewCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderClient]
    throttle_classes = [ReviewCreateThrottle]
    
    def get_object(self):
        """Get the service order from URL to validate permissions."""
        order_id = self.kwargs.get('order_id')
        order = get_object_or_404(
            ServiceOrder.objects.select_related('client', 'worker', 'worker__user'),
            pk=order_id
        )
        return order
    
    def create(self, request, *args, **kwargs):
        """Create review with validations."""
        service_order = self.get_object()
        
        # Check object-level permissions
        self.check_object_permissions(request, service_order)
        
        # Pass context to serializer
        serializer = self.get_serializer(
            data=request.data,
            context={
                'request': request,
                'service_order': service_order
            }
        )
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        
        logger.info(
            f"Review created: Order #{service_order.id}, Rating {review.rating}⭐ "
            f"by {request.user.email}"
        )
        
        # Return full serializer with all information
        full_serializer = ReviewSerializer(review)
        return Response(full_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def worker_reviews(request, worker_id):
    """
    GET /api/workers/{worker_id}/reviews/?page=1&page_size=10
    
    Paginated list of reviews for a worker.
    
    **Permissions**: Public for any authenticated user.
    
    **Query Parameters**:
    - page: Page number (default: 1)
    - page_size: Reviews per page (default: 10, max: 100)
    
    **Errors**:
    - 404: Worker not found
    """
    # Get the worker
    worker = get_object_or_404(
        WorkerProfile.objects.select_related('user'),
        pk=worker_id
    )
    
    # Optimized queryset
    queryset = Review.objects.filter(
        service_order__worker=worker
    ).select_related('service_order__client').order_by('-created_at')
    
    # Apply pagination
    paginator = ReviewPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    # Serialize reviews
    serializer = ReviewListSerializer(page, many=True)
    
    # Prepare worker data for response
    worker_data = {
        'id': str(worker.id),
        'name': f"{worker.user.first_name} {worker.user.last_name}".strip() or worker.user.email,
        'profession': worker.get_profession_display(),
        'average_rating': str(worker.average_rating),
        'total_reviews': queryset.count()
    }
    
    # Pass worker_data to paginator via context
    request.parser_context = {'worker_data': worker_data}
    
    logger.debug(
        f"Retrieved {queryset.count()} reviews for worker {worker_id} "
        f"by {request.user.email}"
    )
    
    # Return paginated response
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def list_reviews(request):
    """
    GET /api/reviews/?worker={worker_id}&page={page}&page_size={page_size}
    
    Paginated list of reviews filtered by worker.
    
    **Query Parameters** (required):
    - worker (int): WorkerProfile ID (not User ID)
    - page (int, optional): Page number (default: 1)
    - page_size (int, optional): Items per page (default: 10, max: 100)
    
    **Errors**:
    - 400: 'worker' parameter required
    - 404: Worker not found
    """
    # Validate worker parameter is present
    worker_id = request.query_params.get('worker')
    
    if not worker_id:
        return Response(
            {'error': "The 'worker' parameter is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get the worker
    worker = get_object_or_404(
        WorkerProfile.objects.select_related('user'),
        pk=worker_id
    )
    
    # Optimized queryset - only reviews for completed orders
    queryset = Review.objects.filter(
        service_order__worker=worker,
        service_order__status='COMPLETED'
    ).select_related('service_order__client').order_by('-created_at')
    
    # Apply pagination
    paginator = ReviewPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    # Serialize reviews with reviewer ID
    reviews_data = []
    for review in page:
        reviews_data.append({
            'id': review.id,
            'reviewer': {
                'id': review.reviewer.id,
                'first_name': review.reviewer.first_name,
                'last_name': review.reviewer.last_name
            },
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.isoformat(),
            'service_order_id': review.service_order.id
        })
    
    # Prepare worker data
    worker_data = {
        'id': worker.id,
        'average_rating': str(worker.average_rating),
        'total_reviews': queryset.count()
    }
    
    # Pass worker_data to paginator via context
    request.parser_context = {'worker_data': worker_data}
    
    logger.info(
        f"Retrieved {len(reviews_data)} reviews for worker {worker_id} "
        f"(total: {queryset.count()}) by {request.user.email}"
    )
    
    # Return custom paginated response
    return Response({
        'count': paginator.page.paginator.count,
        'next': paginator.get_next_link(),
        'previous': paginator.get_previous_link(),
        'results': reviews_data,
        'worker': worker_data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsOrderParticipantReadOnly])
def get_order_review(request, order_id):
    """
    GET /api/orders/{order_id}/review/
    
    Get the review for a specific order.
    
    **Permissions:**
    - Only the order's client or worker can see the review
    - Review is public once created (for participants)
    
    **Response 404 Not Found** - No review exists for this order
    
    **Notes:**
    - Only one review per order exists
    - Only the client can create the review
    - Order must be in COMPLETED status to have a review
    - Reviewer must be the order's client (reviewer_id == order.client_id)
    """
    # Get order and verify existence
    order = get_object_or_404(
        ServiceOrder.objects.select_related('client', 'worker__user'),
        pk=order_id
    )
    
    # Verify permissions manually (decorator verifies has_permission, 
    # but we need to verify has_object_permission)
    permission = IsOrderParticipantReadOnly()
    if not permission.has_object_permission(request, None, order):
        logger.warning(
            f"User {request.user.email} attempted to access review for order {order_id} "
            f"without being a participant"
        )
        return Response(
            {'detail': 'You do not have permission to view this information.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Attempt to get the review
    try:
        review = Review.objects.select_related('service_order__client').get(
            service_order=order
        )
        
        # Serialize the review
        response_data = {
            'id': review.id,
            'reviewer': {
                'id': review.reviewer.id,
                'first_name': review.reviewer.first_name,
                'last_name': review.reviewer.last_name
            },
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.isoformat(),
            'service_order_id': review.service_order.id
        }
        
        logger.info(
            f"Review #{review.id} for order {order_id} retrieved by {request.user.email}"
        )
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Review.DoesNotExist:
        logger.info(
            f"No review found for order {order_id}. User: {request.user.email}"
        )
        return Response(
            {'detail': 'No review found for this order.'},
            status=status.HTTP_404_NOT_FOUND
        )
