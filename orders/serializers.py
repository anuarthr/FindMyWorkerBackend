from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import ServiceOrder, WorkHoursLog, Message

class ServiceOrderSerializer(serializers.ModelSerializer):
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
        full_name = f"{obj.worker.user.first_name} {obj.worker.user.last_name}".strip()
        return full_name if full_name else obj.worker.user.email

    def validate_worker(self, value):
        user = self.context['request'].user
        
        if value.user == user:
            raise serializers.ValidationError(
                _("You cannot create an order for yourself.")
            )
        
        if not value.is_verified:
            raise serializers.ValidationError(
                _("This worker is not verified yet.")
            )
        
        return value

class ServiceOrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceOrder
        fields = ['status']

    def validate_status(self, value):
        instance = self.instance
        current_status = instance.status

        valid_transitions = {
            'PENDING': ['ACCEPTED', 'CANCELLED'],
            'ACCEPTED': ['IN_ESCROW', 'CANCELLED'],
            'IN_ESCROW': ['COMPLETED'],
            'COMPLETED': [],
            'CANCELLED': [],
        }

        allowed_statuses = valid_transitions.get(current_status, [])

        if value not in allowed_statuses:
            raise serializers.ValidationError(
                _(f"Cannot transition from {current_status} to {value}.")
            )

        if value == 'COMPLETED':
            if not instance.can_transition_to_completed():
                raise serializers.ValidationError(
                    _("No se puede completar la orden sin horas aprobadas. El precio acordado es $0.")
                )

        return value

    def update(self, instance, validated_data):
        new_status = validated_data.get('status')
        
        if new_status == 'ACCEPTED':
            pass
        
        if new_status == 'IN_ESCROW':
            pass
        
        if new_status == 'COMPLETED':
            instance.update_agreed_price()
        
        return super().update(instance, validated_data)

class WorkHoursLogSerializer(serializers.ModelSerializer):
    calculated_payment = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        read_only=True
    )
    status_display = serializers.CharField(read_only=True)
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
        user = obj.service_order.worker.user
        return f"{user.first_name} {user.last_name}".strip() or user.email

    def validate(self, data):
        request = self.context.get('request')
        service_order = data.get('service_order')
        
        if service_order and request:
            if service_order.worker.user != request.user:
                raise serializers.ValidationError(
                    _("Solo el trabajador asignado puede registrar horas.")
                )
        
        if service_order and service_order.status not in ['ACCEPTED', 'IN_ESCROW']:
            raise serializers.ValidationError(
                _("Solo se pueden registrar horas en órdenes aceptadas o en garantía.")
            )
        
        if data.get('hours') and data['hours'] <= 0:
            raise serializers.ValidationError({
                'hours': _("Las horas deben ser mayor a 0.")
            })
        
        from datetime import date
        if data.get('date') and data['date'] > date.today():
            raise serializers.ValidationError({
                'date': _("No se pueden registrar horas futuras.")
            })
        
        return data

class WorkHoursLogUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkHoursLog
        fields = ['hours', 'description']

class WorkHoursApprovalSerializer(serializers.Serializer):
    approved = serializers.BooleanField(required=True)
    
    def validate_approved(self, value):
        if not isinstance(value, bool):
            raise serializers.ValidationError(_("Debe ser true o false."))
        return value
    
class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    sender_role = serializers.CharField(source='sender.role', read_only=True)
    
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
        full_name = f"{obj.sender.first_name} {obj.sender.last_name}".strip()
        return full_name if full_name else obj.sender.email
    
    def validate_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                _("El mensaje no puede estar vacío.")
            )
        
        if len(value) > 5000:
            raise serializers.ValidationError(
                _("El mensaje no puede exceder 5000 caracteres.")
            )
        
        return value.strip()