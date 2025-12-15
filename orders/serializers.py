from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import ServiceOrder


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

    class Meta:
        model = ServiceOrder
        fields = [
            'id',
            'client',
            'client_email',
            'worker',
            'worker_name',
            'description',
            'status',
            'status_display',
            'agreed_price',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['client', 'status', 'agreed_price', 'created_at', 'updated_at']

    def get_worker_name(self, obj):
        return f"{obj.worker.user.first_name} {obj.worker.user.last_name}".strip() or obj.worker.user.email

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
