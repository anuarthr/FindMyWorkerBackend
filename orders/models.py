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

    def __str__(self):
        return f"Order #{self.pk} - {self.client.email} → {self.worker.user.email} ({self.status})"
