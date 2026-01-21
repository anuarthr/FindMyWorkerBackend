import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg
from .models import WorkHoursLog, Review

logger = logging.getLogger(__name__)

@receiver(post_save, sender=WorkHoursLog)
def auto_change_order_status(sender, instance, created, **kwargs):
    if created:
        order = instance.service_order
        
        if order.status == 'ACCEPTED':
            order.status = 'IN_ESCROW'
            order.save()
            logger.info(f"✅ Orden #{order.id} cambiada automáticamente a IN_ESCROW")


@receiver(post_save, sender=Review)
def update_worker_average_rating(sender, instance, created, **kwargs):
    """
    Cada vez que se crea una review, recalcula el promedio del trabajador.
    """
    if created:
        worker = instance.worker
        
        # Calcular nuevo promedio (solo reviews de este worker)
        avg_rating = Review.objects.filter(
            service_order__worker=worker
        ).aggregate(Avg('rating'))['rating__avg']
        
        if avg_rating:
            worker.average_rating = round(avg_rating, 2)
            worker.save(update_fields=['average_rating'])
            
            logger.info(f"Worker {worker.id} rating actualizado: {worker.average_rating}⭐")


@receiver(post_delete, sender=Review)
def recalculate_worker_rating_on_delete(sender, instance, **kwargs):
    """
    Cuando se elimina una review, recalcular el rating del trabajador.
    Caso de uso: Admin elimina orden con review, o cliente elimina review dentro de 7 días.
    """
    worker = instance.worker
    
    # Recalcular promedio (excluyendo la review eliminada)
    avg_rating = Review.objects.filter(
        service_order__worker=worker
    ).aggregate(Avg('rating'))['rating__avg']
    
    # Si no hay reviews, resetear a 0.00
    worker.average_rating = round(avg_rating, 2) if avg_rating else 0.00
    worker.save(update_fields=['average_rating'])
    
    logger.info(f"Worker {worker.id} rating recalculado tras eliminar review: {worker.average_rating}⭐")


