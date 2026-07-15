# apps/shared/utils/project_helpers.py

from django.shortcuts import redirect
from django.conf import settings

# ============================================
# PROJECT TEMPLATE MAPPING
# ============================================

PROJECT_TEMPLATE_DIRS = {
    'TRONIC_MASTER': 'tronic_master',
    'HOTEL_MASTER': 'hotel_master',
    'FOOD_MASTER': 'food_master',
    'RETAIL_MASTER': 'retail_master',
    'HEALTH_MASTER': 'health_master',
    'FASHION_MASTER': 'fashion_master',
}

# ============================================
# PROJECT ROLE MAPPINGS - ✅ ADD THIS
# ============================================

PROJECT_ROLE_MAPPINGS = {
    'TRONIC_MASTER': {
        'cashier': 'tronic_master:pos',
        'sales_agent': 'tronic_master:my_sales',
        'manager': 'tronic_master:dashboard',
        'admin': 'tronic_master:dashboard',
        'tenant_admin': 'tronic_master:dashboard',
        'default': 'tronic_master:dashboard',
    },
    'HOTEL_MASTER': {
        'cashier': 'hotel_master:pos',
        'receptionist': 'hotel_master:reception',
        'manager': 'hotel_master:dashboard',
        'admin': 'hotel_master:dashboard',
        'tenant_admin': 'hotel_master:dashboard',
        'default': 'hotel_master:dashboard',
    },
    'FOOD_MASTER': {
        'cashier': 'food_master:pos',
        'waiter': 'food_master:orders',
        'kitchen': 'food_master:kitchen',
        'manager': 'food_master:dashboard',
        'admin': 'food_master:dashboard',
        'tenant_admin': 'food_master:dashboard',
        'default': 'food_master:dashboard',
    },
    'RETAIL_MASTER': {
        'cashier': 'retail_master:pos',
        'sales_agent': 'retail_master:my_sales',
        'manager': 'retail_master:dashboard',
        'admin': 'retail_master:dashboard',
        'tenant_admin': 'retail_master:dashboard',
        'default': 'retail_master:dashboard',
    },
    'HEALTH_MASTER': {
        'cashier': 'health_master:pos',
        'pharmacist': 'health_master:pharmacy',
        'nurse': 'health_master:nurse',
        'doctor': 'health_master:doctor',
        'manager': 'health_master:dashboard',
        'admin': 'health_master:dashboard',
        'tenant_admin': 'health_master:dashboard',
        'default': 'health_master:dashboard',
    },
    'FASHION_MASTER': {
        'cashier': 'fashion_master:pos',
        'sales_agent': 'fashion_master:my_sales',
        'manager': 'fashion_master:dashboard',
        'admin': 'fashion_master:dashboard',
        'tenant_admin': 'fashion_master:dashboard',
        'default': 'fashion_master:dashboard',
    },
}

# ============================================
# PROJECT DASHBOARD MAPPING
# ============================================

PROJECT_DASHBOARDS = {
    'TRONIC_MASTER': 'tronic_master:dashboard',
    'HOTEL_MASTER': 'hotel_master:dashboard',
    'FOOD_MASTER': 'food_master:dashboard',
    'RETAIL_MASTER': 'retail_master:dashboard',
    'HEALTH_MASTER': 'health_master:dashboard',
    'FASHION_MASTER': 'fashion_master:dashboard',
}

PROJECT_NAMES = {
    'TRONIC_MASTER': 'Tech Master',
    'HOTEL_MASTER': 'Hotel Master',
    'FOOD_MASTER': 'Food Master',
    'RETAIL_MASTER': 'Retail Master',
    'HEALTH_MASTER': 'Health Master',
    'FASHION_MASTER': 'Fashion Master',
}

PROJECT_ICONS = {
    'TRONIC_MASTER': 'fa-microchip',
    'HOTEL_MASTER': 'fa-hotel',
    'FOOD_MASTER': 'fa-utensils',
    'RETAIL_MASTER': 'fa-store',
    'HEALTH_MASTER': 'fa-heartbeat',
    'FASHION_MASTER': 'fa-tshirt',
}


def is_project_active(project_code):
    """Check if a project is active in settings"""
    project_types = getattr(settings, 'PROJECT_TYPES', {})
    return project_types.get(project_code, {}).get('active', False)


def get_project_template_dir(project_code):
    """Get the template directory for a project"""
    return PROJECT_TEMPLATE_DIRS.get(project_code, 'tronic_master')


def get_project_dashboard_url(project_code):
    """Get the dashboard URL for a project"""
    return PROJECT_DASHBOARDS.get(project_code, 'tronic_master:dashboard')


def get_project_name(project_code):
    """Get the display name for a project"""
    return PROJECT_NAMES.get(project_code, 'Tech Master')


def get_project_icon(project_code):
    """Get the icon for a project"""
    return PROJECT_ICONS.get(project_code, 'fa-building')


def get_project_context(tenant):
    """Get project context for templates"""
    if not tenant:
        return {
            'project_code': 'TRONIC_MASTER',
            'project_name': 'Tech Master',
            'project_icon': 'fa-microchip',
            'project_template_dir': 'tronic_master',
        }
    
    project_type = getattr(tenant, 'project_type', None)
    if not project_type:
        return {
            'project_code': 'TRONIC_MASTER',
            'project_name': 'Tech Master',
            'project_icon': 'fa-microchip',
            'project_template_dir': 'tronic_master',
        }
    
    code = project_type.code.upper()
    return {
        'project_code': code,
        'project_name': get_project_name(code),
        'project_icon': get_project_icon(code),
        'project_template_dir': get_project_template_dir(code),
    }


def redirect_project_dashboard(tenant):
    """Redirect to the appropriate project dashboard"""
    if not tenant:
        return redirect('tronic_master:dashboard')
    
    project_type = getattr(tenant, 'project_type', None)
    if not project_type:
        return redirect('tronic_master:dashboard')
    
    code = project_type.code.upper()
    
    # Check if project is active
    if not is_project_active(code):
        return redirect('tronic_master:dashboard')
    
    return redirect(PROJECT_DASHBOARDS.get(code, 'tronic_master:dashboard'))



from apps.shared.portal.project_router import get_project_redirect, DEFAULT_REDIRECT

def redirect_project_role(request):
    """Redirect based on user role and tenant project type"""
    user = request.user
    tenant = getattr(user, 'tenant', None)
    
    if not tenant:
        return redirect(DEFAULT_REDIRECT)
    
    project_type = getattr(tenant, 'project_type', None)
    if not project_type:
        return redirect(DEFAULT_REDIRECT)
    
    project_code = project_type.code.upper()
    
    # Check if project is active
    if not is_project_active(project_code):
        return redirect(DEFAULT_REDIRECT)
    
    user_role = user.role
    
    # Get role-based redirect
    project_config = PROJECT_ROLE_MAPPINGS.get(project_code, {})
    redirect_url = project_config.get(user_role) or project_config.get('default')
    
    # ✅ Ensure we have a valid URL
    if not redirect_url:
        redirect_url = get_project_redirect(project_code, 'dashboard')
    
    return redirect(redirect_url)