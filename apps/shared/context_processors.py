# apps/shared/context_processors.py
from django.conf import settings
from django.core.files.storage import default_storage

def tenant_logo_context(request):
    """Add tenant logo info to all templates"""
    context = {
        'tenant_has_valid_logo': False,
        'tenant_logo_url': None,
    }
    
    if hasattr(request, 'tenant'):
        tenant = request.tenant
        if tenant and tenant.logo:
            try:
                if tenant.logo.name and default_storage.exists(tenant.logo.name):
                    context['tenant_has_valid_logo'] = True
                    context['tenant_logo_url'] = tenant.logo.url
            except Exception:
                pass
    
    return context

def offline_mode(request):
    """Add offline mode to template context"""
    return {
        'offline_mode': getattr(settings, 'OFFLINE_MODE', False),
        'is_online': not getattr(settings, 'OFFLINE_MODE', False),
    }