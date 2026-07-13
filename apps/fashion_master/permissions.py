# apps/fashion_master/permissions.py

import logging

logger = logging.getLogger(__name__)

# ============================================
# FASHION MASTER PERMISSIONS - MASTER LIST
# ============================================
FASHION_MASTER_PERMISSIONS = {
    # Dashboard
    'can_view_dashboard': 'View Dashboard',
    
    # Products
    'can_view_product': 'View Products',
    'can_add_product': 'Add Products',
    'can_edit_product': 'Edit Products',
    'can_delete_product': 'Delete Products',
    'can_manage_product': 'Manage Products',
    
    # Categories
    'can_view_category': 'View Categories',
    'can_add_category': 'Add Categories',
    'can_edit_category': 'Edit Categories',
    'can_delete_category': 'Delete Categories',
    
    # Branches
    'can_view_branch': 'View Branches',
    'can_add_branch': 'Add Branches',
    'can_edit_branch': 'Edit Branches',
    'can_delete_branch': 'Delete Branches',
    'can_manage_branch': 'Manage Branches',
    'can_view_branch_stock': 'View Branch Stock',
    'can_transfer_stock': 'Transfer Stock',
    'can_assign_branch_manager': 'Assign Branch Manager',
    
    # Stock/Inventory
    'can_view_stock': 'View Stock',
    'can_manage_stock': 'Manage Stock',
    'can_adjust_stock': 'Adjust Stock',
    'can_view_low_stock': 'View Low Stock Alerts',
    
    # Sales
    'can_view_sale': 'View Sales',
    'can_create_sale': 'Create Sales',
    'can_edit_sale': 'Edit Sales',
    'can_delete_sale': 'Delete Sales',
    'can_process_payment': 'Process Payments',
    'can_view_receipt': 'View Receipts',
    'can_search_sale': 'Search Sales',
    
    # Returns
    'can_view_return': 'View Returns',
    'can_create_return': 'Create Returns',
    'can_approve_return': 'Approve Returns',
    'can_reject_return': 'Reject Returns',
    'can_manage_return': 'Manage Returns',
    
    # Staff
    'can_view_staff': 'View Staff',
    'can_add_staff': 'Add Staff',
    'can_edit_staff': 'Edit Staff',
    'can_delete_staff': 'Delete Staff',
    'can_manage_staff': 'Manage Staff',
    'can_view_staff_attendance': 'View Staff Attendance',
    'can_manage_staff_attendance': 'Manage Staff Attendance',
    'can_view_staff_leave': 'View Staff Leave',
    'can_manage_staff_leave': 'Manage Staff Leave',
    
    # Roles
    'can_view_role': 'View Roles',
    'can_add_role': 'Add Roles',
    'can_edit_role': 'Edit Roles',
    'can_delete_role': 'Delete Roles',
    'can_manage_role': 'Manage Roles',
    'can_assign_role': 'Assign Roles',
    
    # Reports
    'can_view_report': 'View Reports',
    'can_export_report': 'Export Reports',
    'can_view_sales_report': 'View Sales Reports',
    'can_view_inventory_report': 'View Inventory Reports',
    'can_view_expense_report': 'View Expense Reports',
    
    # Settings
    'can_view_settings': 'View Settings',
    'can_manage_settings': 'Manage Settings',
    'can_view_receipt_settings': 'View Receipt Settings',
    'can_view_payment_settings': 'View Payment Settings',
    'can_view_company_settings': 'View Company Settings',
    'can_view_store_settings': 'View Store Settings',
    'can_view_tax_settings': 'View Tax Settings',
    
    # My Work / Agent
    'can_view_my_stock': 'View My Stock',
    'can_view_my_sales': 'View My Sales',
    'can_create_agent_sale': 'Create Agent Sale',
    
    # Lookups
    'can_price_check': 'Price Check',
    'can_product_search': 'Product Search',
}


# ============================================
# PERMISSION CHECK FUNCTIONS
# ============================================

def user_has_fashion_permission(user, permission_codename):
    """
    Check if user has a specific Fashion Master permission.
    Works with SQLite - NO JSON contains lookup.
    """
    if not user or not user.is_authenticated:
        return False
    
    # Super admins have all permissions
    if user.is_super_admin:
        return True
    
    # Tenant admins have all permissions for their tenant
    if user.is_tenant_admin:
        return True
    
    # Check if permission exists in our list
    if permission_codename not in FASHION_MASTER_PERMISSIONS:
        return False
    
    # Get all roles for this user
    from apps.fashion_master.models import FashionRole
    
    try:
        # Get roles using ManyToMany relationship
        roles = FashionRole.objects.filter(
            users=user,
            tenant=user.tenant,
            is_active=True
        )
        
        # Check each role's permissions (list of strings)
        for role in roles:
            if permission_codename in role.permissions:
                return True
                
    except Exception as e:
        logger.error(f"Error checking permission {permission_codename} for user {user.username}: {e}")
        return False
    
    return False


def user_has_any_fashion_permission(user, permission_list):
    """
    Check if user has ANY of the specified Fashion Master permissions.
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_super_admin or user.is_tenant_admin:
        return True
    
    # Split comma-separated string if needed
    if isinstance(permission_list, str):
        permission_list = [p.strip() for p in permission_list.split(',') if p.strip()]
    
    for perm in permission_list:
        if user_has_fashion_permission(user, perm):
            return True
    return False


def user_has_all_fashion_permissions(user, permission_list):
    """
    Check if user has ALL of the specified Fashion Master permissions.
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_super_admin or user.is_tenant_admin:
        return True
    
    # Split comma-separated string if needed
    if isinstance(permission_list, str):
        permission_list = [p.strip() for p in permission_list.split(',') if p.strip()]
    
    for perm in permission_list:
        if not user_has_fashion_permission(user, perm):
            return False
    return True


def get_user_fashion_permissions(user):
    """
    Get all Fashion Master permissions for a user.
    """
    if not user or not user.is_authenticated:
        return []
    
    if user.is_super_admin or user.is_tenant_admin:
        return list(FASHION_MASTER_PERMISSIONS.keys())
    
    from apps.fashion_master.models import FashionRole
    
    try:
        roles = FashionRole.objects.filter(
            users=user,
            tenant=user.tenant,
            is_active=True
        )
        
        permissions = set()
        for role in roles:
            permissions.update(role.permissions)
        
        return list(permissions)
        
    except Exception as e:
        logger.error(f"Error getting user permissions for {user.username}: {e}")
        return []


def get_user_fashion_roles(user):
    """
    Get all Fashion Master roles for a user.
    """
    if not user or not user.is_authenticated:
        return []
    
    from apps.fashion_master.models import FashionRole
    
    try:
        roles = FashionRole.objects.filter(
            users=user,
            tenant=user.tenant,
            is_active=True
        )
        return list(roles)
        
    except Exception as e:
        logger.error(f"Error getting user roles for {user.username}: {e}")
        return []


# ============================================
# TEMPLATE FILTERS (for use in templates)
# ============================================

from django import template
register = template.Library()

@register.filter(name='fashion_can')
def fashion_can(user, permission):
    """Template filter to check if user has a permission"""
    return user_has_fashion_permission(user, permission)

@register.filter(name='fashion_can_any')
def fashion_can_any(user, permission_list):
    """Template filter to check if user has ANY of the permissions"""
    return user_has_any_fashion_permission(user, permission_list)

@register.filter(name='fashion_can_all')
def fashion_can_all(user, permission_list):
    """Template filter to check if user has ALL of the permissions"""
    return user_has_all_fashion_permissions(user, permission_list)

@register.filter(name='fashion_has_role')
def fashion_has_role(user, role_name):
    """Template filter to check if user has a specific fashion role"""
    if not user or not user.is_authenticated:
        return False
    
    from apps.fashion_master.models import FashionRole
    
    try:
        return FashionRole.objects.filter(
            users=user,
            tenant=user.tenant,
            name=role_name,
            is_active=True
        ).exists()
    except Exception as e:
        logger.error(f"Error checking role for user {user.username}: {e}")
        return False