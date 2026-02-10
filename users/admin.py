from django.contrib import admin
from django.utils.html import format_html
from .models import User, WorkerProfile, RecommendationLog, PortfolioItem


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Admin interface for User model."""
    
    list_display = ['id', 'email', 'role', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name']
    readonly_fields = ['date_joined']
    ordering = ['-date_joined']
    
    fieldsets = (
        ('Account Info', {
            'fields': ('email', 'password', 'role')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'avatar')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser')
        }),
        ('Timestamps', {
            'fields': ('date_joined',)
        }),
    )


@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    """Admin interface for WorkerProfile model."""
    
    list_display = [
        'id', 'user', 'profession', 'years_experience',
        'hourly_rate', 'is_verified', 'average_rating'
    ]
    list_filter = ['profession', 'is_verified', 'years_experience']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'bio']
    readonly_fields = ['average_rating']
    
    fieldsets = (
        ('Worker Info', {
            'fields': ('user', 'profession', 'bio')
        }),
        ('Experience & Rates', {
            'fields': ('years_experience', 'hourly_rate')
        }),
        ('Location', {
            'fields': ('location',)
        }),
        ('Verification & Rating', {
            'fields': ('is_verified', 'average_rating')
        }),
    )


@admin.register(RecommendationLog)
class RecommendationLogAdmin(admin.ModelAdmin):
    """Admin interface for RecommendationLog model."""
    
    list_display = [
        'id', 'user', 'strategy_used', 'results_count',
        'response_time_ms', 'cache_hit', 'created_at'
    ]
    list_filter = ['strategy_used', 'cache_hit', 'created_at']
    search_fields = ['query', 'user__email']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    """Interfaz administrativa para PortfolioItem."""
    
    list_display = [
        'id', 'worker', 'title', 'image_thumbnail', 'created_at'
    ]
    list_filter = ['created_at', 'worker__profession']
    search_fields = [
        'title', 'description',
        'worker__user__email',
        'worker__user__first_name',
        'worker__user__last_name'
    ]
    readonly_fields = ['created_at', 'image_preview']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Item de Portfolio', {
            'fields': ('worker', 'title', 'description')
        }),
        ('Imagen', {
            'fields': ('image', 'image_preview')
        }),
        ('Metadatos', {
            'fields': ('created_at',)
        }),
    )
    
    def image_thumbnail(self, obj):
        """Muestra miniatura pequeña en vista de lista."""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px; border-radius: 4px;" />',
                obj.image.url
            )
        return '-'
    image_thumbnail.short_description = 'Imagen'
    
    def image_preview(self, obj):
        """Muestra preview más grande en vista de detalle."""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 400px; border-radius: 8px;" />',
                obj.image.url
            )
        return '-'
    image_preview.short_description = 'Vista Previa'
