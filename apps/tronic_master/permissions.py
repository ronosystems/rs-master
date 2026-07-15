# apps/tronic_master/permissions.py

import logging

logger = logging.getLogger(__name__)

# ============================================
# TECH MASTER PERMISSIONS - ONE PER MENU ITEM
# ============================================

TRONIC_MASTER_PERMISSIONS = {
    # ============================================
    # DASHBOARD MENU
    # ============================================
    'can_view_report': 'View Reports Dashboard',           # ← Fixed
    'can_view_sale': 'View Sales History',                 # ← Fixed
    'can_view_low_stock': 'View Low Stock Alerts',         # ← Fixed
    'can_create_sale': 'Create Sale',                      # ← Fixed
    'can_process_payment': 'Process Payment',              # ← Fixed

    # ============================================
    # MEMBERS MENU
    # ============================================
    'can_view_staff': 'View Staff List',                   # ← Fixed
    'can_add_staff': 'Add Staff',                          # ← Fixed
    'can_manage_staff': 'Manage Staff',                    # ← Fixed
    'can_view_staff_attendance': 'View Staff Attendance',  # ← Fixed
    'can_view_staff_leave': 'View Staff Leave',            # ← Fixed
    'can_view_roles': 'View Roles List',                   # ← Fixed
    'can_create_role': 'Create Role',                      # ← Fixed
    'can_assign_role': 'Assign Role',                      # ← Fixed

    # ============================================
    # BRANCHES MENU
    # ============================================
    'can_view_branch': 'View Branches',                    # ← Fixed
    'can_add_branch': 'Add Branch',                        # ← Fixed
    'can_manage_branch': 'Manage Branches',                # ← Fixed
    'can_view_branch_stock': 'View Branch Stock',          # ← Fixed
    'can_transfer_stock': 'Transfer Stock',                # ← Fixed

    # ============================================
    # INVENTORY - CATEGORIES
    # ============================================
    'can_view_category': 'View Categories',                # ← Fixed
    'can_add_category': 'Add Category',                    # ← Fixed
    'can_edit_category': 'Edit Category',                  # ← Fixed
    'can_manage_categories': 'Manage Categories',          # ← Fixed

    # ============================================
    # INVENTORY - PRODUCTS
    # ============================================
    'can_view_product': 'View Products',                   # ← Fixed
    'can_add_product': 'Add Product',                      # ← Fixed
    'can_edit_product': 'Edit Product',                    # ← Fixed
    'can_manage_products': 'Manage Products',              # ← Fixed
    'can_view_damaged_units': 'View Damaged Units',        # ← Fixed
    'can_transfer_items': 'Transfer Items',                # ← Fixed
    'can_bulk_print_labels': 'Bulk Print Labels',          # ← Fixed
    'can_view_product_barcodes': 'View Product Barcodes',  # ← Fixed
    'can_import_products': 'Import Products',              # ← Fixed

    # ============================================
    # INVENTORY - STOCK
    # ============================================
    'can_view_stock': 'View Stock',                        # ← Fixed
    'can_manage_stock': 'Manage Stock',                    # ← Fixed
    'can_view_stock_report': 'View Stock Report',          # ← Fixed
    'can_view_stock_history': 'View Stock History',        # ← Fixed
    'can_assign_to_agent': 'Assign to Agent',              # ← Fixed

    # ============================================
    # SALES MENU
    # ============================================
    'can_view_agent_sale': 'View Agent Sale',              # ← Fixed
    'can_view_sales_history': 'View Sales History',        # ← Fixed
    'can_search_sales': 'Search Sales',                    # ← Fixed
    'can_view_returns': 'View Returns',                    # ← Fixed
    'can_view_receipt': 'View Receipt',                    # ← Fixed
    'can_view_receipt_search': 'View Receipt Search',      # ← Fixed

    # ============================================
    # SUPPLIERS MENU
    # ============================================
    'can_view_supplier': 'View Suppliers',                 # ← Fixed
    'can_add_supplier': 'Add Supplier',                    # ← Fixed
    'can_edit_supplier': 'Edit Supplier',                  # ← Fixed
    'can_manage_suppliers': 'Manage Suppliers',            # ← Fixed

    # ============================================
    # REPORTS MENU
    # ============================================
    'can_view_report_dashboard': 'View Report Dashboard',  # ← Fixed
    'can_view_sales_reports': 'View Sales Reports',        # ← Fixed
    'can_view_expenses': 'View Expenses',                  # ← Fixed
    'can_view_expense_report': 'View Expense Report',      # ← Fixed
    'can_view_inventory_report': 'View Inventory Report',  # ← Fixed
    'can_export_report': 'Export Reports',                 # ← Fixed

    # ============================================
    # SETTINGS MENU
    # ============================================
    'can_view_settings': 'View Settings',                  # ← Fixed
    'can_manage_settings': 'Manage Settings',              # ← Fixed
    'can_view_receipt_settings': 'View Receipt Settings',  # ← Fixed
    'can_view_payment_settings': 'View Payment Settings',  # ← Fixed
    'can_view_company_settings': 'View Company Settings',  # ← Fixed

    # ============================================
    # MY BUSINESS MENU
    # ============================================
    'can_view_my_stock': 'View My Stock',                  # ← Fixed
    'can_view_my_sales': 'View My Sales',                  # ← Fixed
    'can_view_agent_sale_form': 'View Agent Sale Form',    # ← Fixed

    # ============================================
    # PRICE LOOKUP MENU
    # ============================================
    'can_view_price_check': 'View Price Check',            # ← Fixed
    'can_view_product_search': 'View Product Search',      # ← Fixed
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
    if permission_codename not in TRONIC_MASTER_PERMISSIONS:
        return False

    # Get all roles for this user
    from apps.shared.roles.models import ProjectRole

    try:
        # Get roles using ManyToMany relationship
        roles = ProjectRole.objects.filter(
            users=user,
            tenant=user.tenant,
            project_type='tronic_master',
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