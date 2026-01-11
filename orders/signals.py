from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import WorkHoursLog

@receiver(post_save, sender=WorkHoursLog)
def auto_change_order_status(sender, instance, created, **kwargs):
    if created:
        order = instance.service_order
        
        if order.status == 'ACCEPTED':
            order.status = 'IN_ESCROW'
            order.save()
            print(f"✅ Orden #{order.id} cambiada automáticamente a IN_ESCROW")
