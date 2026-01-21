from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import WorkerProfile
from django.contrib.gis.geos import Point
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'avatar']
        read_only_fields = ['id', 'role', 'email']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    worker_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name', 'role', 'worker_profile'] 

    def get_worker_profile(self, obj):
        """Retorna el ID del worker profile si el usuario es WORKER"""
        if obj.role == 'WORKER' and hasattr(obj, 'worker_profile'):
            return obj.worker_profile.id
        return None

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data['role'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user

class WorkerProfileUpdateSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True, required=False, allow_null=True)
    longitude = serializers.FloatField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = WorkerProfile
        fields = [
            'profession', 
            'bio', 
            'years_experience', 
            'hourly_rate', 
            'latitude', 
            'longitude'
        ]

    def update(self, instance, validated_data):
        lat = validated_data.pop('latitude', None)
        lng = validated_data.pop('longitude', None)

        if lat is not None and lng is not None:
            instance.location = Point(float(lng), float(lat), srid=4326)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

class WorkerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) 
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = WorkerProfile
        fields = [
            'id', 
            'user',
            'profession', 
            'bio', 
            'years_experience', 
            'hourly_rate', 
            'is_verified', 
            'average_rating',
            'latitude', 
            'longitude'
        ]
        read_only_fields = ['id', 'user', 'is_verified', 'average_rating']

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        'no_active_account': _('No se encontró una cuenta activa con estas credenciales.')
    }

    def validate(self, attrs):
        data = super().validate(attrs)
        return data