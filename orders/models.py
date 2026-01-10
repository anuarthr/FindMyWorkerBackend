from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


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

    def calculate_total_price(self):
        from django.db.models import Sum, F
        total = self.work_hours.filter(
            approved_by_client=True
        ).aggregate(
            total_payment=Sum(F('hours') * self.worker.hourly_rate)
        )['total_payment']
        
        return total or 0

    def update_agreed_price(self):
        self.agreed_price = self.calculate_total_price()
        self.save(update_fields=['agreed_price', 'updated_at'])

    def can_transition_to_completed(self):
        return self.agreed_price and self.agreed_price > 0

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
        # Evitar duplicados por fecha
        unique_together = [['service_order', 'date']]

    def __str__(self):
        return f"{self.service_order.id} - {self.date} - {self.hours}h"

    @property
    def calculated_payment(self):
        """Calcula el pago basado en hourly_rate del trabajador"""
        if self.service_order.worker.hourly_rate:
            return float(self.hours) * float(self.service_order.worker.hourly_rate)
        return 0

    @property
    def status_display(self):
        """Estado visual del registro"""
        return _('Approved') if self.approved_by_client else _('Pending Approval')
