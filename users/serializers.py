from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import WorkerProfile
from django.contrib.gis.geos import Point

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'avatar']
        read_only_fields = ['id', 'role', 'email']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name', 'role'] 

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data['role'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user
    
class WorkerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) 
    latitude = serializers.FloatField(write_only=True, required=False)
    longitude = serializers.FloatField(write_only=True, required=False)

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
        read_only_fields = ['is_verified', 'average_rating']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        if instance.location:
            data['latitude'] = instance.location.y
            data['longitude'] = instance.location.x
        else:
            data['latitude'] = None
            data['longitude'] = None
        return data

    def update(self, instance, validated_data):
        lat = validated_data.pop('latitude', None)
        lng = validated_data.pop('longitude', None)

        if lat is not None and lng is not None:
            instance.location = Point(float(lng), float(lat), srid=4326)
        return super().update(instance, validated_data)