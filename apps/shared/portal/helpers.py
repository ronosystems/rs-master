# apps/shared/portal/helpers.py
from apps.shared.permissions.models import UserRoleAssignment

def has_pos_access(user):
    """Check if user has POS access - includes admin/superadmin"""
    if not user.is_authenticated:
        return False
    
    # Check superuser
    if user.is_superuser:
        return True
    
    # Check groups
    if user.groups.filter(name__in=['admin', 'superadmin', 'cashier']).exists():
        return True
    
    # Check role assignments
    has_role = UserRoleAssignment.objects.filter(
        user=user,
        role__codename__in=['admin', 'superadmin', 'cashier'],
        is_active=True
    ).exists()
    
    return has_role

def is_admin_user(user):
    """Check if user is admin or superadmin"""
    if not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    if user.groups.filter(name__in=['admin', 'superadmin']).exists():
        return True
    
    has_admin_role = UserRoleAssignment.objects.filter(
        user=user,
        role__codename__in=['admin', 'superadmin'],
        is_active=True
    ).exists()
    
    return has_admin_role

def get_user_branch(user):
    """Get the branch assigned to a user"""
    if hasattr(user, 'branch') and user.branch:
        return user.branch
    elif hasattr(user, 'tech_staff_profile') and user.tech_staff_profile:
        return user.tech_staff_profile.branch
    return None