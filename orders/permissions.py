from rest_framework import permissions

class IsOrderParticipant(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            obj.client == request.user or 
            obj.worker.user == request.user
        )

class CanChangeOrderStatus(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        new_status = request.data.get('status')

        # PENDING -> ACCEPTED: Solo el trabajador
        if obj.status == 'PENDING' and new_status == 'ACCEPTED':
            return obj.worker.user == user

        # ACCEPTED -> IN_ESCROW: Solo el cliente (simula pago)
        if obj.status == 'ACCEPTED' and new_status == 'IN_ESCROW':
            return obj.client == user

        # IN_ESCROW -> COMPLETED: Solo el cliente
        if obj.status == 'IN_ESCROW' and new_status == 'COMPLETED':
            return obj.client == user

        # PENDING/ACCEPTED -> CANCELLED: Cliente o Trabajador
        if new_status == 'CANCELLED' and obj.status in ['PENDING', 'ACCEPTED']:
            return obj.client == user or obj.worker.user == user

        return False