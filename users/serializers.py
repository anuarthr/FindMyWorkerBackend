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
        - Idioma de búsqueda (es/en)
    """
    
    query = serializers.CharField(
        required=True,
        max_length=500,
        help_text="Texto de búsqueda en lenguaje natural. Ej: 'Plomero urgente para reparar fuga'"
    )
    
    language = serializers.ChoiceField(
        choices=['es', 'en'],
        default='es',
        help_text="Idioma de búsqueda: 'es' (español) o 'en' (inglés). Solo español soportado actualmente."
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
        
        # Validar idioma (solo español soportado por ahora)
        language = data.get('language', 'es')
        if language == 'en':
            raise serializers.ValidationError({
                'language': 'Inglés no soportado actualmente. Use "es" para español. Funcionalidad en desarrollo (HU3).'
            })
        
        return data


class WorkerRecommendationSerializer(serializers.ModelSerializer):
    """
    Serializer para trabajadores recomendados con información adicional de scoring.
    
    Incluye campos planos para compatibilidad con frontend y campos detallados
    para análisis avanzado.
    """
    
    user = UserSerializer(read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    # Campos planos para compatibilidad con frontend
    recommendation_score = serializers.FloatField(
        read_only=True, 
        help_text="Score normalizado de relevancia (0-1)"
    )
    matched_keywords = serializers.ListField(
        read_only=True, 
        help_text="Lista de palabras clave que coinciden con la búsqueda"
    )
    explanation = serializers.CharField(
        read_only=True, 
        help_text="Explicación en texto de por qué se recomendó este trabajador"
    )
    
    # Campos detallados (backward compatibility)
    recommendation_details = serializers.SerializerMethodField(
        help_text="Información detallada del scoring (para análisis avanzado)"
    )
    
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
            # Campos planos de recomendación
            'recommendation_score',
            'matched_keywords',
            'explanation',
            # Campos detallados
            'recommendation_details',
        ]
        read_only_fields = ['id', 'user', 'is_verified', 'average_rating']
    
    def get_latitude(self, obj):
        return obj.location.y if obj.location else None
    
    def get_longitude(self, obj):
        return obj.location.x if obj.location else None
    
    def get_recommendation_details(self, obj):
        """
        Retorna información detallada del scoring para análisis avanzado.
        """
        if not hasattr(obj, '_recommendation_data'):
            return None
        
        data = obj._recommendation_data
        return {
            'semantic_similarity': data.get('score', 0),
            'relevance_percentage': data.get('relevance_percentage', 0),
            'distance_km': data.get('distance_km'),
            'distance_factor': data.get('distance_factor'),
            'normalized_score': data.get('normalized_score'),
            'matched_terms_count': len(data.get('matched_keywords', [])),
        }


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
        choices=['ready', 'training', 'not_trained', 'degraded', 'unhealthy'],
        help_text="Estado general del sistema: ready (listo), training (entrenando), not_trained (sin entrenar), degraded (degradado), unhealthy (no saludable)"
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


# ============================================================================
# SERIALIZERS DE PORTFOLIO (HU4)
# ============================================================================

from .models import PortfolioItem


class PortfolioItemSerializer(serializers.ModelSerializer):
    """
    Serializador de lectura para items de portfolio.
    
    Incluye información completa del trabajador y URLs absolutas de imágenes.
    Usado para operaciones GET (list/retrieve).
    """
    
    worker_id = serializers.IntegerField(source="worker.id", read_only=True)
    worker_user_id = serializers.IntegerField(source="worker.user.id", read_only=True)
    worker_email = serializers.EmailField(source="worker.user.email", read_only=True)
    image_url = serializers.SerializerMethodField()
    order_info = serializers.SerializerMethodField()
    
    class Meta:
        model = PortfolioItem
        fields = [
            "id",
            "worker_id",
            "worker_user_id",
            "worker_email",
            "title",
            "description",
            "image",
            "image_url",
            "order",
            "is_external_work",
            "order_info",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "worker_id",
            "worker_user_id",
            "worker_email",
            "created_at",
            "image_url",
            "is_external_work",
            "order_info",
        ]
    
    def get_image_url(self, obj):
        """Retorna URL absoluta de la imagen (maneja S3 y storage local)."""
        if obj.image and hasattr(obj.image, "url"):
            url = obj.image.url
            request = self.context.get("request")
            
            if request is not None and not url.startswith("http"):
                return request.build_absolute_uri(url)
            
            return url
        return None
    
    def get_order_info(self, obj):
        """
        Retorna información básica de la orden si existe.
        
        Incluye datos del cliente y estado para contexto.
        """
        if obj.order:
            # Construir nombre del cliente
            client_name = f"{obj.order.client.first_name} {obj.order.client.last_name}".strip()
            if not client_name:
                client_name = obj.order.client.email
            
            return {
                "id": obj.order.id,
                "client_name": client_name,
                "description": obj.order.description,
                "status": obj.order.status,
                "updated_at": obj.order.updated_at
            }
        return None


class PortfolioItemCreateSerializer(serializers.ModelSerializer):
    """
    Serializador de escritura para items de portfolio.
    
    Maneja creación y actualizaciones con asignación automática de worker.
    Permite relacionar con órdenes completadas de la plataforma.
    Usado para operaciones POST/PATCH/PUT.
    """
    
    class Meta:
        model = PortfolioItem
        fields = ["id", "title", "description", "image", "order", "is_external_work"]
        read_only_fields = ["id", "is_external_work"]
    
    def validate_image(self, image):
        """Los validadores del modelo ya aplican."""
        return image
    
    def validate_title(self, title):
        """
        Valida que el título no esté vacío o solo sea espacios.
        
        Aplica strip() para normalizar el título y rechaza
        cadenas vacías o con solo espacios en blanco.
        """
        if not title or not title.strip():
            raise serializers.ValidationError(
                _("El título no puede estar vacío o contener solo espacios.")
            )
        return title.strip()
    
    def validate_order(self, order):
        """
        Valida que la orden pertenece al trabajador y esté completada.
        """
        if order:
            request = self.context.get("request")
            if not request or not request.user:
                raise serializers.ValidationError(
                    _("Usuario no autenticado.")
                )
            
            worker_profile = getattr(request.user, "worker_profile", None)
            if not worker_profile:
                raise serializers.ValidationError(
                    _("El usuario no tiene perfil de trabajador.")
                )
            
            # Validar que la orden pertenece al trabajador
            if order.worker != worker_profile:
                raise serializers.ValidationError(
                    _("No puedes asociar una orden que no te pertenece.")
                )
            
            # Validar que la orden esté completada
            if order.status != 'COMPLETED':
                raise serializers.ValidationError(
                    _("Solo puedes asociar órdenes completadas.")
                )
        
        return order
    
    def create(self, validated_data):
        """Crea item de portfolio para el trabajador autenticado."""
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError(
                {"detail": _("Usuario no autenticado.")}
            )
        
        user = request.user
        worker_profile = getattr(user, "worker_profile", None)
        
        if worker_profile is None:
            raise serializers.ValidationError(
                {"detail": _("El usuario no tiene perfil de trabajador.")}
            )
        
        # Si hay orden asociada, marcar como trabajo de la plataforma
        order = validated_data.get('order')
        if order:
            validated_data['is_external_work'] = False
        
        return PortfolioItem.objects.create(
            worker=worker_profile,
            **validated_data
        )


class WorkerProfileWithPortfolioSerializer(WorkerProfileSerializer):
    """
    Serializador extendido de perfil de trabajador incluyendo portfolio.
    
    Usado para vistas detalladas donde el portfolio debe mostrarse
    junto con la información básica del trabajador.
    """
    
    portfolio_items = PortfolioItemSerializer(many=True, read_only=True)
    portfolio_count = serializers.SerializerMethodField()
    
    class Meta(WorkerProfileSerializer.Meta):
        fields = WorkerProfileSerializer.Meta.fields + [
            "portfolio_items",
            "portfolio_count",
        ]
    
    def get_portfolio_count(self, obj):
        """Retorna cantidad total de items de portfolio."""
        return obj.portfolio_items.count()
