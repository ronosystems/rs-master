import logging

logger = logging.getLogger(__name__)

TRONIC_MASTER_PERMISSIONS = {
    # ============================================
    # DASHBOARD MENU
    # ============================================
    'can_view_report': 'View Reports Dashboard',
    'can_view_sale': 'View Sales History',
    'can_view_low_stock': 'View Low Stock Alerts',
    'can_create_sale': 'Create Sale',
    'can_process_payment': 'Process Payment',
    
    # ============================================
    # MEMBERS MENU
    # ============================================
    'can_view_staff': 'View Staff List',
    'can_add_staff': 'Add Staff',
    'can_manage_staff': 'Manage Staff',
    'can_view_staff_attendance': 'View Staff Attendance',
    'can_view_staff_leave': 'View Staff Leave',
    'can_view_roles': 'View Roles List',
    'can_create_role': 'Create Role',
    'can_assign_role': 'Assign Role',
    
    # ============================================
    # BRANCHES MENU
    # ============================================
    'can_view_branch': 'View Branches',
    'can_add_branch': 'Add Branch',
    'can_manage_branch': 'Manage Branches',
    'can_view_branch_stock': 'View Branch Stock',
    'can_transfer_stock': 'Transfer Stock',
    
    # ============================================
    # INVENTORY - CATEGORIES
    # ============================================
    'can_view_category': 'View Categories',
    'can_add_category': 'Add Category',
    'can_edit_category': 'Edit Category',
    'can_manage_categories': 'Manage Categories',
    
    # ============================================
    # INVENTORY - PRODUCTS
    # ============================================
    'can_view_product': 'View Products',
    'can_add_product': 'Add Product',
    'can_edit_product': 'Edit Product',
    'can_manage_products': 'Manage Products',
    'can_view_damaged_units': 'View Damaged Units',
    'can_transfer_items': 'Transfer Items',
    'can_bulk_print_labels': 'Bulk Print Labels',
    'can_view_product_barcodes': 'View Product Barcodes',
    'can_import_products': 'Import Products',
    
    # ============================================
    # INVENTORY - STOCK
    # ============================================
    'can_view_stock': 'View Stock',
    'can_manage_stock': 'Manage Stock',
    'can_view_stock_report': 'View Stock Report',
    'can_view_stock_history': 'View Stock History',
    'can_assign_to_agent': 'Assign to Agent',
    
    # ============================================
    # SALES MENU
    # ============================================
    'can_view_agent_sale': 'View Agent Sale',
    'can_view_sales_history': 'View Sales History',
    'can_search_sales': 'Search Sales',
    'can_view_returns': 'View Returns',
    'can_view_receipt': 'View Receipt',
    'can_view_receipt_search': 'View Receipt Search',
    
    # ============================================
    # SUPPLIERS MENU
    # ============================================
    'can_view_supplier': 'View Suppliers',
    'can_add_supplier': 'Add Supplier',
    'can_edit_supplier': 'Edit Supplier',
    'can_manage_suppliers': 'Manage Suppliers',
    
    # ============================================
    # REPORTS MENU
    # ============================================
    'can_view_report_dashboard': 'View Report Dashboard',
    'can_view_sales_reports': 'View Sales Reports',
    'can_view_expenses': 'View Expenses',
    'can_view_expense_report': 'View Expense Report',
    'can_view_inventory_report': 'View Inventory Report',
    'can_export_report': 'Export Reports',
    
    # ============================================
    # SETTINGS MENU
    # ============================================
    'can_view_settings': 'View Settings',
    'can_manage_settings': 'Manage Settings',
    'can_view_receipt_settings': 'View Receipt Settings',
    'can_view_payment_settings': 'View Payment Settings',
    'can_view_company_settings': 'View Company Settings',
    
    # ============================================
    # MY BUSINESS MENU
    # ============================================
    'can_view_my_stock': 'View My Stock',
    'can_view_my_sales': 'View My Sales',
    'can_view_agent_sale_form': 'View Agent Sale Form',
    
    # ============================================
    # PRICE LOOKUP MENU
    # ============================================
    'can_view_price_check': 'View Price Check',
    'can_view_product_search': 'View Product Search',
}


def user_has_tronic_permission(user, permission_codename):
    """
    Check if user has a specific Tronic Master permission.
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_super_admin:
        return True
    
    if user.is_tenant_admin:
        return True
    
    if permission_codename not in TRONIC_MASTER_PERMISSIONS:
        return False
    
    from apps.shared.roles.models import ProjectRole
    
    try:
        roles = ProjectRole.objects.filter(
            users=user,
            tenant=user.tenant,
            project_type='tronic_master',
            is_active=True
        )
        
        for role in roles:
            if permission_codename in role.permissions:
                return True
                
    except Exception as e:
        logger.error(f"Error checking permission {permission_codename} for user {user.username}: {e}")
        return False
    
    return False


def user_has_any_tronic_permission(user, permission_list):
    """
    Check if user has ANY of the specified Tronic Master permissions.
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_super_admin or user.is_tenant_admin:
        return True
    
    for perm in permission_list:
        if user_has_tronic_permission(user, perm):
            return True
    return False


def user_has_all_tronic_permissions(user, permission_list):
    """
    Check if user has ALL of the specified Tronic Master permissions.
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_super_admin or user.is_tenant_admin:
        return True
    
    for perm in permission_list:
        if not user_has_tronic_permission(user, perm):
            return False
    return True


def get_user_tronic_permissions(user):
    """
    Get all Tronic Master permissions for a user.
    """
    if not user or not user.is_authenticated:
        return []
    
    if user.is_super_admin or user.is_tenant_admin:
        return list(TRONIC_MASTER_PERMISSIONS.keys())
    
    from apps.shared.roles.models import ProjectRole
    
    try:
        roles = ProjectRole.objects.filter(
            users=user,
            tenant=user.tenant,
            project_type='tronic_master',
            is_active=True
        )
        
        permissions = set()
        for role in roles:
            permissions.update(role.permissions)
        
        return list(permissions)
        
    except Exception as e:
        logger.error(f"Error getting user permissions for {user.username}: {e}")
        return []
