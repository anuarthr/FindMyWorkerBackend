"""
Authentication views.

Handles user registration and JWT token generation.
"""
from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model

from ..serializers import (
    UserRegistrationSerializer,
    CustomTokenObtainPairSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/
    
    Public endpoint for user registration.
    Creates a new user account (CLIENT or WORKER).
    """
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegistrationSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/auth/login/
    
    Public endpoint for obtaining JWT access/refresh tokens.
    Extends simple-jwt's default view with custom error messages.
    """
    serializer_class = CustomTokenObtainPairSerializer
