# apps/tech_master/permissions.py

import logging

logger = logging.getLogger(__name__)

# ============================================
# TECH MASTER PERMISSIONS - ONE PER MENU ITEM
# ============================================
TECH_MASTER_PERMISSIONS = {
    # ============================================
    # DASHBOARD MENU
    # ============================================
    'can_view_dashboard_overview': 'View Dashboard Overview',
    'can_view_reports_dashboard': 'View Reports Dashboard',
    'can_view_sales_history': 'View Sales History',
    'can_view_low_stock_alerts': 'View Low Stock Alerts',
    'can_view_pos': 'View Point of Sale',
    
    # ============================================
    # COMPANY MENU
    # ============================================
    'can_view_check_plans': 'View Check Plans',
    'can_view_my_subscription': 'View My Subscription',
    
    # ============================================
    # MEMBERS MENU
    # ============================================
    'can_view_staff_list': 'View Staff List',
    'can_manage_staff': 'Manage Staff',
    'can_add_staff': 'Add Staff',
    'can_view_staff_attendance': 'View Staff Attendance',
    'can_view_staff_leave': 'View Staff Leave',
    'can_view_roles_list': 'View Roles List',
    'can_create_role': 'Create Role',
    'can_assign_role': 'Assign Role',
    
    # ============================================
    # BRANCHES MENU
    # ============================================
    'can_view_branches': 'View Shop Branches',
    'can_add_branch': 'Add Branch',
    'can_assign_branch_manager': 'Assign Branch Manager',
    'can_view_branch_stock': 'View Branch Stock',
    'can_transfer_stock': 'Transfer Stock',
    
    # ============================================
    # INVENTORY - CATEGORIES
    # ============================================
    'can_view_categories': 'View Categories',
    'can_manage_categories': 'Manage Categories',
    'can_add_category': 'Add Category',
    
    # ============================================
    # INVENTORY - PRODUCTS
    # ============================================
    'can_view_products': 'View Product List',
    'can_manage_products': 'Manage Products',
    'can_add_product': 'Add Product',
    'can_view_damaged_units': 'View Damaged Units',
    'can_transfer_items': 'Item Transfer',
    'can_bulk_print_labels': 'Bulk Print Labels',
    'can_view_product_barcodes': 'View Product Barcodes',
    'can_import_products': 'Import Products',
    
    # ============================================
    # INVENTORY - STOCK
    # ============================================
    'can_manage_stock': 'Manage Stock',
    'can_view_stock_report': 'View Stock Report',
    'can_view_stock_history': 'View Stock History',
    'can_assign_to_agent': 'Assign Products to Agent',
    
    # ============================================
    # SALES MENU
    # ============================================
    'can_view_agent_sale': 'View Agent Sale',
    'can_view_sales_history': 'View Sales History',
    'can_search_sales': 'Search Sales',
    'can_view_returns': 'View Returns',
    'can_view_receipt_search': 'View Receipt Search',
    
    # ============================================
    # SUPPLIERS MENU
    # ============================================
    'can_view_suppliers': 'View Supplier List',
    'can_manage_suppliers': 'Manage Suppliers',
    'can_add_supplier': 'Add Supplier',
    
    # ============================================
    # REPORTS MENU
    # ============================================
    'can_view_report_dashboard': 'View Report Dashboard',
    'can_view_sales_reports': 'View Sales Reports',
    'can_view_expenses': 'View Expenses',
    'can_view_expense_report': 'View Expense Report',
    'can_view_inventory_report': 'View Inventory Report',
    'can_export_reports': 'Export Reports',
    
    # ============================================
    # SETTINGS MENU
    # ============================================
    'can_view_receipt_settings': 'View Receipt Settings',
    'can_view_payment_settings': 'View Payment Settings',
    'can_view_company_settings': 'View Company Settings',
    
    # ============================================
    # MY WORK MENU
    # ============================================
    'can_view_my_stock': 'View My Stock',
    'can_view_my_sales': 'View My Sales',
    'can_view_agent_sale_form': 'View Agent Sale Form',
    
    # ============================================
    # LOOKUPS MENU
    # ============================================
    'can_view_price_check': 'View Price Check',
    'can_view_product_search': 'View Product Search',
}


# ============================================
# PERMISSION CHECK FUNCTIONS
# ============================================

def user_has_tech_permission(user, permission_codename):
    """
    Check if user has a specific Tech Master permission.
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
    if permission_codename not in TECH_MASTER_PERMISSIONS:
        return False
    
    # Get all roles for this user
    from apps.shared.roles.models import ProjectRole
    
    try:
        # Get roles using ManyToMany relationship
        roles = ProjectRole.objects.filter(
            users=user,
            tenant=user.tenant,
            project_type='tech_master',
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


def user_has_any_tech_permission(user, permission_list):
    """
    Check if user has ANY of the specified Tech Master permissions.
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_super_admin or user.is_tenant_admin:
        return True
    
    for perm in permission_list:
        if user_has_tech_permission(user, perm):
            return True
    return False


def user_has_all_tech_permissions(user, permission_list):
    """
    Check if user has ALL of the specified Tech Master permissions.
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_super_admin or user.is_tenant_admin:
        return True
    
    for perm in permission_list:
        if not user_has_tech_permission(user, perm):
            return False
    return True


def get_user_tech_permissions(user):
    """
    Get all Tech Master permissions for a user.
    """
    if not user or not user.is_authenticated:
        return []
    
    if user.is_super_admin or user.is_tenant_admin:
        return list(TECH_MASTER_PERMISSIONS.keys())
    
    from apps.shared.roles.models import ProjectRole
    
    try:
        roles = ProjectRole.objects.filter(
            users=user,
            tenant=user.tenant,
            project_type='tech_master',
            is_active=True
        )
        
        permissions = set()
        for role in roles:
            permissions.update(role.permissions)
        
        return list(permissions)
        
    except Exception as e:
        logger.error(f"Error getting user permissions for {user.username}: {e}")
        return []