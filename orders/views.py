from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import ServiceOrder
from .serializers import ServiceOrderSerializer, ServiceOrderStatusSerializer
from .permissions import IsOrderParticipant, CanChangeOrderStatus
from django.db.models import Q

class ServiceOrderCreateView(generics.CreateAPIView):
    queryset = ServiceOrder.objects.all()
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)

class ServiceOrderListView(generics.ListAPIView):
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = ServiceOrder.objects.filter(
            Q(client=user) | Q(worker__user=user)
        ).select_related('client', 'worker', 'worker__user')

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        return queryset

class ServiceOrderDetailView(generics.RetrieveAPIView):
    queryset = ServiceOrder.objects.select_related('client', 'worker', 'worker__user')
    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant]

class ServiceOrderStatusUpdateView(generics.UpdateAPIView):
    queryset = ServiceOrder.objects.select_related('client', 'worker', 'worker__user')
    serializer_class = ServiceOrderStatusSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant, CanChangeOrderStatus]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        full_serializer = ServiceOrderSerializer(instance)
        return Response(full_serializer.data)
