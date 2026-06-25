# apps/shared/audit_log/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import AuditLog, AuditLogSettings


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action_badge', 'model_name', 'object_repr', 'tenant']
    list_filter = ['action', 'model_name', 'tenant', 'created_at']
    search_fields = ['user__username', 'object_repr', 'description', 'ip_address']
    readonly_fields = ['created_at', 'changes_display']
    
    fieldsets = (
        ('Action Details', {
            'fields': ('user', 'action', 'model_name', 'object_id', 'object_repr', 'description')
        }),
        ('Changes', {
            'fields': ('changes_display',),
        }),
        ('Request Details', {
            'fields': ('ip_address', 'user_agent', 'url', 'method')
        }),
        ('Metadata', {
            'fields': ('tenant', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Action')
    def action_badge(self, obj):
        """Display action as colored badge"""
        colors = {
            'create': 'success',
            'update': 'primary',
            'delete': 'danger',
            'view': 'info',
            'login': 'success',
            'logout': 'secondary',
            'failed_login': 'danger',
            'export': 'info',
            'import': 'info',
            'approve': 'success',
            'reject': 'danger',
            'assign': 'primary',
            'unassign': 'warning',
            'process': 'info',
            'payment': 'success',
            'refund': 'warning',
            'print': 'secondary',
            'download': 'info',
            'system': 'dark',
            'other': 'secondary',
        }
        color = colors.get(obj.action, 'secondary')
        
        # ✅ Use action_display property instead of get_action_display()
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.action_display
        )
    
    @admin.display(description='Changes')
    def changes_display(self, obj):
        """Display changes in a readable format"""
        if not obj.changes:
            return 'No changes'
        
        html = '<table style="width:100%; border-collapse: collapse;">'
        for key, value in obj.changes.items():
            if isinstance(value, dict):
                old = value.get('old', '')
                new = value.get('new', '')
                html += f'''
                    <tr>
                        <td style="padding: 4px; border-bottom: 1px solid #eee; font-weight: bold;">{key}</td>
                        <td style="padding: 4px; border-bottom: 1px solid #eee;">
                            <span style="color: #dc3545;">{old}</span> 
                            → 
                            <span style="color: #28a745;">{new}</span>
                        </td>
                    </tr>
                '''
            else:
                html += f'''
                    <tr>
                        <td style="padding: 4px; border-bottom: 1px solid #eee; font-weight: bold;">{key}</td>
                        <td style="padding: 4px; border-bottom: 1px solid #eee;">{value}</td>
                    </tr>
                '''
        html += '</table>'
        return format_html(html)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AuditLogSettings)
class AuditLogSettingsAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'enabled', 'log_all_actions', 'retention_days', 'auto_cleanup']
    list_filter = ['enabled', 'log_all_actions', 'auto_cleanup']
    search_fields = ['tenant__company_name']
    
    fieldsets = (
        ('General Settings', {
            'fields': ('tenant', 'enabled')
        }),
        ('Logging Options', {
            'fields': ('log_all_actions', 'log_reads', 'log_writes', 'log_auth')
        }),
        ('Retention', {
            'fields': ('retention_days', 'auto_cleanup')
        }),
        ('Exclusions', {
            'fields': ('excluded_models',)
        }),
    )