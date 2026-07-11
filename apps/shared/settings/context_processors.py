# apps/shared/settings/context_processors.py

from .models import CompanySetting

def company_settings(request):
    """Add company settings to template context"""
    context = {}
    
    if request.user.is_authenticated and hasattr(request.user, 'tenant'):
        tenant = request.user.tenant
        if tenant:
            try:
                company_settings = CompanySetting.objects.get(tenant=tenant)
                context['company_settings'] = company_settings
            except CompanySetting.DoesNotExist:
                pass
    
    return context