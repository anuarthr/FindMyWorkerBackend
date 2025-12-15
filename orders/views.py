from django.shortcuts import render
from rest_framework import generics, permissions
from .models import ServiceOrder
from .serializers import ServiceOrderSerializer

class ServiceOrderCreateView(generics.CreateAPIView):
    queryset = ServiceOrder.objects.all()
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)

