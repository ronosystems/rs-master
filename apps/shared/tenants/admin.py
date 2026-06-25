# apps/shared/tenants/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from .models import ProjectType, Tenant


@admin.register(ProjectType)
class ProjectTypeAdmin(admin.ModelAdmin):
    """Admin configuration for Project Types"""
    
    list_display = ['name', 'code', 'icon', 'color_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'color']
    search_fields = ['name', 'code', 'description']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description')
        }),
        ('Display Settings', {
            'fields': ('icon', 'color')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    actions = ['sync_from_settings']
    
    def color_display(self, obj):
        """Display color as a colored box"""
        return format_html(
            '<span style="background-color: {}; padding: 4px 12px; border-radius: 4px; color: white; font-size: 12px;">{}</span>',
            obj.color,
            obj.color
        )
    color_display.short_description = 'Color'
    
    def sync_from_settings(self, request, queryset):
        """Admin action to sync project types from settings"""
        from .models import ProjectType
        result = ProjectType.sync_from_settings()
        self.message_user(
            request, 
            f'✅ Synced project types: {result["created"]} created, {result["updated"]} updated',
            messages.SUCCESS
        )
    sync_from_settings.short_description = "Sync project types from settings.py"


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """Admin configuration for Tenants"""
    
    list_display = ['display_logo', 'company_name', 'project_type', 'status', 'created_at']
    list_filter = ['project_type', 'status']
    search_fields = ['company_name', 'code', 'company_email', 'company_phone']
    
    fieldsets = (
        ('Company Information', {
            'fields': ('company_name', 'logo', 'company_address', 'company_phone', 'company_email', 'company_pin')
        }),
        ('Project & Identification', {
            'fields': ('project_type', 'code')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def display_logo(self, obj):
        """Display logo thumbnail in admin"""
        if obj.logo:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 4px;" />',
                obj.logo.url
            )
        return '📷 No Logo'
    display_logo.short_description = 'Logo'