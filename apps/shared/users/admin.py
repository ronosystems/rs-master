# apps/shared/users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import User
from apps.shared.permissions.models import UserRoleAssignment, Role


class UserRoleAssignmentInline(admin.TabularInline):
    """Inline for managing user role assignments in admin"""
    model = UserRoleAssignment
    extra = 1
    fk_name = 'user'
    fields = ['role', 'is_active', 'assigned_by', 'notes']
    raw_id_fields = ['role', 'assigned_by']
    show_change_link = True
    can_delete = True
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('role', 'assigned_by')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter roles to only show project roles (not system roles)"""
        if db_field.name == 'role':
            kwargs['queryset'] = Role.objects.filter(
                is_system_role=False,
                is_active=True
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_max_num(self, request, obj=None, **kwargs):
        """Limit the number of role assignments for non-super admins"""
        if not request.user.is_superuser:
            return 5
        return super().get_max_num(request, obj, **kwargs)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User Admin - Simplified for Tenant Admins"""
    
    # ============================================
    # LIST DISPLAY - Simple for all users
    # ============================================
    list_display = [
        'username', 
        'full_name_display', 
        'system_role_badge', 
        'project_role_display',
        'tenant_display', 
        'is_active_display',
    ]
    
    list_filter = ['role', 'tenant', 'is_active']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'phone_number']
    
    inlines = [UserRoleAssignmentInline]
    
    # ============================================
    # FIELDSETS - Different for Super Admin vs Tenant Admin
    # ============================================
    def get_fieldsets(self, request, obj=None):
        """Return different fieldsets based on user's role"""
        
        # Super Admin sees everything
        if request.user.is_superuser:
            return [
                ('Login Credentials', {
                    'fields': ('username', 'password')
                }),
                ('Personal Information', {
                    'fields': ('first_name', 'last_name', 'email', 'phone_number')
                }),
                ('Tenant & System Role', {
                    'fields': ('tenant', 'role'),
                    'description': 'System roles: Super Admin (platform owner), Admin (company owner), User (regular staff)'
                }),
                ('Permissions', {
                    'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
                }),
            ]
        
        # Tenant Admin sees simplified view
        return [
            ('Personal Information', {
                'fields': ('first_name', 'last_name', 'email', 'phone_number')
            }),
            ('System Role', {
                'fields': ('role',),
                'description': 'System roles determine overall access level'
            }),
            ('Status', {
                'fields': ('is_active',),
            }),
        ]
    
    # ============================================
    # ADD FIELDSETS - Simplified for Tenant Admins
    # ============================================
    def get_add_fieldsets(self, request, obj=None):
        """Return different add fieldsets based on user's role"""
        
        if request.user.is_superuser:
            return (
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
        
        # Tenant Admin add fields - simplified
        return (
            (None, {
                'classes': ('wide',),
                'fields': (
                    'username', 
                    'password1', 
                    'password2',
                    'first_name',
                    'last_name',
                    'email',
                    'phone_number',
                    'is_active'
                ),
            }),
        )
    
    # ============================================
    # READONLY FIELDS - Based on permissions
    # ============================================
    readonly_fields = ['created_at', 'updated_at']
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields read-only based on permissions"""
        fields = ['created_at', 'updated_at']
        
        if obj and not request.user.is_superuser:
            # Tenant Admin cannot change system role of other users
            fields.extend(['role', 'tenant', 'is_superuser', 'is_staff'])
        
        return fields
    
    # ============================================
    # QUERYSET - Only show users from same tenant
    # ============================================
    def get_queryset(self, request):
        """Filter users based on user's role"""
        qs = super().get_queryset(request)
        
        # Super Admin sees all users
        if request.user.is_superuser:
            return qs.prefetch_related('role_assignments', 'role_assignments__role')
        
        # Tenant Admin only sees users from their tenant
        if request.user.tenant:
            return qs.filter(tenant=request.user.tenant).prefetch_related(
                'role_assignments', 'role_assignments__role'
            )
        
        return qs.none()
    
    # ============================================
    # DISPLAY METHODS
    # ============================================
    
    @admin.display(description='Full Name')
    def full_name_display(self, obj):
        return obj.full_name
    
    @admin.display(description='System Role')
    def system_role_badge(self, obj):
        """Display system role with color coding"""
        colors = {
            'super_admin': 'danger',
            'admin': 'primary',
            'user': 'secondary',
        }
        color = colors.get(obj.role, 'secondary')
        role_display = obj.role_display
        
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            role_display
        )
    
    @admin.display(description='Project Role(s)')
    def project_role_display(self, obj):
        """Display all active project roles assigned to the user"""
        assignments = UserRoleAssignment.objects.filter(
            user=obj,
            is_active=True
        ).select_related('role')
        
        if not assignments.exists():
            return mark_safe('<span class="text-muted">-</span>')
        
        # Create badges for each project role
        badges = []
        for assignment in assignments:
            badges.append(
                format_html(
                    '<span class="badge bg-info me-1">{}</span>',
                    assignment.role.name
                )
            )
        
        return mark_safe(' '.join(badges))
    
    @admin.display(description='Tenant', ordering='tenant__company_name')
    def tenant_display(self, obj):
        """Display tenant name or 'None'"""
        return obj.tenant.company_name if obj.tenant else '-'
    
    @admin.display(description='Status', boolean=True)
    def is_active_display(self, obj):
        """Display active status as boolean for admin"""
        return obj.is_active
    
    # ============================================
    # SAVE HANDLING
    # ============================================
    def save_model(self, request, obj, form, change):
        """Handle saving with tenant auto-assignment for Tenant Admins"""
        if not request.user.is_superuser and request.user.tenant:
            # Auto-assign tenant for Tenant Admins
            obj.tenant = request.user.tenant
        super().save_model(request, obj, form, change)
    
    # ============================================
    # PERMISSION CHECKS
    # ============================================
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of super admin accounts by non-super admins"""
        if obj and obj.is_super_admin and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of super admin accounts by non-super admins"""
        if obj and obj.is_super_admin and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)