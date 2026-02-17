"""
Orders app views.

Organized into focused modules:
    - order_views: Service order CRUD and worker metrics
    - hours_views: Work hours logging and approval
    - message_views: Order messaging
    - review_views: Review creation and listing
"""

# Order Management
from .order_views import (
    ServiceOrderCreateView,
    ServiceOrderListView,
    ServiceOrderDetailView,
    ServiceOrderStatusUpdateView,
    worker_metrics,
    completed_orders_without_portfolio,
    StandardResultsSetPagination,
)

# Work Hours
from .hours_views import (
    WorkHoursLogViewSet,
    order_price_summary,
)

# Messaging
from .message_views import (
    order_messages,
)

# Reviews
from .review_views import (
    CreateReviewView,
    worker_reviews,
    list_reviews,
    get_order_review,
)

__all__ = [
    # Pagination
    'StandardResultsSetPagination',
    # Orders
    'ServiceOrderCreateView',
    'ServiceOrderListView',
    'ServiceOrderDetailView',
    'ServiceOrderStatusUpdateView',
    'worker_metrics',
    'completed_orders_without_portfolio',
    # Hours
    'WorkHoursLogViewSet',
    'order_price_summary',
    # Messages
    'order_messages',
    # Reviews
    'CreateReviewView',
    'worker_reviews',
    'list_reviews',
    'get_order_review',
]
