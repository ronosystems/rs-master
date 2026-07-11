# apps/fashion_master/templatetags/fashion_permissions.py

from django import template
from apps.fashion_master.permissions import (
    user_has_fashion_permission,
    user_has_any_fashion_permission,
    user_has_all_fashion_permissions,
    get_user_fashion_permissions,
    get_user_fashion_roles
)

register = template.Library()


@register.filter
def fashion_can(user, permission_codename):
    """
    Check if user has a specific Fashion Master permission.
    Usage: {% if user|fashion_can:'can_view_product' %}
    """
    if not user or not user.is_authenticated:
        return False
    return user_has_fashion_permission(user, permission_codename)


@register.filter
def fashion_can_any(user, permission_codenames):
    """
    Check if user has ANY of the specified Fashion Master permissions.
    Usage: {% if user|fashion_can_any:'can_view_product,can_add_product' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if isinstance(permission_codenames, str):
        permissions = [p.strip() for p in permission_codenames.split(',') if p.strip()]
    else:
        permissions = permission_codenames
    
    return user_has_any_fashion_permission(user, permissions)


@register.filter
def fashion_can_all(user, permission_codenames):
    """
    Check if user has ALL of the specified Fashion Master permissions.
    Usage: {% if user|fashion_can_all:'can_view_product,can_add_product' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if isinstance(permission_codenames, str):
        permissions = [p.strip() for p in permission_codenames.split(',') if p.strip()]
    else:
        permissions = permission_codenames
    
    return user_has_all_fashion_permissions(user, permissions)


@register.filter
def fashion_has_role(user, role_name):
    """
    Check if user has a specific Fashion Master role.
    Usage: {% if user|fashion_has_role:'Store Manager' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    from apps.fashion_master.models import FashionRole
    return FashionRole.objects.filter(
        users=user,
        tenant=user.tenant,
        name=role_name,
        is_active=True
    ).exists()


@register.filter
def fashion_has_any_role(user, role_names):
    """
    Check if user has ANY of the specified Fashion Master roles.
    Usage: {% if user|fashion_has_any_role:'Store Manager,Sales Rep' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if isinstance(role_names, str):
        roles = [r.strip() for r in role_names.split(',') if r.strip()]
    else:
        roles = role_names
    
    from apps.fashion_master.models import FashionRole
    return FashionRole.objects.filter(
        users=user,
        tenant=user.tenant,
        name__in=roles,
        is_active=True
    ).exists()


@register.simple_tag
def fashion_user_permissions(user):
    """
    Get all permissions for a user as a list.
    Usage: {% fashion_user_permissions user as perms %}
    """
    if not user or not user.is_authenticated:
        return []
    return get_user_fashion_permissions(user)


@register.simple_tag
def fashion_user_roles(user):
    """
    Get all roles for a user.
    Usage: {% fashion_user_roles user as roles %}
    """
    if not user or not user.is_authenticated:
        return []
    return get_user_fashion_roles(user)


@register.simple_tag(takes_context=True)
def fashion_check_perm(context, permission_codename):
    """
    Check permission in template context.
    Usage: {% fashion_check_perm 'can_view_product' as has_perm %}
    """
    request = context.get('request')
    if not request:
        return False
    return user_has_fashion_permission(request.user, permission_codename)



@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key"""
    if dictionary is None:
        return None
    return dictionary.get(key)