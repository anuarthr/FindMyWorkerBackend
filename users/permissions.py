"""
Permisos personalizados para el módulo de usuarios.

Provee clases de permisos reutilizables para portfolio y gestión de perfiles.
Sigue el principio Open/Closed: fácil de extender sin modificar.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsWorkerAndOwnerOrReadOnly(BasePermission):
    """
    Permiso para items de portfolio.
    
    Reglas:
    - GET/HEAD/OPTIONS: Cualquiera autenticado (lectura pública)
    - POST: Solo usuarios con rol WORKER
    - PATCH/PUT/DELETE: Solo owner WORKER o ADMIN
    """
    
    def has_permission(self, request, view):
        """Verifica permisos a nivel de vista (antes de obtener el objeto)."""
        if request.method in SAFE_METHODS:
            return True
        
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.method == "POST":
            return request.user.role == "WORKER"
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Verifica permisos a nivel de objeto (después de obtener el objeto)."""
        if request.method in SAFE_METHODS:
            return True
        
        user = request.user
        
        if user.role == "ADMIN" or user.is_superuser:
            return True
        
        if user.role == "WORKER":
            return obj.worker.user_id == user.id
        
        return False


class IsWorkerOwner(BasePermission):
    """
    Permiso que solo permite acceso al WORKER propietario.
    
    Más estricto que IsWorkerAndOwnerOrReadOnly - sin lectura pública.
    Útil para endpoints privados de perfil de trabajador.
    """
    
    def has_permission(self, request, view):
        """Verifica si el usuario es WORKER autenticado."""
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role == "WORKER"
    
    def has_object_permission(self, request, view, obj):
        """Verifica si el usuario es el propietario del perfil."""
        user = request.user
        
        if user.role == "ADMIN" or user.is_superuser:
            return True
        
        return obj.worker.user_id == user.id
