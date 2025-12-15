from django.contrib import admin
from .models import ServiceOrder

@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'worker', 'status', 'agreed_price', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['client__email', 'worker__user__email', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Parties', {
            'fields': ('client', 'worker')
        }),
        ('Order Details', {
            'fields': ('description', 'status', 'agreed_price')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
