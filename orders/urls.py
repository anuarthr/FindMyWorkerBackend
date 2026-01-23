from django.urls import path
from rest_framework import routers
from .views import (
    ServiceOrderCreateView,
    ServiceOrderListView,
    ServiceOrderDetailView,
    ServiceOrderStatusUpdateView,
    worker_metrics,
    WorkHoursLogViewSet,
    order_price_summary,
    order_messages,
    CreateReviewView,
    worker_reviews,
    list_reviews
)

router = routers.SimpleRouter()
router.register(r'(?P<order_pk>\d+)/work-hours', WorkHoursLogViewSet, basename='order-workhours')

work_hours_list = WorkHoursLogViewSet.as_view({
    'get': 'list',
    'post': 'create'
})

work_hours_detail = WorkHoursLogViewSet.as_view({
    'get': 'retrieve',
    'patch': 'partial_update',
    'delete': 'destroy'
})

work_hours_approve = WorkHoursLogViewSet.as_view({
    'post': 'approve'
})

urlpatterns = [
    path('', ServiceOrderCreateView.as_view(), name='order-create'),
    path('list/', ServiceOrderListView.as_view(), name='order-list'),
    path('<int:pk>/', ServiceOrderDetailView.as_view(), name='order-detail'),
    path('<int:pk>/status/', ServiceOrderStatusUpdateView.as_view(), name='order-status-update'),
    path('workers/me/metrics/', worker_metrics, name='worker-metrics'),
    path('<int:order_pk>/work-hours/', work_hours_list, name='order-work-hours-list'),
    path('<int:order_pk>/work-hours/<int:pk>/', work_hours_detail, name='order-work-hours-detail'),
    path('<int:order_pk>/work-hours/<int:pk>/approve/', work_hours_approve, name='order-work-hours-approve'),
    path('<int:pk>/price-summary/', order_price_summary, name='order-price-summary'),
    path('<int:pk>/messages/', order_messages, name='order-messages'),
    # Reviews
    path('<int:order_id>/review/', CreateReviewView.as_view(), name='order-create-review'),
    path('workers/<int:worker_id>/reviews/', worker_reviews, name='worker-reviews'),
] + router.urls