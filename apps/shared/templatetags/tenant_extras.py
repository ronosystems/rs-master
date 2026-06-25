# apps/shared/templatetags/tenant_extras.py
from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.simple_tag
def get_tenant_logo_url(tenant):
    """Get logo URL only if valid"""
    if tenant and hasattr(tenant, 'get_logo_url'):
        return tenant.get_logo_url()
    return None

@register.filter
def has_valid_logo(tenant):
    """Check if tenant has valid logo"""
    if tenant and hasattr(tenant, 'has_valid_logo'):
        return tenant.has_valid_logo()
    return False

@register.simple_tag
def tenant_logo_or_fallback(tenant, fallback_class='fas fa-store'):
    """Return logo HTML or fallback icon"""
    if tenant and hasattr(tenant, 'has_valid_logo') and tenant.has_valid_logo():
        url = tenant.get_logo_url()
        return f'<img src="{url}" alt="{tenant.company_name}" class="tenant-logo-img">'
    
    # Return fallback icon
    return f'<i class="{fallback_class} tenant-logo-fallback"></i>'