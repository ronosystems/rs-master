# apps/tronic_master/views_helpers.py
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def tech_permission_required(permission):
    """
    Decorator for class-based views to check permission
    Usage: @tech_permission_required('can_view_product')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            from apps.tronic_master.permission_tech import has_tech_permission
            if has_tech_permission(request.user, permission):
                return view_func(request, *args, **kwargs)
            messages.error(request, f'You do not have permission to access this page.')
            return redirect('tronic_master:dashboard')
        return _wrapped_view
    return decorator

def get_user_permissions(user):
    """
    Get all tronic_master permissions for a user
    """
    if not user or not user.is_authenticated:
        return []
    
    from apps.tronic_master.permission_tech import TECH_PERMISSIONS
    
    permissions = []
    for perm in TECH_PERMISSIONS.keys():
        if user.has_perm(f"tronic_master.{perm}"):
            permissions.append(perm)
    
    return permissions

def get_user_menu_items(user):
    """
    Get menu items based on user permissions
    """
    if not user or not user.is_authenticated:
        return {}
    
    # This function could be used to generate dynamic menus
    # based on permissions instead of checking in the template
    
    menu_items = {
        'dashboard': {
            'overview': user.has_perm('tronic_master.can_view_report') or user.is_super_admin or user.is_tenant_admin,
            'reports_dashboard': user.has_perm('tronic_master.can_view_report'),
            'sales_history': user.has_perm('tronic_master.can_view_sale'),
            'low_stock_alerts': user.has_perm('tronic_master.can_view_low_stock'),
            'pos': user.has_perm('tronic_master.can_create_sale') or user.has_perm('tronic_master.can_process_payment'),
        },
        'members': {
            'staff_list': user.has_perm('tronic_master.can_view_staff'),
            'manage_staff': user.has_perm('tronic_master.can_view_staff') or user.has_perm('tronic_master.can_manage_staff'),
            'add_staff': user.has_perm('tronic_master.can_add_staff'),
            'staff_attendance': user.has_perm('tronic_master.can_manage_staff'),
            'staff_leave': user.has_perm('tronic_master.can_manage_staff'),
            'role_list': user.has_perm('tronic_master.can_manage_staff'),
            'role_create': user.has_perm('tronic_master.can_manage_staff'),
            'role_assign': user.has_perm('tronic_master.can_manage_staff'),
        },
        'branches': {
            'shop_branches': user.has_perm('tronic_master.can_view_branch'),
            'add_branch': user.has_perm('tronic_master.can_add_branch'),
            'assign_manager': user.has_perm('tronic_master.can_manage_branch'),
            'branch_stock': user.has_perm('tronic_master.can_manage_branch'),
            'transfer_stock': user.has_perm('tronic_master.can_manage_branch'),
        },
        'inventory': {
            'categories': user.has_perm('tronic_master.can_view_category'),
            'manage_categories': user.has_perm('tronic_master.can_add_category') or user.has_perm('tronic_master.can_edit_category'),
            'product_list': user.has_perm('tronic_master.can_view_product'),
            'manage_products': user.has_perm('tronic_master.can_add_product') or user.has_perm('tronic_master.can_edit_product'),
            'add_product': user.has_perm('tronic_master.can_add_product'),
            'stock_report': user.has_perm('tronic_master.can_view_stock'),
            'stock_history': user.has_perm('tronic_master.can_view_stock'),
            'damaged_units': user.has_perm('tronic_master.can_view_stock'),
            'item_transfer': user.has_perm('tronic_master.can_manage_stock'),
            'assign_to_agent': user.has_perm('tronic_master.can_manage_stock'),
            'stock_management': user.has_perm('tronic_master.can_manage_stock'),
            'barcodes': user.has_perm('tronic_master.can_view_product'),
            'bulk_print': user.has_perm('tronic_master.can_view_product'),
            'import_products': user.has_perm('tronic_master.can_add_product'),
        },
        'sales': {
            'new_sale': user.has_perm('tronic_master.can_create_sale'),
            'agent_sale': user.has_perm('tronic_master.can_create_sale'),
            'sales_history': user.has_perm('tronic_master.can_view_sale'),
            'sales_search': user.has_perm('tronic_master.can_view_sale'),
            'returns': user.has_perm('tronic_master.can_view_sale'),
            'receipt_lookup': user.has_perm('tronic_master.can_view_receipt'),
        },
        'suppliers': {
            'supplier_list': user.has_perm('tronic_master.can_view_supplier'),
            'manage_suppliers': user.has_perm('tronic_master.can_add_supplier') or user.has_perm('tronic_master.can_edit_supplier'),
            'add_supplier': user.has_perm('tronic_master.can_add_supplier'),
        },
        'reports': {
            'report_dashboard': user.has_perm('tronic_master.can_view_report'),
            'sales_reports': user.has_perm('tronic_master.can_view_sale') and user.has_perm('tronic_master.can_view_report'),
            'expenses': user.has_perm('tronic_master.can_view_report'),
            'expense_report': user.has_perm('tronic_master.can_view_report'),
            'inventory_report': user.has_perm('tronic_master.can_view_report'),
            'export_reports': user.has_perm('tronic_master.can_export_report'),
        },
        'settings': {
            'receipt_settings': user.has_perm('tronic_master.can_view_settings'),
            'payment_settings': user.has_perm('tronic_master.can_view_settings'),
            'company_settings': user.has_perm('tronic_master.can_view_settings'),
        },
        'my_work': {
            'my_stock': user.has_perm('tronic_master.can_view_product'),
            'my_sales': user.has_perm('tronic_master.can_view_product'),
            'new_sale_agent': user.has_perm('tronic_master.can_view_product'),
        },
        'lookups': {
            'price_check': user.has_perm('tronic_master.can_view_product'),
            'product_search': user.has_perm('tronic_master.can_view_product'),
        },
        'company': {
            'check_plans': user.is_super_admin or user.is_tenant_admin,
        },
    }
    
    return menu_items