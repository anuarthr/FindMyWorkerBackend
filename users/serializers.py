from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import WorkerProfile, RecommendationLog
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


# ============================================================================
# SERIALIZERS DEL SISTEMA DE RECOMENDACIÓN (HU2)
# ============================================================================

class RecommendationRequestSerializer(serializers.Serializer):
    """
    Serializer para validar requests al endpoint de recomendaciones.
    
    Valida y normaliza los parámetros de búsqueda incluyendo:
        - Query de búsqueda en lenguaje natural
        - Estrategia de ranking (tfidf/fallback/hybrid)
        - Filtros geográficos y de calidad
    """
    
    query = serializers.CharField(
        required=True,
        max_length=500,
        help_text="Texto de búsqueda en lenguaje natural. Ej: 'Plomero urgente para reparar fuga'"
    )
    
    strategy = serializers.ChoiceField(
        choices=['tfidf', 'fallback', 'hybrid'],
        default='tfidf',
        help_text="Estrategia de ranking: tfidf (ML puro), fallback (geo+rating), hybrid (combinado)"
    )
    
    top_n = serializers.IntegerField(
        default=5,
        min_value=1,
        max_value=20,
        help_text="Número de recomendaciones a retornar (1-20)"
    )
    
    # Filtros opcionales
    min_rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=2,
        min_value=0,
        max_value=5,
        required=False,
        allow_null=True,
        help_text="Rating mínimo del trabajador (0-5)"
    )
    
    latitude = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=-90,
        max_value=90,
        help_text="Latitud del usuario para filtrado geográfico"
    )
    
    longitude = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=-180,
        max_value=180,
        help_text="Longitud del usuario para filtrado geográfico"
    )
    
    max_distance_km = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=200,
        help_text="Distancia máxima en kilómetros (solo si latitude/longitude están presentes)"
    )
    
    profession = serializers.ChoiceField(
        choices=WorkerProfile.ProfessionChoices.choices,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Filtrar por profesión específica"
    )
    
    def validate(self, data):
        """
        Validación cruzada de campos.
        """
        # Si hay latitude o longitude, ambos deben estar presentes
        lat = data.get('latitude')
        lng = data.get('longitude')
        
        if (lat is not None and lng is None) or (lng is not None and lat is None):
            raise serializers.ValidationError(
                "Latitude y longitude deben proporcionarse juntos"
            )
        
        # Si hay max_distance_km, debe haber coordenadas
        if data.get('max_distance_km') and (lat is None or lng is None):
            raise serializers.ValidationError(
                "max_distance_km requiere latitude y longitude"
            )
        
        # Limpiar query
        query = data.get('query', '').strip()
        if len(query) < 3:
            raise serializers.ValidationError({
                'query': 'La búsqueda debe tener al menos 3 caracteres'
            })
        
        return data


class WorkerRecommendationSerializer(serializers.ModelSerializer):
    """
    Serializer para trabajadores recomendados con información adicional de scoring.
    """
    
    user = UserSerializer(read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    # Campos adicionales de recomendación
    score = serializers.FloatField(read_only=True, help_text="Score de relevancia (0-1)")
    relevance_percentage = serializers.FloatField(read_only=True, help_text="Relevancia en porcentaje")
    distance_km = serializers.FloatField(read_only=True, required=False, help_text="Distancia en km (si aplica)")
    explanation = serializers.JSONField(read_only=True, help_text="Explicación de por qué se recomendó (XAI)")
    
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
            'longitude',
            # Campos de recomendación
            'score',
            'relevance_percentage',
            'distance_km',
            'explanation',
        ]
        read_only_fields = ['id', 'user', 'is_verified', 'average_rating']
    
    def get_latitude(self, obj):
        return obj.location.y if obj.location else None
    
    def get_longitude(self, obj):
        return obj.location.x if obj.location else None


class RecommendationResponseSerializer(serializers.Serializer):
    """
    Serializer para la respuesta completa del endpoint de recomendaciones.
    """
    
    query = serializers.CharField(help_text="Query original del usuario")
    processed_query = serializers.CharField(help_text="Query después de preprocesamiento")
    strategy_used = serializers.CharField(help_text="Estrategia utilizada para ranking")
    total_results = serializers.IntegerField(help_text="Cantidad de resultados encontrados")
    
    recommendations = WorkerRecommendationSerializer(many=True, help_text="Lista de trabajadores recomendados")
    
    performance_ms = serializers.FloatField(help_text="Tiempo de respuesta en milisegundos")
    cache_hit = serializers.BooleanField(help_text="Si el resultado vino de cache")
    
    # Metadata
    log_id = serializers.UUIDField(help_text="ID del log de esta recomendación", required=False)


class RecommendationAnalyticsSerializer(serializers.Serializer):
    """
    Serializer para métricas y analytics del sistema de recomendación.
    """
    
    # Estadísticas generales
    total_queries = serializers.IntegerField(help_text="Total de queries procesadas")
    unique_users = serializers.IntegerField(help_text="Usuarios únicos que han buscado")
    
    # Performance
    avg_response_time_ms = serializers.FloatField(help_text="Tiempo promedio de respuesta")
    cache_hit_rate = serializers.FloatField(help_text="Tasa de hits en cache (0-1)")
    avg_results_per_query = serializers.FloatField(help_text="Promedio de resultados por query")
    
    # Engagement
    avg_ctr = serializers.FloatField(help_text="Click-Through Rate promedio")
    avg_conversion_rate = serializers.FloatField(help_text="Tasa de conversión promedio")
    avg_mrr = serializers.FloatField(help_text="Mean Reciprocal Rank promedio")
    
    # Top queries
    top_query_terms = serializers.ListField(
        child=serializers.DictField(),
        help_text="Términos más buscados con conteo"
    )
    
    # A/B Testing results
    ab_test_results = serializers.DictField(
        help_text="Comparación de estrategias (tfidf vs fallback vs hybrid)"
    )
    
    # Corpus health
    corpus_health = serializers.DictField(
        help_text="Estado de salud del corpus de trabajadores"
    )
    
    # Rango de fechas
    date_range = serializers.DictField(help_text="Rango de fechas del análisis")


class RecommendationHealthSerializer(serializers.Serializer):
    """
    Serializer para health check del sistema de recomendación.
    """
    
    status = serializers.ChoiceField(
        choices=['healthy', 'degraded', 'unhealthy'],
        help_text="Estado general del sistema"
    )
    
    # Estado del modelo
    model_trained = serializers.BooleanField(help_text="Si el modelo TF-IDF está entrenado")
    model_last_trained = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Última vez que se entrenó el modelo"
    )
    corpus_size = serializers.IntegerField(help_text="Cantidad de trabajadores en el corpus")
    vocabulary_size = serializers.IntegerField(
        required=False,
        help_text="Tamaño del vocabulario TF-IDF"
    )
    
    # Estado de cache
    cache_status = serializers.ChoiceField(
        choices=['connected', 'disconnected', 'error'],
        help_text="Estado de la conexión a Redis"
    )
    cache_keys_count = serializers.IntegerField(
        required=False,
        help_text="Cantidad de keys en cache relacionadas con ML"
    )
    
    # Performance reciente
    avg_response_time_ms = serializers.FloatField(
        required=False,
        help_text="Tiempo promedio de respuesta (últimas 100 queries)"
    )
    
    # Errores recientes
    recent_errors_count = serializers.IntegerField(
        default=0,
        help_text="Cantidad de errores en las últimas 24h"
    )
    
    # Recomendaciones
    recommendations = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Recomendaciones para mejorar el sistema"
    )
    
    # Timestamp
    checked_at = serializers.DateTimeField(help_text="Timestamp del health check")
