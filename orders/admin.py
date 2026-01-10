from django.contrib import admin
from .models import ServiceOrder, WorkHoursLog

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