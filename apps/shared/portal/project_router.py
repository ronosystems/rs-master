# apps/shared/portal/project_router.py

from django.shortcuts import redirect
from django.urls import reverse

PROJECT_URLS = {
    'TECH_MASTER': {
        'dashboard': 'tech_master:dashboard',
        'pos': 'tech_master:pos',
        'login_redirect': 'tech_master:dashboard',
    },
    'HOTEL_MASTER': {
        'dashboard': 'hotel_master:dashboard',
        'pos': 'hotel_master:pos',
        'login_redirect': 'hotel_master:dashboard',
    },
    'FOOD_MASTER': {
        'dashboard': 'food_master:dashboard',
        'pos': 'food_master:pos',
        'login_redirect': 'food_master:dashboard',
    },
    'RETAIL_MASTER': {
        'dashboard': 'retail_master:dashboard',
        'pos': 'retail_master:pos',
        'login_redirect': 'retail_master:dashboard',
    },
    'HEALTH_MASTER': {
        'dashboard': 'health_master:dashboard',
        'pos': 'health_master:pos',
        'login_redirect': 'health_master:dashboard',
    },
    'FASHION_MASTER': {
        'dashboard': 'fashion_master:dashboard',
        'pos': 'fashion_master:pos',
        'login_redirect': 'fashion_master:dashboard',
    },
}

# ✅ Default fallback
DEFAULT_PROJECT = 'TECH_MASTER'
DEFAULT_REDIRECT = 'tech_master:dashboard'

def get_project_redirect(project_code: str, redirect_type: str = 'dashboard') -> str:
    """
    Get the redirect URL for a project.
    Always returns a string, never None.
    """
    if not project_code:
        return DEFAULT_REDIRECT
    
    project_config = PROJECT_URLS.get(project_code.upper())
    if not project_config:
        return DEFAULT_REDIRECT
    
    url_name = project_config.get(redirect_type)
    if not url_name:
        # Fallback to login_redirect or dashboard
        url_name = project_config.get('login_redirect') or project_config.get('dashboard')
    
    if not url_name:
        return DEFAULT_REDIRECT
    
    return url_name


def redirect_to_project_dashboard(project_code: str):
    """Redirect to the correct project dashboard"""
    url_name = get_project_redirect(project_code, 'dashboard')
    return redirect(url_name)