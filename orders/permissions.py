from rest_framework import permissions

class IsOrderParticipant(permissions.BasePermission):
    message = "You don't have permission to access this order."
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'service_order'):
            order = obj.service_order
        else:
            order = obj
        return (
            order.client == request.user or 
            order.worker.user == request.user
        )

class CanChangeOrderStatus(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        new_status = request.data.get('status')

        if obj.status == 'PENDING' and new_status == 'ACCEPTED':
            return obj.worker.user == user

        if obj.status == 'ACCEPTED' and new_status == 'IN_ESCROW':
            return obj.client == user

        if obj.status == 'IN_ESCROW' and new_status == 'COMPLETED':
            return obj.client == user

        if new_status == 'CANCELLED' and obj.status in ['PENDING', 'ACCEPTED']:
            return obj.client == user or obj.worker.user == user

        return False