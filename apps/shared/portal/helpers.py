# apps/shared/portal/helpers.py

from django.contrib import messages
from apps.shared.permissions.models import UserRoleAssignment
import logging

logger = logging.getLogger(__name__)


def check_subscription_limit(tenant, limit_type, current_count, max_limit, request=None):
    """
    Check if a tenant has reached their subscription limit.
    
    Args:
        tenant: The tenant object
        limit_type: String describing the limit (e.g., 'staff', 'products', 'users')
        current_count: Current number of items
        max_limit: Maximum allowed by subscription
        request: Django request object for redirects
    
    Returns:
        bool: True if limit is reached, False otherwise
    """
    if max_limit is None or max_limit == 0:
        # No limit set
        return False
    
    if current_count >= max_limit:
        if request:
            messages.error(
                request,
                f'<strong>⚠️ Subscription Limit Reached!</strong><br>'
                f'You have reached the maximum of {max_limit} {limit_type} allowed in your current plan. '
                f'Please upgrade your subscription to add more {limit_type}.'
            )
            logger.warning(f"Subscription limit reached for tenant {tenant.id}: {limit_type} limit {max_limit}")
        return True
    
    # Show warning if close to limit (80% or more)
    if current_count >= max_limit * 0.8:
        remaining = max_limit - current_count
        if request:
            messages.warning(
                request,
                f'<strong>⚠️ Subscription Limit Warning</strong><br>'
                f'You are approaching your {limit_type} limit. '
                f'You have {remaining} {limit_type} remaining. '
                f'Consider upgrading your plan to avoid reaching the limit.'
            )
    
    return False


def get_subscription_limit(tenant, limit_type):
    """
    Get the subscription limit for a specific type.
    """
    # Default limits based on subscription plan
    default_limits = {
        'staff': 10,
        'products': 100,
        'users': 5,
        'branches': 3,
        'storage_gb': 1,
    }
    
    # If tenant has a subscription plan, use those limits
    if hasattr(tenant, 'subscription_plan') and tenant.subscription_plan:
        try:
            from apps.shared.tenants.models import SubscriptionPlan
            plan = SubscriptionPlan.objects.filter(code=tenant.subscription_plan).first()
            if plan:
                limit_map = {
                    'staff': plan.max_users,
                    'users': plan.max_users,
                    'products': plan.max_products,
                    'branches': plan.max_branches,
                    'storage_gb': plan.max_storage_gb,
                }
                return limit_map.get(limit_type, default_limits.get(limit_type, 999))
        except Exception as e:
            logger.error(f"Error getting subscription limit: {e}")
    
    return default_limits.get(limit_type, 999)


def show_upgrade_prompt(request):
    """
    Show a prompt to upgrade subscription.
    """
    messages.error(
        request,
        '<strong>🚀 Upgrade Required!</strong><br>'
        'You have reached the limit of your current subscription plan. '
        'Please contact your administrator to upgrade your plan and continue adding items.<br><br>'
        '<a href="/subscription/plans/" class="btn btn-primary btn-sm">'
        '<i class="fas fa-rocket me-1"></i>View Plans</a>'
    )


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
    
    # ✅ Check role field
    if hasattr(user, 'role') and user.role in ['admin', 'super_admin', 'tenant_admin', 'cashier']:
        return True
    
    # Check role assignments
    has_role = UserRoleAssignment.objects.filter(
        user=user,
        role__codename__in=['admin', 'superadmin', 'cashier', 'tenant_admin'],
        is_active=True
    ).exists()
    
    if has_role:
        return True
    
    # ✅ Check if user is staff (has admin panel access)
    if user.is_staff:
        return True
    
    return False


def is_admin_user(user):
    """Check if user is admin or superadmin"""
    if not user.is_authenticated:
        return False
    
    # Check superuser
    if user.is_superuser:
        return True
    
    # Check groups
    if user.groups.filter(name__in=['admin', 'superadmin']).exists():
        return True
    
    # ✅ Check role field
    if hasattr(user, 'role') and user.role in ['admin', 'super_admin', 'tenant_admin']:
        return True
    
    # Check role assignments
    has_admin_role = UserRoleAssignment.objects.filter(
        user=user,
        role__codename__in=['admin', 'superadmin', 'tenant_admin'],
        is_active=True
    ).exists()
    
    if has_admin_role:
        return True
    
    # ✅ Check if user is staff (has admin panel access)
    if user.is_staff:
        return True
    
    return False


def get_user_branch(user):
    """Get the branch assigned to a user"""
    if hasattr(user, 'branch') and user.branch:
        return user.branch
    elif hasattr(user, 'tech_staff_profile') and user.tech_staff_profile:
        return user.tech_staff_profile.branch
    return None