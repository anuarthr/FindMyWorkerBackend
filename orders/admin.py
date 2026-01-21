from django.contrib import admin
from .models import ServiceOrder, WorkHoursLog, Review

class WorkHoursLogInline(admin.TabularInline):
    model = WorkHoursLog
    extra = 0
    readonly_fields = ['calculated_payment', 'created_at', 'updated_at']
    fields = ['date', 'hours', 'description', 'approved_by_client', 'calculated_payment', 'created_at']
    ordering = ['-date']
    
    def has_add_permission(self, request, obj=None):
        return True
    
    def has_delete_permission(self, request, obj=None):
        return True

@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'client', 
        'worker', 
        'status', 
        'agreed_price_display',
        'total_hours_logged',
        'total_hours_approved',
        'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['client__email', 'worker__user__email', 'description']
    readonly_fields = [
        'created_at',
        'updated_at',
        'calculate_total_price_display',
        'total_hours_summary'
    ]
    
    inlines = [WorkHoursLogInline]
    
    fieldsets = (
        ('Parties', {
            'fields': ('client', 'worker')
        }),
        ('Order Details', {
            'fields': ('description', 'status', 'agreed_price')
        }),
        ('Hours Summary', {
            'fields': ('calculate_total_price_display', 'total_hours_summary'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def agreed_price_display(self, obj):
        """Muestra el precio acordado formateado"""
        if obj.agreed_price:
            return f"${obj.agreed_price:,.2f}"
        return "Sin precio"
    agreed_price_display.short_description = 'Precio Acordado'
    
    def total_hours_logged(self, obj):
        """Total de horas registradas (aprobadas + pendientes)"""
        total = sum(log.hours for log in obj.work_hours.all())
        return f"{total:.2f}h"
    total_hours_logged.short_description = 'Horas Totales'
    
    def total_hours_approved(self, obj):
        """Total de horas aprobadas"""
        total = sum(log.hours for log in obj.work_hours.filter(approved_by_client=True))
        return f"{total:.2f}h"
    total_hours_approved.short_description = 'Horas Aprobadas'
    
    def calculate_total_price_display(self, obj):
        """Calcula el precio total basado en horas aprobadas"""
        total = obj.calculate_total_price()
        return f"${total:,.2f}"
    calculate_total_price_display.short_description = 'Total Calculado (Horas Aprobadas)'
    
    def total_hours_summary(self, obj):
        approved = sum(log.hours for log in obj.work_hours.filter(approved_by_client=True))
        pending = sum(log.hours for log in obj.work_hours.filter(approved_by_client=False))
        
        return f"✅ {approved:.2f}h aprobadas | ⏳ {pending:.2f}h pendientes"
    total_hours_summary.short_description = 'Resumen de Horas'
    
    actions = ['recalculate_prices']
    
    def recalculate_prices(self, request, queryset):
        count = 0
        for order in queryset:
            order.update_agreed_price()
            count += 1
        
        self.message_user(
            request, 
            f"Se recalcularon los precios de {count} órdenes."
        )
    recalculate_prices.short_description = "♻️ Recalcular precios (basado en horas aprobadas)"

@admin.register(WorkHoursLog)
class WorkHoursLogAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'service_order',
        'date',
        'hours',
        'approved_status',
        'calculated_payment_display',
        'created_at'
    ]
    list_filter = ['approved_by_client', 'date', 'created_at']
    search_fields = ['service_order__id', 'description', 'service_order__client__email']
    readonly_fields = ['calculated_payment_display', 'worker_info', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Order Info', {
            'fields': ('service_order', 'worker_info')
        }),
        ('Work Details', {
            'fields': ('date', 'hours', 'description')
        }),
        ('Approval', {
            'fields': ('approved_by_client', 'calculated_payment_display')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def approved_status(self, obj):
        if obj.approved_by_client:
            return "✅ Aprobado"
        return "⏳ Pendiente"
    approved_status.short_description = 'Estado'
    
    def calculated_payment_display(self, obj):
        return f"${obj.calculated_payment:,.2f}"
    calculated_payment_display.short_description = 'Pago Calculado'
    
    def worker_info(self, obj):
        worker = obj.service_order.worker
        return f"{worker.user.email} (${worker.hourly_rate}/hora)"
    worker_info.short_description = 'Trabajador'
    
    actions = ['approve_hours', 'revoke_approval']
    
    def approve_hours(self, request, queryset):
        count = 0
        orders_to_update = set()
        
        for log in queryset:
            if not log.approved_by_client:
                log.approved_by_client = True
                log.save()
                orders_to_update.add(log.service_order)
                count += 1
        
        for order in orders_to_update:
            order.update_agreed_price()
        
        self.message_user(
            request, 
            f"Se aprobaron {count} registros de horas. Se actualizaron {len(orders_to_update)} órdenes."
        )
    approve_hours.short_description = "✅ Aprobar horas seleccionadas"
    
    def revoke_approval(self, request, queryset):
        count = 0
        orders_to_update = set()
        
        for log in queryset:
            if log.approved_by_client:
                log.approved_by_client = False
                log.save()
                orders_to_update.add(log.service_order)
                count += 1
        
        for order in orders_to_update:
            order.update_agreed_price()
        
        self.message_user(
            request, 
            f"Se revocó la aprobación de {count} registros. Se actualizaron {len(orders_to_update)} órdenes."
        )
    revoke_approval.short_description = "❌ Revocar aprobación"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """
    Administrador para Reviews.
    """
    list_display = [
        'id',
        'service_order',
        'reviewer_display',
        'worker_display',
        'rating_display',
        'comment_preview',
        'created_at',
        'can_edit'
    ]
    list_filter = ['rating', 'created_at']
    search_fields = [
        'service_order__id',
        'service_order__client__email',
        'service_order__worker__user__email',
        'comment'
    ]
    readonly_fields = [
        'service_order',
        'reviewer_display',
        'worker_display',
        'created_at',
        'can_edit'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Orden', {
            'fields': ('service_order', 'reviewer_display', 'worker_display')
        }),
        ('Evaluación', {
            'fields': ('rating', 'comment')
        }),
        ('Metadata', {
            'fields': ('created_at', 'can_edit'),
            'classes': ('collapse',)
        }),
    )
    
    def reviewer_display(self, obj):
        """Muestra el reviewer (cliente)"""
        return obj.reviewer.email if obj.reviewer else 'N/A'
    reviewer_display.short_description = 'Cliente (Reviewer)'
    
    def worker_display(self, obj):
        """Muestra el trabajador evaluado"""
        return obj.worker.user.email if obj.worker else 'N/A'
    worker_display.short_description = 'Trabajador'
    
    def rating_display(self, obj):
        """Muestra el rating con estrellas"""
        return f"{obj.rating}⭐" if obj.rating else 'N/A'
    rating_display.short_description = 'Rating'
    
    def comment_preview(self, obj):
        """Muestra preview del comentario"""
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = 'Comentario'
    
    def has_delete_permission(self, request, obj=None):
        """
        Permite eliminar reviews solo si tienen menos de 7 días.
        """
        if obj and not obj.can_edit:
            return False
        return super().has_delete_permission(request, obj)
    
    def has_change_permission(self, request, obj=None):
        """
        Permite editar reviews solo si tienen menos de 7 días.
        """
        if obj and not obj.can_edit:
            return False
        return super().has_change_permission(request, obj)