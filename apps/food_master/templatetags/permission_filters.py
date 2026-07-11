# apps/food_master/templatetags/permission_filters.py

from django import template
from apps.shared.permissions.models import UserRoleAssignment

register = template.Library()

@register.filter(name='has_perm')
def has_perm(user, perm):
    """
    Check if user has a specific permission.
    Usage: {% if user|has_perm:'food_master.can_take_orders' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    # Super admins and tenant admins have all permissions
    if user.is_super_admin or user.is_tenant_admin:
        return True
    
    # Check if user has the specific permission directly
    if user.has_perm(perm):
        return True
    
    # Check if user has the permission via role assignments
    if hasattr(user, 'role_assignments'):
        # Get all active role assignments for this user
        assignments = UserRoleAssignment.objects.filter(
            user=user,
            is_active=True
        ).select_related('role')
        
        # Extract permission codename from the full permission string
        perm_codename = perm.split('.')[-1] if '.' in perm else perm
        
        for assignment in assignments:
            role = assignment.role
            # Check if role has the permission
            if role.permissions.filter(codename=perm_codename).exists():
                return True
    
    return False


@register.filter(name='has_any_perm')
def has_any_perm(user, perms):
    """
    Check if user has any of the specified permissions.
    Usage: {% if user|has_any_perm:'food_master.can_take_orders,food_master.can_view_orders' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    # Super admins and tenant admins have all permissions
    if user.is_super_admin or user.is_tenant_admin:
        return True
    
    perm_list = [p.strip() for p in perms.split(',')]
    for perm in perm_list:
        if has_perm(user, perm):
            return True
    
    return False


@register.filter(name='has_all_perms')
def has_all_perms(user, perms):
    """
    Check if user has all of the specified permissions.
    Usage: {% if user|has_all_perms:'food_master.can_take_orders,food_master.can_view_orders' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    # Super admins and tenant admins have all permissions
    if user.is_super_admin or user.is_tenant_admin:
        return True
    
    perm_list = [p.strip() for p in perms.split(',')]
    for perm in perm_list:
        if not has_perm(user, perm):
            return False
    
    return True


@register.simple_tag
def user_has_perm(user, perm):
    """
    Simple tag to check permission.
    Usage: {% user_has_perm user 'food_master.can_take_orders' %}
    """
    return has_perm(user, perm)  