from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import WorkerProfile
from django.core.cache import cache
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


@receiver(post_save, sender=WorkerProfile)
def invalidate_recommendation_cache(sender, instance, **kwargs):
    """
    Invalida el cache del modelo de recomendación cuando se actualiza un WorkerProfile.
    
    Esto fuerza el reentrenamiento del modelo TF-IDF en la próxima query,
    asegurando que los cambios en biografías y skills se reflejen en las recomendaciones.
    
    El cache se invalida siempre que se actualiza un perfil de trabajador
    (enfoque conservador para garantizar datos frescos).
    """
    # Solo invalidar en updates, no en creación
    if not kwargs.get('created', False):
        cache.delete('recommendation_model_data')
        cache.delete('recommendation_model_metadata')
        logger.info(
            f"Cache de recomendación invalidado por actualización de {instance.user.email}"
        )
        
        # Nota: El modelo se reentrenará automáticamente en la próxima query
        # o puede reentrenarse manualmente con: python manage.py train_recommendation_model
