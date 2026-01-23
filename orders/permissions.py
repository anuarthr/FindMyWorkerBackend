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


class IsOrderClient(permissions.BasePermission):
    """
    Permiso personalizado: Solo el cliente de la orden puede crear review.
    """
    message = "Solo el cliente de esta orden puede crear una review."
    
    def has_permission(self, request, view):
        """Nivel de vista: verificar autenticación"""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Nivel de objeto: verificar ownership de la orden"""
        # obj es ServiceOrder
        return obj.client.id == request.user.id


class IsOrderParticipantReadOnly(permissions.BasePermission):
    """
    Permiso personalizado: Solo el cliente o trabajador de la orden pueden ver (GET).
    Usado específicamente para endpoints de solo lectura.
    """
    message = "Solo los participantes de esta orden pueden ver esta información."
    
    def has_permission(self, request, view):
        """Nivel de vista: verificar autenticación y método"""
        # Solo permitir método GET
        if request.method != 'GET':
            return False
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Nivel de objeto: verificar que el usuario sea participante"""
        # obj puede ser Review u Order
        if hasattr(obj, 'service_order'):
            order = obj.service_order
        else:
            order = obj
        
        return (
            order.client.id == request.user.id or 
            order.worker.user.id == request.user.id
        )
