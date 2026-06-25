# apps/shared/users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User Admin"""
    
    list_display = [
        'username', 
        'full_name_display', 
        'role_badge', 
        'tenant_display', 
        'is_active',
        'created_at'
    ]
    
    list_filter = ['role', 'tenant', 'is_active']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'phone_number']
    
    fieldsets = (
        ('Login Credentials', {
            'fields': ('username', 'password')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone_number')
        }),
        ('Tenant & Role', {
            'fields': ('tenant', 'role')
        }),
        ('POS Settings', {
            'fields': ('pin_code',),
            'classes': ('collapse',)
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 
                'password1', 
                'password2', 
                'role', 
                'tenant',
                'first_name',
                'last_name',
                'email',
                'phone_number',
                'is_active'
            ),
        }),
    )
    
    @admin.display(description='Full Name')
    def full_name_display(self, obj):
        return obj.full_name
    
    @admin.display(description='Role')
    def role_badge(self, obj):
        colors = {
            'super_admin': 'danger',
            'admin': 'primary',
            'manager': 'warning',
            'cashier': 'success',
            'sales_agent': 'info',
        }
        color = colors.get(obj.role, 'secondary')
        role_display = obj.role_display
        
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            role_display
        )
    
    @admin.display(description='Tenant')
    def tenant_display(self, obj):
        """Display tenant name or 'None'"""
        return obj.tenant.company_name if obj.tenant else '-'