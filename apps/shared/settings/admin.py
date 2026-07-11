# apps/shared/settings/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import CompanySetting


@admin.register(CompanySetting)
class CompanySettingAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'company_name', 'has_logo', 'primary_color', 'created_at']
    list_filter = ['tenant']
    search_fields = ['company_name', 'tenant__company_name']
    readonly_fields = ['logo_preview', 'favicon_preview']
    
    fieldsets = (
        ('Company Details', {
            'fields': ('tenant', 'company_name', 'company_address', 'company_phone', 
                      'company_email', 'company_website', 'company_tax_pin')
        }),
        ('Branding', {
            'fields': ('logo', 'logo_preview', 'favicon', 'favicon_preview', 
                      'primary_color', 'secondary_color', 'accent_color')
        }),
        ('Display Settings', {
            'fields': ('show_logo_on_receipts', 'show_logo_on_invoices', 
                      'show_logo_on_reports', 'show_logo_on_dashboard')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(boolean=True, description='Has Logo')
    def has_logo(self, obj):
        return obj.has_valid_logo()
    
    @admin.display(description='Logo Preview')
    def logo_preview(self, obj):
        if obj.has_valid_logo():
            return format_html('<img src="{}" style="max-height: 100px; max-width: 200px;" />', obj.logo.url)
        return "No logo uploaded"
    
    @admin.display(description='Favicon Preview')
    def favicon_preview(self, obj):
        if obj.favicon:
            return format_html('<img src="{}" style="max-height: 32px; max-width: 32px;" />', obj.favicon.url)
        return "No favicon uploaded"