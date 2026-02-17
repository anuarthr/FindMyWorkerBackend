"""
Vistas de Portfolio.

Maneja operaciones CRUD para items de portfolio de trabajadores.
Implementa HU4: Portafolio Visual de Evidencias.
"""

import logging
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from ..models import PortfolioItem
from ..serializers import (
    PortfolioItemSerializer,
    PortfolioItemCreateSerializer,
)
from ..permissions import IsWorkerAndOwnerOrReadOnly

logger = logging.getLogger(__name__)


class MyPortfolioListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/users/workers/portfolio/
    POST /api/users/workers/portfolio/
    
    Gestiona items de portfolio del trabajador autenticado.
    
    **GET**: Lista todos los items del trabajador autenticado
    **POST**: Crea nuevo item (multipart/form-data)
    
    **Permisos**: 
    - GET: WORKER autenticado
    - POST: Solo WORKER
    
    **Cuerpo (POST)**:
    - title (string, requerido, máx 255): Título del proyecto
    - description (string, opcional): Descripción detallada
    - image (file, requerido, máx 2MB): Imagen JPG/PNG/WEBP
    
    **Errores**:
    - 400: Imagen inválida (tamaño/formato), campos faltantes
    - 401: No autenticado
    - 403: Usuario no es WORKER
    """
    
    permission_classes = [IsWorkerAndOwnerOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        """Retorna items de portfolio solo para el trabajador autenticado."""
        user = self.request.user
        
        if not user.is_authenticated:
            return PortfolioItem.objects.none()
        
        worker_profile = getattr(user, "worker_profile", None)
        if worker_profile is None:
            return PortfolioItem.objects.none()
        
        return PortfolioItem.objects.filter(worker=worker_profile).select_related(
            "worker", "worker__user", "order", "order__client"
        )
    
    def get_serializer_class(self):
        """Usa diferentes serializers para operaciones de lectura/escritura."""
        if self.request.method == "POST":
            return PortfolioItemCreateSerializer
        return PortfolioItemSerializer
    
    def get_serializer_context(self):
        """Incluye request en contexto del serializer para construcción de URLs."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        """
        Crea un item de portfolio y retorna representación completa.
        
        Usa PortfolioItemCreateSerializer para validación/creación,
        luego serializa con PortfolioItemSerializer para incluir order_info.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        # Log de creación
        logger.info(
            f"Portfolio item creado: {instance.title} "
            f"por trabajador {instance.worker.user.email} (ID: {instance.id})"
        )
        
        # Serializar respuesta con el serializer de lectura (incluye order_info)
        read_serializer = PortfolioItemSerializer(instance, context={'request': request})
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def perform_create(self, serializer):
        """Override no necesario - lógica movida a create()."""
        pass


class WorkerPortfolioListView(generics.ListAPIView):
    """
    GET /api/users/workers/{worker_id}/portfolio/
    
    Lista items públicos de portfolio para un trabajador específico.
    
    **Permisos**: Público (AllowAny)
    
    **Parámetros de Query**:
    - page (int, opcional): Número de página
    - page_size (int, opcional): Items por página (default: 10)
    
    **Errores**:
    - 404: Worker ID no encontrado
    """
    
    serializer_class = PortfolioItemSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        """Retorna items de portfolio para el trabajador especificado."""
        worker_id = self.kwargs.get("worker_id")
        return PortfolioItem.objects.filter(
            worker_id=worker_id
        ).select_related("worker", "worker__user", "order", "order__client")
    
    def get_serializer_context(self):
        """Incluye request en contexto del serializer."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class PortfolioItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/users/workers/portfolio/{id}/
    PATCH  /api/users/workers/portfolio/{id}/
    DELETE /api/users/workers/portfolio/{id}/
    
    Obtiene, actualiza o elimina un item específico de portfolio.
    
    **Permisos**:
    - GET: Cualquiera
    - PATCH/DELETE: Solo owner WORKER o ADMIN
    
    **PATCH** (multipart/form-data o JSON):
    - title (string, opcional)
    - description (string, opcional)
    - image (file, opcional): Nueva imagen para reemplazar existente
    
    **Respuestas**:
    - 200: Actualizado exitosamente
    - 204: Eliminado exitosamente
    - 403: No es owner o admin
    - 404: Item no encontrado
    """
    
    queryset = PortfolioItem.objects.select_related("worker", "worker__user", "order", "order__client")
    permission_classes = [IsWorkerAndOwnerOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_serializer_class(self):
        """Usa serializer de escritura para modificaciones, lectura para obtención."""
        if self.request.method in ["PATCH", "PUT"]:
            return PortfolioItemCreateSerializer
        return PortfolioItemSerializer
    
    def get_serializer_context(self):
        """Incluye request en contexto del serializer."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
    
    def update(self, request, *args, **kwargs):
        """
        Actualiza un item de portfolio y retorna representación completa.
        
        Usa PortfolioItemCreateSerializer para validación/actualización,
        luego serializa con PortfolioItemSerializer para incluir order_info.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()
        
        # Log de actualización
        logger.info(
            f"Portfolio item actualizado: {updated_instance.title} "
            f"(ID: {updated_instance.id}) por {request.user.email}"
        )
        
        # Serializar respuesta con el serializer de lectura
        read_serializer = PortfolioItemSerializer(updated_instance, context={'request': request})
        return Response(read_serializer.data)
    
    def perform_update(self, serializer):
        """Override no necesario - lógica movida a update()."""
        pass
    
    def perform_destroy(self, instance):
        """Registra eliminación de items de portfolio."""
        logger.info(
            f"Portfolio item eliminado: {instance.title} "
            f"(ID: {instance.id}) por {self.request.user.email}"
        )
        instance.delete()
