from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import WorkerProfile
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_worker_profile(sender, instance, created, **kwargs):
    """
    Crea automáticamente un WorkerProfile cuando se registra un usuario con rol WORKER.
    """
    if created and instance.role == 'WORKER':
        WorkerProfile.objects.create(user=instance)
        logger.info(f"WorkerProfile creado automáticamente para usuario {instance.email}")
