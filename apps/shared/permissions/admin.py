# apps/shared/permissions/admin.py

from django.contrib import admin
from .models import Role, SystemPermission, UserRoleAssignment


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'codename', 'role_type', 'is_system_role', 'is_active', 'permission_count']
    list_filter = ['role_type', 'is_system_role', 'is_active']
    search_fields = ['name', 'codename', 'description']
    filter_horizontal = ['permissions', 'users', 'project_types']
    
    @admin.display(description='Permissions')
    def permission_count(self, obj):
        return obj.permissions.count()


@admin.register(SystemPermission)
class SystemPermissionAdmin(admin.ModelAdmin):
    list_display = ['codename', 'name', 'action', 'category', 'is_active']
    list_filter = ['action', 'category', 'is_active']
    search_fields = ['django_permission__codename', 'django_permission__name', 'description']
    readonly_fields = ['codename', 'name']
    
    def codename(self, obj):
        return obj.django_permission.codename
    
    def name(self, obj):
        return obj.django_permission.name


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'assigned_by', 'assigned_at', 'is_active']
    list_filter = ['is_active', 'assigned_at']
    search_fields = ['user__username', 'role__name']
    readonly_fields = ['assigned_at']
    raw_id_fields = ['user', 'role', 'assigned_by']