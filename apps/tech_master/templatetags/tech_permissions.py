# apps/tech_master/templatetags/tech_permissions.py

from django import template
from apps.tech_master.permissions import (
    user_has_tech_permission,
    user_has_any_tech_permission,
    user_has_all_tech_permissions,
)

register = template.Library()


@register.filter
def tech_can(user, permission_codename):
    """
    Check if user has a specific Tech Master permission.
    Usage: {% if user|tech_can:'can_view_product' %}
    """
    if not user or not user.is_authenticated:
        return False
    return user_has_tech_permission(user, permission_codename)


@register.filter
def tech_can_any(user, permission_codenames):
    """
    Check if user has ANY of the specified Tech Master permissions.
    Usage: {% if user|tech_can_any:'can_view_product,can_add_product' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if isinstance(permission_codenames, str):
        permissions = [p.strip() for p in permission_codenames.split(',') if p.strip()]
    else:
        permissions = permission_codenames
    
    return user_has_any_tech_permission(user, permissions)


@register.filter
def tech_can_all(user, permission_codenames):
    """
    Check if user has ALL of the specified Tech Master permissions.
    Usage: {% if user|tech_can_all:'can_view_product,can_add_product' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if isinstance(permission_codenames, str):
        permissions = [p.strip() for p in permission_codenames.split(',') if p.strip()]
    else:
        permissions = permission_codenames
    
    return user_has_all_tech_permissions(user, permissions)


@register.filter
def tech_has_role(user, role_name):
    """
    Check if user has a specific Tech Master role.
    Usage: {% if user|tech_has_role:'Cashier' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    from apps.shared.roles.models import ProjectRole
    return ProjectRole.objects.filter(
        users=user,
        tenant=user.tenant,
        project_type='tech_master',
        name=role_name,
        is_active=True
    ).exists()