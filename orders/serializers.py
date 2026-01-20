from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from decimal import Decimal
from .models import ServiceOrder, WorkHoursLog, Message


class ServiceOrderSerializer(serializers.ModelSerializer):
    """
    Serializador completo para ServiceOrder.
    Incluye campos calculados y relacionados para una vista integral.
    """
    status_display = serializers.CharField(
        source='get_status_display', 
        read_only=True
    )
    client_email = serializers.EmailField(
        source='client.email', 
        read_only=True
    )
    worker_name = serializers.SerializerMethodField()
    
    worker_hourly_rate = serializers.DecimalField(
        source='worker.hourly_rate',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = ServiceOrder
        fields = [
            'id',
            'client',
            'client_email',
            'worker',
            'worker_name',
            'worker_hourly_rate',
            'description',
            'status',
            'status_display',
            'agreed_price',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['client', 'status', 'agreed_price', 'created_at', 'updated_at']

    def get_worker_name(self, obj):
        """
        Retorna el nombre completo del trabajador o su email si no tiene nombre.
        
        Args:
            obj (ServiceOrder): Instancia de la orden
            
        Returns:
            str: Nombre completo o email del trabajador
        """
        if not obj.worker or not obj.worker.user:
            return "N/A"
        
        full_name = f"{obj.worker.user.first_name} {obj.worker.user.last_name}".strip()
        return full_name if full_name else obj.worker.user.email

    def validate_worker(self, value):
        """
        Valida que el trabajador seleccionado sea válido para crear una orden.
        
        Validaciones:
        - No puede crear orden consigo mismo
        - El trabajador debe estar verificado
        - El trabajador debe tener tarifa horaria configurada
        """
        request = self.context.get('request')
        if not request:
            return value
            
        user = request.user
        
        # Validar que no sea el mismo usuario
        if value.user == user:
            raise serializers.ValidationError(
                _("No puedes crear una orden para ti mismo.")
            )
        
        # Validar que el trabajador esté verificado
        if not value.is_verified:
            raise serializers.ValidationError(
                _("Este trabajador aún no está verificado.")
            )
        
        # Validar que tenga tarifa horaria configurada
        if not value.hourly_rate or value.hourly_rate <= 0:
            raise serializers.ValidationError(
                _("Este trabajador no tiene una tarifa horaria configurada.")
            )
        
        return value

class ServiceOrderStatusSerializer(serializers.ModelSerializer):
    """
    Serializador para actualizar solo el estado de una orden.
    Implementa máquina de estados con transiciones válidas.
    
    Transiciones permitidas:
    - PENDING -> ACCEPTED (por trabajador)
    - PENDING -> CANCELLED (por cliente/trabajador)
    - ACCEPTED -> IN_ESCROW (por cliente al pagar)
    - ACCEPTED -> CANCELLED (por cliente/trabajador)
    - IN_ESCROW -> COMPLETED (por cliente al confirmar trabajo)
    """
    class Meta:
        model = ServiceOrder
        fields = ['status']

    def validate_status(self, value):
        """
        Valida que la transición de estado sea válida.
        
        Args:
            value (str): Nuevo estado solicitado
            
        Returns:
            str: Estado validado
            
        Raises:
            ValidationError: Si la transición no es válida
        """
        instance = self.instance
        if not instance:
            return value
            
        current_status = instance.status

        # Definir transiciones válidas desde cada estado
        valid_transitions = {
            'PENDING': ['ACCEPTED', 'CANCELLED'],
            'ACCEPTED': ['IN_ESCROW', 'CANCELLED'],
            'IN_ESCROW': ['COMPLETED'],
            'COMPLETED': [],  # Estado final, no se puede cambiar
            'CANCELLED': [],  # Estado final, no se puede cambiar
        }

        allowed_statuses = valid_transitions.get(current_status, [])

        if value not in allowed_statuses:
            raise serializers.ValidationError(
                _(f"No se puede cambiar de {current_status} a {value}. "
                  f"Transiciones válidas: {', '.join(allowed_statuses) if allowed_statuses else 'ninguna'}")
            )

        # Validación especial para COMPLETED
        if value == 'COMPLETED':
            if not instance.can_transition_to_completed():
                raise serializers.ValidationError(
                    _("No se puede completar la orden sin horas aprobadas. El precio acordado debe ser mayor a $0.")
                )

        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        """
        Actualiza el estado de la orden.
        Usa transacción atómica para garantizar consistencia.
        
        Args:
            instance (ServiceOrder): Instancia de la orden
            validated_data (dict): Datos validados
            
        Returns:
            ServiceOrder: Orden actualizada
        """
        new_status = validated_data.get('status')
        
        # Lógica específica por estado (hooks para futura expansión)
        if new_status == 'ACCEPTED':
            # Aquí se podría notificar al cliente
            pass
        
        if new_status == 'IN_ESCROW':
            # Aquí se podría procesar el pago
            pass
        
        # Si se completa la orden, actualizar precio final
        if new_status == 'COMPLETED':
            instance.update_agreed_price()
        
        return super().update(instance, validated_data)

class WorkHoursLogSerializer(serializers.ModelSerializer):
    """
    Serializador para registros de horas trabajadas.
    Incluye cálculos automáticos de pago y validaciones de negocio.
    """
    calculated_payment = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        read_only=True,
        help_text="Pago calculado (horas * tarifa horaria del trabajador)"
    )
    status_display = serializers.CharField(
        read_only=True,
        help_text="Estado legible del registro"
    )
    worker_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkHoursLog
        fields = [
            'id',
            'service_order',
            'date',
            'hours',
            'description',
            'approved_by_client',
            'calculated_payment',
            'status_display',
            'worker_name',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['approved_by_client', 'created_at', 'updated_at']

    def get_worker_name(self, obj):
        """Retorna el nombre del trabajador de la orden."""
        if not obj.service_order or not obj.service_order.worker:
            return "N/A"
        user = obj.service_order.worker.user
        return f"{user.first_name} {user.last_name}".strip() or user.email

    def validate(self, data):
        """
        Validaciones a nivel de serializador para WorkHoursLog.
        
        Validaciones:
        - Solo el trabajador puede registrar horas
        - Solo en órdenes ACCEPTED o IN_ESCROW
        - Horas deben ser positivas
        - No se pueden registrar horas futuras
        - Solo un registro por día por orden
        """
        request = self.context.get('request')
        service_order = data.get('service_order') or (self.instance.service_order if self.instance else None)
        
        # Validar permisos del trabajador
        if service_order and request:
            if service_order.worker.user != request.user:
                raise serializers.ValidationError(
                    _("Solo el trabajador asignado puede registrar horas.")
                )
        
        # Validar estado de la orden
        if service_order and service_order.status not in ['ACCEPTED', 'IN_ESCROW']:
            raise serializers.ValidationError(
                _("Solo se pueden registrar horas en órdenes aceptadas o en garantía.")
            )
        
        # Validar que las horas sean positivas
        hours = data.get('hours')
        if hours is not None:
            if hours <= 0:
                raise serializers.ValidationError({
                    'hours': _("Las horas deben ser mayores a 0.")
                })
            if hours > 24:
                raise serializers.ValidationError({
                    'hours': _("No se pueden registrar más de 24 horas por día.")
                })
        
        # Validar fecha
        date = data.get('date')
        if date:
            from datetime import date as date_type
            if date > date_type.today():
                raise serializers.ValidationError({
                    'date': _("No se pueden registrar horas futuras.")
                })
            
            # Validar único registro por día (solo en creación)
            if not self.instance and service_order:
                existing = WorkHoursLog.objects.filter(
                    service_order=service_order,
                    date=date
                ).exists()
                if existing:
                    raise serializers.ValidationError({
                        'date': _(f"Ya existe un registro de horas para la fecha {date}.")
                    })
        
        return data

class WorkHoursLogUpdateSerializer(serializers.ModelSerializer):
    """
    Serializador para actualizar registros de horas existentes.
    Solo permite modificar horas y descripción.
    """
    class Meta:
        model = WorkHoursLog
        fields = ['hours', 'description']
    
    def validate_hours(self, value):
        """Valida que las horas sean válidas."""
        if value <= 0:
            raise serializers.ValidationError(_("Las horas deben ser mayores a 0."))
        if value > 24:
            raise serializers.ValidationError(_("No se pueden registrar más de 24 horas."))
        return value

class WorkHoursApprovalSerializer(serializers.Serializer):
    """
    Serializador para aprobar/rechazar registros de horas.
    Solo el cliente de la orden puede usar este serializador.
    """
    approved = serializers.BooleanField(
        required=True,
        help_text="true para aprobar, false para revocar aprobación"
    )
    
    def validate_approved(self, value):
        """Valida que el valor sea booleano."""
        if not isinstance(value, bool):
            raise serializers.ValidationError(_("Debe ser true o false."))
        return value
    
class MessageSerializer(serializers.ModelSerializer):
    """
    Serializador para mensajes de chat en órdenes de servicio.
    Incluye información del remitente y validaciones de contenido.
    """
    sender_name = serializers.SerializerMethodField()
    sender_email = serializers.EmailField(
        source='sender.email', 
        read_only=True
    )
    sender_role = serializers.CharField(
        source='sender.role', 
        read_only=True
    )
    
    class Meta:
        model = Message
        fields = [
            'id',
            'service_order',
            'sender',
            'sender_name',
            'sender_email',
            'sender_role',
            'content',
            'is_read',
            'timestamp'
        ]
        read_only_fields = ['sender', 'timestamp', 'is_read']
    
    def get_sender_name(self, obj):
        """
        Retorna el nombre completo del remitente o su email.
        
        Args:
            obj (Message): Instancia del mensaje
            
        Returns:
            str: Nombre completo o email del remitente
        """
        if not obj.sender:
            return "Usuario desconocido"
        full_name = f"{obj.sender.first_name} {obj.sender.last_name}".strip()
        return full_name if full_name else obj.sender.email
    
    def validate_content(self, value):
        """
        Valida el contenido del mensaje.
        
        Validaciones:
        - No puede estar vacío
        - Máximo 5000 caracteres
        - No puede contener solo espacios en blanco
        
        Args:
            value (str): Contenido del mensaje
            
        Returns:
            str: Contenido validado y limpio
            
        Raises:
            ValidationError: Si el contenido no es válido
        """
        if not value or not value.strip():
            raise serializers.ValidationError(
                _("El mensaje no puede estar vacío.")
            )
        
        if len(value) > 5000:
            raise serializers.ValidationError(
                _("El mensaje no puede exceder 5000 caracteres.")
            )
        
        # Limpiar espacios en blanco al inicio y final
        cleaned_value = value.strip()
        
        # Validar que después de limpiar aún tenga contenido
        if not cleaned_value:
            raise serializers.ValidationError(
                _("El mensaje no puede contener solo espacios en blanco.")
            )
        
        return cleaned_value