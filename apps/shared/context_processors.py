# apps/shared/context_processors.py

from django.conf import settings
from django.core.files.storage import default_storage
from .settings_manager import get_tenant_settings
import logging

logger = logging.getLogger(__name__)

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


def tenant_settings(request):
    """
    Make tenant settings available in all templates
    """
    context = {
        'tenant_settings': {},
        'company_settings': {},
        'receipt_settings': {},
        'payment_settings': {},
        'hotel_settings': {},
        'profile_settings': {},
        'currency_settings': {},
    }
    
    if hasattr(request, 'user') and request.user.is_authenticated:
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            try:
                settings_manager = get_tenant_settings(tenant=tenant, user=request.user)
                
                # ✅ FORCE REFRESH - clear cache before getting
                settings_manager.clear_cache()
                
                context['tenant_settings'] = settings_manager.get_all()
                context['company_settings'] = settings_manager.get_company_settings()
                context['receipt_settings'] = settings_manager.get_receipt_settings()
                context['payment_settings'] = settings_manager.get_payment_settings()
                
                # Log for debugging - shows what's actually loaded
                logger.debug(f"Company name loaded: {context['company_settings'].get('company_name')}")
                
                # Currency settings
                context['currency_settings'] = {
                    'currency': settings_manager.get('display_currency'),
                    'symbol': settings_manager.get('display_currency_symbol'),
                    'position': settings_manager.get('currency_position'),
                    'decimal_places': settings_manager.get('decimal_places'),
                    'thousand_separator': settings_manager.get('thousand_separator'),
                    'decimal_separator': settings_manager.get('decimal_separator'),
                }
                
                # Hotel settings
                hotel_keys = ['hotel_name', 'hotel_address', 'hotel_phone', 'hotel_email', 
                            'hotel_website', 'hotel_description', 'check_in_time', 
                            'check_out_time', 'tax_rate', 'service_charge']
                hotel_settings = {}
                for key in hotel_keys:
                    hotel_settings[key] = settings_manager.get(key)
                context['hotel_settings'] = hotel_settings
                
                # Profile settings
                profile_keys = ['theme', 'language', 'currency', 'date_format', 'time_format',
                              'notifications_enabled', 'email_notifications', 'sms_notifications',
                              'push_notifications', 'notify_on_sale', 'notify_on_stock']
                profile_settings = {}
                for key in profile_keys:
                    profile_settings[key] = settings_manager.get(key)
                context['profile_settings'] = profile_settings
                
            except Exception as e:
                logger.error(f"Error loading tenant settings: {e}")
    
    return context