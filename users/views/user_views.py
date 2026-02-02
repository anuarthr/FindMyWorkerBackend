"""
User and Worker Profile views.

Handles user profile management and worker profile CRUD operations.
"""
from rest_framework import generics, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import WorkerProfile
from ..serializers import (
    UserSerializer,
    WorkerProfileSerializer,
    WorkerProfileUpdateSerializer,
)


class ManageUserView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/users/me/
    
    Retrieve or update the authenticated user's profile.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ManageWorkerProfileView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/users/worker-profile/
    
    Retrieve or update the authenticated user's worker profile.
    Creates the profile automatically if it doesn't exist.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, created = WorkerProfile.objects.get_or_create(user=self.request.user)
        return profile
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return WorkerProfileSerializer
        return WorkerProfileUpdateSerializer


class WorkerAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin-only viewset for managing worker profiles.
    
    Endpoints:
        GET /api/admin/workers/ - List all workers
        GET /api/admin/workers/{id}/ - Worker detail
        GET /api/admin/workers/pending/ - List unverified workers
        POST /api/admin/workers/{id}/approve/ - Approve a worker
    """
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get list of workers pending verification."""
        pending_workers = WorkerProfile.objects.filter(is_verified=False)
        serializer = self.get_serializer(pending_workers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a worker for platform use."""
        worker = self.get_object()
        worker.is_verified = True
        worker.save()
        return Response({'status': 'approved', 'id': worker.id})
