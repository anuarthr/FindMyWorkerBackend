from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta


class ServiceOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        ACCEPTED = 'ACCEPTED', _('Accepted')
        IN_ESCROW = 'IN_ESCROW', _('In Escrow')
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled')

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_orders',
        verbose_name=_('Client')
    )
    worker = models.ForeignKey(
        'users.WorkerProfile',
        on_delete=models.CASCADE,
        related_name='worker_orders',
        verbose_name=_('Worker')
    )
    description = models.TextField(
        verbose_name=_('Job Description')
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('Status')
    )
    agreed_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Agreed Price')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )

    class Meta:
        verbose_name = _('Service Order')
        verbose_name_plural = _('Service Orders')
        ordering = ['-created_at']
        # Índices para optimizar queries frecuentes
        indexes = [
            models.Index(fields=['client', 'status'], name='order_client_status_idx'),
            models.Index(fields=['worker', 'status'], name='order_worker_status_idx'),
            models.Index(fields=['status', 'created_at'], name='order_status_created_idx'),
        ]

    def calculate_total_price(self):
        """
        Calcula el precio total de la orden basado en horas aprobadas.
        
        Returns:
            Decimal: Total a pagar calculado (horas * tarifa horaria)
        """
        from django.db.models import Sum, F
        
        # Validar que el worker tenga tarifa horaria configurada
        if not self.worker.hourly_rate or self.worker.hourly_rate <= 0:
            return Decimal('0.00')
        
        total = self.work_hours.filter(
            approved_by_client=True
        ).aggregate(
            total_payment=Sum(F('hours') * self.worker.hourly_rate)
        )['total_payment']
        
        return Decimal(str(total)) if total else Decimal('0.00')

    def update_agreed_price(self):
        """
        Actualiza el precio acordado basándose en las horas aprobadas.
        Solo actualiza los campos necesarios para evitar triggers innecesarios.
        """
        self.agreed_price = self.calculate_total_price()
        self.save(update_fields=['agreed_price', 'updated_at'])

    def can_transition_to_completed(self):
        """
        Verifica si la orden puede transicionar a estado COMPLETED.
        Requiere que haya un precio acordado mayor a cero.
        
        Returns:
            bool: True si puede completarse, False en caso contrario
        """
        return self.agreed_price and self.agreed_price > 0
    
    def get_total_hours(self):
        """
        Obtiene el total de horas registradas (aprobadas y pendientes).
        
        Returns:
            dict: Diccionario con 'approved' y 'pending' horas
        """
        from django.db.models import Sum
        approved = self.work_hours.filter(approved_by_client=True).aggregate(
            total=Sum('hours'))['total'] or Decimal('0.00')
        pending = self.work_hours.filter(approved_by_client=False).aggregate(
            total=Sum('hours'))['total'] or Decimal('0.00')
        
        return {
            'approved': approved,
            'pending': pending,
            'total': approved + pending
        }
    
    def clean(self):
        """
        Validaciones a nivel de modelo.
        """
        super().clean()
        
        # Validar que el cliente no sea el mismo que el trabajador
        if self.worker and self.client == self.worker.user:
            raise ValidationError(_("El cliente no puede crear una orden consigo mismo."))
        
        # Validar transiciones de estado
        if self.pk:  # Solo para instancias existentes
            old_instance = ServiceOrder.objects.filter(pk=self.pk).first()
            if old_instance and old_instance.status == 'COMPLETED' and self.status != 'COMPLETED':
                raise ValidationError(_("No se puede cambiar el estado de una orden completada."))

    def __str__(self):
        return f"Order #{self.pk} - {self.client.email} → {self.worker.user.email} ({self.status})"
    
class WorkHoursLog(models.Model):
    service_order = models.ForeignKey(
        ServiceOrder,
        on_delete=models.CASCADE,
        related_name='work_hours',
        verbose_name=_('Service Order')
    )
    date = models.DateField(
        verbose_name=_('Work Date')
    )
    hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_('Hours Worked'),
        help_text=_('Ejemplo: 5.5 para 5 horas y 30 minutos')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Work Description'),
        help_text=_('Descripción de las tareas realizadas')
    )
    approved_by_client = models.BooleanField(
        default=False,
        verbose_name=_('Approved by Client')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )

    class Meta:
        verbose_name = _('Work Hours Log')
        verbose_name_plural = _('Work Hours Logs')
        ordering = ['-date', '-created_at']
        unique_together = [['service_order', 'date']]
        # Índice para optimizar consultas de aprobación
        indexes = [
            models.Index(fields=['service_order', 'approved_by_client'], name='workhours_order_approved_idx'),
            models.Index(fields=['date'], name='workhours_date_idx'),
        ]

    def __str__(self):
        return f"{self.service_order.id} - {self.date} - {self.hours}h"
    
    def save(self, *args, **kwargs):
        """
        Override del método save para ejecutar validaciones.
        """
        self.full_clean()  # Ejecuta las validaciones del método clean()
        super().save(*args, **kwargs)

    @property
    def calculated_payment(self):
        """
        Calcula el pago basado en hourly_rate del trabajador.
        
        Returns:
            Decimal: Monto calculado (horas * tarifa horaria)
        """
        if self.service_order.worker.hourly_rate and self.service_order.worker.hourly_rate > 0:
            return Decimal(str(self.hours)) * Decimal(str(self.service_order.worker.hourly_rate))
        return Decimal('0.00')

    @property
    def status_display(self):
        """Estado visual del registro"""
        return _('Approved') if self.approved_by_client else _('Pending Approval')
    
    def clean(self):
        """
        Validaciones a nivel de modelo para WorkHoursLog.
        """
        super().clean()
        
        # Validar que las horas sean positivas
        if self.hours and self.hours <= 0:
            raise ValidationError({'hours': _("Las horas deben ser mayores a 0.")})
        
        # Validar que no se registren horas futuras
        from datetime import date
        if self.date and self.date > date.today():
            raise ValidationError({'date': _("No se pueden registrar horas futuras.")})        
        
        # Validar que la orden esté en estado correcto
        if self.service_order and self.service_order.status not in ['ACCEPTED', 'IN_ESCROW']:
            raise ValidationError(_("Solo se pueden registrar horas en órdenes aceptadas o en garantía."))
    
class Message(models.Model):
    service_order = models.ForeignKey(
        ServiceOrder,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('Service Order')
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name=_('Sender')
    )
    content = models.TextField(
        verbose_name=_('Message Content'),
        help_text=_('Contenido del mensaje de texto')
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name=_('Read')
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Timestamp')
    )

    class Meta:
        verbose_name = _('Message')
        verbose_name_plural = _('Messages')
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['service_order', 'timestamp']),
            models.Index(fields=['sender', 'timestamp']),
        ]

    def __str__(self):
        return f"Message #{self.pk} - Order #{self.service_order.id} - {self.sender.email}"
    
    def mark_as_read(self):
        """
        Marca el mensaje como leído.
        """
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
    
    def clean(self):
        """
        Validaciones a nivel de modelo para Message.
        """
        super().clean()
        
        # Validar que el contenido no esté vacío
        if not self.content or not self.content.strip():
            raise ValidationError({'content': _("El mensaje no puede estar vacío.")})
        
        # Validar longitud máxima del mensaje
        if len(self.content) > 5000:
            raise ValidationError({'content': _("El mensaje no puede exceder 5000 caracteres.")})
        
        # Validar que el remitente sea parte de la orden
        if self.service_order and self.sender:
            is_participant = (
                self.sender == self.service_order.client or 
                self.sender == self.service_order.worker.user
            )
            if not is_participant:
                raise ValidationError(_("Solo los participantes de la orden pueden enviar mensajes."))


class Review(models.Model):
    """
    Review de un cliente sobre un trabajador después de completar una orden.
    Relación 1:1 con ServiceOrder (una orden = una review máximo).
    """
    service_order = models.OneToOneField(
        ServiceOrder,
        on_delete=models.CASCADE,
        related_name='review',
        verbose_name=_('Service Order')
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_("Calificación de 1 a 5 estrellas"),
        verbose_name=_('Rating')
    )
    comment = models.TextField(
        validators=[MinLengthValidator(10)],
        help_text=_("Mínimo 10 caracteres"),
        verbose_name=_('Comment')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    
    class Meta:
        db_table = 'reviews'
        verbose_name = _('Review')
        verbose_name_plural = _('Reviews')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service_order'], name='review_order_idx'),
            models.Index(fields=['-created_at'], name='review_created_idx'),
        ]
    
    def __str__(self):
        return f"Review {self.rating}⭐ - Orden #{self.service_order.id}"
    
    @property
    def reviewer(self):
        """El reviewer es siempre el cliente de la orden"""
        return self.service_order.client
    
    @property
    def worker(self):
        """El trabajador evaluado"""
        return self.service_order.worker
    
    @property
    def can_edit(self):
        """
        Verifica si la review puede ser editada.
        Las reviews son inmutables después de 7 días.
        """
        time_since_creation = timezone.now() - self.created_at
        return time_since_creation < timedelta(days=7)
    
    def clean(self):
        """
        Validaciones a nivel de modelo para Review.
        """
        super().clean()
        
        # Validar que la orden esté completada
        if self.service_order and self.service_order.status != 'COMPLETED':
            raise ValidationError(_("Solo se pueden crear reviews para órdenes completadas."))
        
        # Validar que el rating esté en el rango correcto
        if self.rating and (self.rating < 1 or self.rating > 5):
            raise ValidationError({'rating': _("El rating debe estar entre 1 y 5.")})
        
        # Validar longitud del comentario
        if self.comment and len(self.comment.strip()) < 10:
            raise ValidationError({'comment': _("El comentario debe tener al menos 10 caracteres.")})
    
    def save(self, *args, **kwargs):
        """
        Override del método save para ejecutar validaciones.
        """
        self.full_clean()
        super().save(*args, **kwargs)