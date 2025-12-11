from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .managers import CustomUserManager
from django.contrib.gis.db import models as geomodels
from django.utils.translation import gettext_lazy as _

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
