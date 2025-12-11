from django.shortcuts import render
from rest_framework import generics, permissions
from .serializers import UserSerializer, UserRegistrationSerializer
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from .models import WorkerProfile
from .serializers import WorkerProfileSerializer, CustomTokenObtainPairSerializer
from rest_framework import generics, permissions, viewsets
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegistrationSerializer

class ManageUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class ManageWorkerProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = WorkerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, created = WorkerProfile.objects.get_or_create(user=self.request.user)
        return profile
    
class WorkerAdminViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [permissions.IsAdminUser] # Solo Staff/Superuser

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Lista trabajadores NO verificados"""
        pending_workers = WorkerProfile.objects.filter(is_verified=False)
        serializer = self.get_serializer(pending_workers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Aprueba un trabajador específico"""
        worker = self.get_object()
        worker.is_verified = True
        worker.save()
        return Response({'status': 'approved', 'id': worker.id})

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer