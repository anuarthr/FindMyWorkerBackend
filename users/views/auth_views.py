"""
Authentication views.

Handles user registration, JWT token generation, and password management.
"""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.utils.translation import gettext_lazy as _

from ..serializers import (
    UserRegistrationSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
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


class ChangePasswordView(generics.GenericAPIView):
    """
    POST /api/auth/change-password/
    
    Authenticated endpoint for changing user password.
    Requires current password for security validation.
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            "detail": _("Contraseña actualizada exitosamente.")
        }, status=status.HTTP_200_OK)


class PasswordResetRequestView(generics.GenericAPIView):
    """
    POST /api/auth/password-reset/
    
    Public endpoint for requesting password reset.
    Sends reset token to user's email (email sending to be implemented).
    """
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            # Generar token de reset
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # TODO: Enviar email con el token y uid
            # Por ahora, retornamos el token en desarrollo (REMOVER EN PRODUCCIÓN)
            # En producción, solo retornar mensaje de éxito
            
            return Response({
                "detail": _("Si el email existe, recibirás instrucciones para resetear tu contraseña."),
                # SOLO PARA DESARROLLO - REMOVER EN PRODUCCIÓN
                "dev_token": token,
                "dev_uid": uid,
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            # Por seguridad, retornamos el mismo mensaje
            return Response({
                "detail": _("Si el email existe, recibirás instrucciones para resetear tu contraseña.")
            }, status=status.HTTP_200_OK)


class PasswordResetConfirmView(generics.GenericAPIView):
    """
    POST /api/auth/password-reset-confirm/
    
    Public endpoint for confirming password reset with token.
    """
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # En implementación completa, el token vendría en la URL
        # Por ahora lo recibimos en el body
        token = serializer.validated_data['token']
        
        # TODO: Decodificar uid de la URL
        # Por ahora, buscamos el token en todos los usuarios activos
        # ESTO ES TEMPORAL - En producción usar uid de URL
        
        user_found = None
        for user in User.objects.filter(is_active=True):
            if default_token_generator.check_token(user, token):
                user_found = user
                break
        
        if not user_found:
            return Response({
                "detail": _("Token inválido o expirado.")
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Actualizar contraseña
        user_found.set_password(serializer.validated_data['new_password'])
        user_found.save()
        
        return Response({
            "detail": _("Contraseña restablecida exitosamente.")
        }, status=status.HTTP_200_OK)
