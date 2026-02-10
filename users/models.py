from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .managers import CustomUserManager
from django.contrib.gis.db import models as geomodels
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import uuid

class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", _("Administrator")
        CLIENT = "CLIENT", _("Client")
        WORKER = "WORKER", _("Worker")
        COMPANY = "COMPANY", _("Company")

    email = models.EmailField(unique=True)
    first_name = models.CharField(_("First Name"), max_length=150, blank=True)
    last_name = models.CharField(_("Last Name"), max_length=150, blank=True)
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.CLIENT)
    
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"

class WorkerProfile(models.Model):
    class ProfessionChoices(models.TextChoices):
        PLUMBER = 'PLUMBER', _('Plumber')
        ELECTRICIAN = 'ELECTRICIAN', _('Electrician')
        MASON = 'MASON', _('Mason')
        PAINTER = 'PAINTER', _('Painter')
        CARPENTER = 'CARPENTER', _('Carpenter')
        OTHER = 'OTHER', _('Other')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='worker_profile')
    profession = models.CharField(
        _("Profession"),
        max_length=50,
        choices=ProfessionChoices.choices,
        default=ProfessionChoices.OTHER
    )
    bio = models.TextField(_("Biography"), blank=True)
    years_experience = models.PositiveIntegerField(_("Years of Experience"), default=0)
    hourly_rate = models.DecimalField(_("Hourly Rate"), max_digits=10, decimal_places=2, null=True, blank=True)
    location = geomodels.PointField(_("Location"), null=True, blank=True, srid=4326) 
    is_verified = models.BooleanField(_("Verified"), default=False)
    average_rating = models.DecimalField(_("Average Rating"), max_digits=3, decimal_places=2, default=0.0)

    def __str__(self):
        return f"Perfil de {self.user.email}"


class RecommendationLog(models.Model):
    """
    Modelo para tracking de queries del sistema de recomendación.
    
    Permite análisis de:
        - Queries más comunes
        - Performance del sistema (tiempo de respuesta)
        - A/B Testing (comparación de estrategias)
        - Feedback Loop (CTR, clicks, conversiones)
        - Métricas MRR (Mean Reciprocal Rank)
    """
    
    class StrategyChoices(models.TextChoices):
        TFIDF = 'tfidf', _('TF-IDF Puro')
        FALLBACK = 'fallback', _('Geo + Rating')
        HYBRID = 'hybrid', _('Híbrido (TF-IDF + Rating + Geo)')
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Query info
    query = models.TextField(_("Query Original"))
    processed_query = models.TextField(_("Query Procesada"))
    strategy_used = models.CharField(
        _("Estrategia Usada"),
        max_length=20,
        choices=StrategyChoices.choices
    )
    
    # Usuario que realizó la búsqueda (opcional, puede ser anónimo)
    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recommendation_queries'
    )
    
    # Filtros aplicados
    filters_applied = models.JSONField(
        _("Filtros Aplicados"),
        default=dict,
        blank=True
    )
    
    # Resultados
    results_count = models.PositiveIntegerField(_("Cantidad de Resultados"), default=0)
    top_worker_ids = models.JSONField(
        _("IDs de Top Trabajadores"),
        default=list,
        help_text="Lista de IDs de trabajadores recomendados en orden"
    )
    
    # Performance
    response_time_ms = models.FloatField(_("Tiempo de Respuesta (ms)"), default=0.0)
    cache_hit = models.BooleanField(_("Hit en Cache"), default=False)
    
    # Feedback Loop (tracking de interacción)
    worker_clicked = models.ForeignKey(
        'WorkerProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clicked_from_recommendations',
        help_text="Trabajador que el usuario clickeó (si alguno)"
    )
    
    click_position = models.PositiveIntegerField(
        _("Posición del Click"),
        null=True,
        blank=True,
        help_text="Posición (0-indexed) del trabajador clickeado en los resultados"
    )
    
    worker_hired = models.ForeignKey(
        'WorkerProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hired_from_recommendations',
        help_text="Trabajador que fue contratado (conversión)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(_("Fecha de Creación"), auto_now_add=True)
    
    # Geo info del usuario (para análisis)
    user_latitude = models.FloatField(_("Latitud del Usuario"), null=True, blank=True)
    user_longitude = models.FloatField(_("Longitud del Usuario"), null=True, blank=True)
    
    class Meta:
        verbose_name = _("Log de Recomendación")
        verbose_name_plural = _("Logs de Recomendaciones")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['strategy_used', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"Query: '{self.query[:50]}' - {self.strategy_used} ({self.created_at})"
    
    @property
    def ctr(self) -> float:
        """
        Click-Through Rate: ¿El usuario clickeó en algún resultado?
        
        Returns:
            1.0 si hubo click, 0.0 si no
        """
        return 1.0 if self.worker_clicked else 0.0
    
    @property
    def conversion_rate(self) -> float:
        """
        Conversion Rate: ¿El usuario contrató a alguien?
        
        Returns:
            1.0 si hubo contratación, 0.0 si no
        """
        return 1.0 if self.worker_hired else 0.0
    
    @property
    def reciprocal_rank(self) -> float:
        """
        Reciprocal Rank: Métrica de calidad del ranking.
        
        Si el usuario clickeó en la posición 0 (primera) -> RR = 1.0
        Si clickeó en posición 1 (segunda) -> RR = 0.5
        Si clickeó en posición 2 (tercera) -> RR = 0.33
        Si no clickeó en nada -> RR = 0.0
        
        Returns:
            Reciprocal rank value
        """
        if self.click_position is not None:
            return 1.0 / (self.click_position + 1)
        return 0.0


# ============================================================================
# MÓDULO DE PORTFOLIO (HU4)
# ============================================================================

from .validators import portfolio_image_validators
from .constants import (
    MAX_IMAGE_WIDTH,
    IMAGE_QUALITY_JPEG,
    IMAGE_QUALITY_PNG_OPTIMIZE,
    IMAGE_QUALITY_WEBP,
    DEFAULT_IMAGE_FORMAT,
    DEFAULT_IMAGE_EXTENSION,
)
from io import BytesIO
from PIL import Image as PILImage
from django.core.files.base import ContentFile


def portfolio_image_upload_to(instance, filename):
    """
    Genera la ruta de subida para imágenes de portfolio.
    
    Organiza imágenes por ID de trabajador para mantener estructura limpia en S3.
    Patrón: portfolio/worker_{id}/{filename}
    """
    return f"portfolio/worker_{instance.worker.id}/{filename}"


def compress_image(image, format_hint=None):
    """
    Comprime y redimensiona imagen usando Pillow.
    
    Aplica compresión inteligente:
    - Redimensiona si width > MAX_IMAGE_WIDTH (mantiene aspect ratio)
    - Optimiza calidad según formato
    - Convierte a formatos web-friendly
    
    Raises:
        ValidationError: Si el archivo no puede ser procesado por Pillow
    """
    try:
        img = PILImage.open(image)
        img_format = format_hint or img.format or DEFAULT_IMAGE_FORMAT
    except (IOError, OSError) as e:
        raise ValidationError(
            _("El archivo no es una imagen válida o está corrupto.")
        )
    
    # Convert RGBA to RGB for JPEG compatibility
    if img.mode in ("RGBA", "LA", "P") and img_format.upper() in ["JPEG", "JPG"]:
        background = PILImage.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = background
    
    # Resize if needed (maintains aspect ratio)
    if img.width > MAX_IMAGE_WIDTH:
        ratio = MAX_IMAGE_WIDTH / float(img.width)
        new_height = int(float(img.height) * ratio)
        img = img.resize((MAX_IMAGE_WIDTH, new_height), PILImage.LANCZOS)
    
    buffer = BytesIO()
    if img_format.upper() in ["JPEG", "JPG"]:
        img.save(buffer, format="JPEG", optimize=True, quality=IMAGE_QUALITY_JPEG)
        ext = "jpg"
    elif img_format.upper() == "PNG":
        img.save(buffer, format="PNG", optimize=IMAGE_QUALITY_PNG_OPTIMIZE)
        ext = "png"
    elif img_format.upper() == "WEBP":
        img.save(buffer, format="WEBP", quality=IMAGE_QUALITY_WEBP)
        ext = "webp"
    else:
        img.save(buffer, format="JPEG", optimize=True, quality=IMAGE_QUALITY_JPEG)
        ext = DEFAULT_IMAGE_EXTENSION
    
    buffer.seek(0)
    return ContentFile(buffer.read()), ext


class PortfolioItem(models.Model):
    """
    Item de portfolio para perfiles de trabajadores.
    
    Permite a los trabajadores mostrar su trabajo con fotos antes/después,
    descripciones de proyectos y evidencia visual de su experiencia.
    
    Reglas de negocio:
    - Solo rol WORKER puede crear items de portfolio
    - Las imágenes se comprimen automáticamente al subir
    - Máximo 2MB por imagen (validado antes de comprimir)
    - Lectura pública, escritura solo para dueño
    
    Relacionado con HU4: Portafolio Visual de Evidencias
    """
    
    worker = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="portfolio_items",
        verbose_name=_("Trabajador"),
        help_text=_("Trabajador dueño de este item de portfolio")
    )
    title = models.CharField(
        _("Título"),
        max_length=255,
        help_text=_("Título breve describiendo el trabajo (ej: 'Remodelación de Cocina')")
    )
    description = models.TextField(
        _("Descripción"),
        blank=True,
        help_text=_("Descripción detallada del proyecto y técnicas utilizadas")
    )
    image = models.ImageField(
        _("Imagen"),
        upload_to=portfolio_image_upload_to,
        validators=portfolio_image_validators,
        help_text=_("Foto antes/después o muestra del proyecto (máx 2MB)")
    )
    created_at = models.DateTimeField(
        _("Fecha de Creación"),
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = _("Item de Portfolio")
        verbose_name_plural = _("Items de Portfolio")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["worker", "-created_at"], name="portfolio_worker_created_idx"),
        ]
    
    def save(self, *args, **kwargs):
        """
        Comprime la imagen antes de guardar.
        
        Aplica compresión solo si la imagen es nueva o cambió,
        reduciendo costos de almacenamiento y mejorando tiempos de carga.
        """
        if self.image and hasattr(self.image, "file"):
            try:
                compressed_file, ext = compress_image(self.image)
                
                original_name = self.image.name.rsplit(".", 1)[0] if "." in self.image.name else self.image.name
                file_name = f"{original_name}.{ext}"
                
                self.image = compressed_file
                self.image.name = file_name
            except ValidationError:
                # Re-propagar ValidationError (ej: imagen corrupta)
                raise
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Fallo compresión de imagen para PortfolioItem: {e}")
                # Propagar como ValidationError para consistencia
                raise ValidationError(
                    _("Error al procesar la imagen. Verifica que sea un archivo válido.")
                )
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.worker.user.email} - {self.title}"

