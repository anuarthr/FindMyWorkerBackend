from django.urls import path
from .views import (ServiceOrderCreateView,
    ServiceOrderListView,
    ServiceOrderDetailView,
    ServiceOrderStatusUpdateView)

urlpatterns = [
    path('', ServiceOrderCreateView.as_view(), name='order-create'),
    path('list/', ServiceOrderListView.as_view(), name='order-list'),
    path('<int:pk>/', ServiceOrderDetailView.as_view(), name='order-detail'),
    path('<int:pk>/status/', ServiceOrderStatusUpdateView.as_view(), name='order-status-update'),
]
