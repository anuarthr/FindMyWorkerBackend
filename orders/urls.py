from django.urls import path
from .views import ServiceOrderCreateView

urlpatterns = [
    path('', ServiceOrderCreateView.as_view(), name='order-create'),
]
