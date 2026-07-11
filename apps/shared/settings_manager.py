from django.core.cache import cache
from django.apps import apps
from django.conf import settings as django_settings
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def get_setting_model(model_name):
    """Get a setting model using Django's app registry"""
    try:
        # Try to get from 'settings' app first
        return apps.get_model('settings', model_name)
    except LookupError:
        try:
            # Fallback to 'tenants' app
            return apps.get_model('tenants', model_name)
        except LookupError:
            try:
                # Try 'shared.settings'
                return apps.get_model('shared.settings', model_name)
            except LookupError:
                logger.warning(f"Model {model_name} not found in app registry")
                return None


class SettingsManager:
    """
    Unified settings manager that handles tenant-specific and system-wide settings
    with proper priority: Tenant Settings > System Settings > Defaults
    """
    
    DEFAULTS = {
        # Company settings
        'company_name': '',
        'company_address': '',
        'company_phone': '',
        'company_email': '',
        'company_website': '',
        'company_tax_pin': '',
        'primary_color': '#0d6efd',
        'secondary_color': '#6c757d',
        'accent_color': '#ffc107',
        'show_logo_on_receipts': True,
        'show_logo_on_invoices': True,
        'show_logo_on_reports': True,
        'show_logo_on_dashboard': True,
        
        # Receipt settings
        'business_name': '',
        'business_address': '',
        'business_phone': '',
        'business_email': '',
        'business_tax_pin': '',
        'show_business_name': True,
        'show_address': True,
        'show_phone': True,
        'show_email': True,
        'show_tax_pin': True,
        'show_receipt_number': True,
        'show_sale_date': True,
        'show_sale_time': True,
        'show_agent_user': True,
        'show_buyer_name': True,
        'show_buyer_phone': True,
        'show_buyer_id': True,
        'show_next_of_kin_name': True,
        'show_next_of_kin_phone': True,
        'show_items_table': True,
        'show_imei': True,
        'show_quantity': True,
        'show_unit_price': True,
        'show_line_total': True,
        'show_gross_total': True,
        'show_footer_message': True,
        'footer_text': 'Thank you for your business!',
        'show_vat_on_receipt': False,
        'vat_rate': Decimal('16.00'),
        'vat_label': 'VAT',
        'tax_type': 'exclusive',
        
        # Payment settings
        'enable_cash': True,
        'enable_mpesa': True,
        'enable_card': False,
        'enable_bank_transfer': False,
        'enable_credit': False,
        'display_currency': 'KES',
        'display_currency_symbol': 'KSh',
        'currency_position': 'before',
        'decimal_places': 2,
        'thousand_separator': ',',
        'decimal_separator': '.',
        'enable_tax': False,
        'tax_percentage': Decimal('16.00'),
        'tax_inclusive': True,
        'tax_label': 'VAT',
        'till_number': '',
        'paybill_number': '',
        'account_number': '',
        'show_till_number': True,
        'show_paybill': True,
        'show_account_number': True,
        'show_payment_details_on_receipt': True,
        'min_cash_payment': Decimal('0.00'),
        'min_mpesa_payment': Decimal('0.00'),
        'enable_partial_payment': False,
        'enable_deposit_payment': False,
        'deposit_percentage': Decimal('0.00'),
        'credit_limit_enabled': False,
        'credit_limit_amount': Decimal('0.00'),
        'credit_days_allowed': 30,
        'credit_interest_rate': Decimal('0.00'),
        'credit_fee_percentage': Decimal('0.00'),
        'mpesa_environment': 'sandbox',
        'card_payment_gateway': '',
        'require_payment_confirmation': True,
        'require_payment_receipt': False,
        'send_payment_receipt_email': True,
        'send_payment_receipt_sms': False,
        'payment_footer_text': '',
        'show_payment_instructions': True,
        'payment_instructions': '',
        
        # Profile defaults
        'theme': 'light',
        'language': 'en',
        'currency': 'KES',
        'date_format': 'Y-m-d',
        'time_format': 'H:i',
        'notifications_enabled': True,
        'email_notifications': True,
        'sms_notifications': True,
        'push_notifications': True,
        'notify_on_sale': True,
        'notify_on_stock': True,
        
        # Hotel defaults
        'hotel_name': '',
        'hotel_address': '',
        'hotel_phone': '',
        'hotel_email': '',
        'hotel_website': '',
        'hotel_description': '',
        'check_in_time': '14:00',
        'check_out_time': '11:00',
        'tax_rate': Decimal('0.00'),
        'service_charge': Decimal('0.00'),
    }
    
    def __init__(self, tenant=None, user=None):
        self.tenant = tenant
        self.user = user
        self._cache_key = f"settings_{tenant.id if tenant else 'system'}_{user.id if user else 'global'}"
        self._cache = {}
    
    def get(self, key, default=None, use_cache=True):
        """Get a setting value with priority: Tenant > System > Default"""
        if use_cache and key in self._cache:
            return self._cache[key]
        
        value = None
        
        if self.tenant:
            value = self._get_tenant_setting(key)
        
        if value is None:
            value = self._get_system_setting(key)
        
        if value is None:
            value = default if default is not None else self.DEFAULTS.get(key)
        
        if use_cache:
            self._cache[key] = value
        
        return value
    
    def _get_tenant_setting(self, key):
        """Get tenant-specific setting value"""
        # Get models from the 'settings' app
        CompanySetting = get_setting_model('CompanySetting')
        ReceiptSetting = get_setting_model('ReceiptSetting')
        PaymentSetting = get_setting_model('PaymentSetting')
        HotelSetting = get_setting_model('HotelSetting')
        ProfileSetting = get_setting_model('ProfileSetting')
        
        # Try CompanySetting
        if CompanySetting:
            try:
                instance = CompanySetting.objects.get(tenant=self.tenant)
                if hasattr(instance, key):
                    return getattr(instance, key)
            except CompanySetting.DoesNotExist:
                pass
            except Exception:
                pass
        
        # Try ReceiptSetting
        if ReceiptSetting:
            try:
                instance = ReceiptSetting.objects.get(tenant=self.tenant)
                if hasattr(instance, key):
                    return getattr(instance, key)
            except ReceiptSetting.DoesNotExist:
                pass
            except Exception:
                pass
        
        # Try PaymentSetting
        if PaymentSetting:
            try:
                instance = PaymentSetting.objects.get(tenant=self.tenant)
                if hasattr(instance, key):
                    return getattr(instance, key)
            except PaymentSetting.DoesNotExist:
                pass
            except Exception:
                pass
        
        # Try HotelSetting
        if HotelSetting:
            try:
                instance = HotelSetting.objects.get(tenant=self.tenant)
                if hasattr(instance, key):
                    return getattr(instance, key)
            except HotelSetting.DoesNotExist:
                pass
            except Exception:
                pass
        
        # Try ProfileSetting (if user is provided)
        if self.user and ProfileSetting:
            try:
                instance = ProfileSetting.objects.get(user=self.user)
                if hasattr(instance, key):
                    return getattr(instance, key)
            except ProfileSetting.DoesNotExist:
                pass
            except Exception:
                pass
        
        return None
    
    def _get_system_setting(self, key):
        """Get system-wide setting from SystemSetting model"""
        SystemSetting = get_setting_model('SystemSetting')
        
        if not SystemSetting:
            return None
        
        try:
            instance = SystemSetting.objects.get(key=key)
            return instance.value
        except SystemSetting.DoesNotExist:
            return None
        except Exception:
            return None
    
    def get_all(self, prefix=None):
        """Get all settings, optionally filtered by prefix"""
        settings = {}
        for key in self.DEFAULTS:
            if prefix and not key.startswith(prefix):
                continue
            settings[key] = self.get(key)
        return settings
    
    def get_company_settings(self):
        """Get all company-related settings"""
        return self.get_all(prefix='company_')
    
    def get_receipt_settings(self):
        """Get all receipt-related settings"""
        receipt_keys = [
            'business_name', 'business_address', 'business_phone', 'business_email', 'business_tax_pin',
            'show_business_name', 'show_address', 'show_phone', 'show_email', 'show_tax_pin',
            'show_receipt_number', 'show_sale_date', 'show_sale_time', 'show_agent_user',
            'show_buyer_name', 'show_buyer_phone', 'show_buyer_id',
            'show_next_of_kin_name', 'show_next_of_kin_phone',
            'show_items_table', 'show_imei', 'show_quantity', 'show_unit_price',
            'show_line_total', 'show_gross_total',
            'show_footer_message', 'footer_text',
            'show_vat_on_receipt', 'vat_rate', 'vat_label', 'tax_type'
        ]
        settings = {}
        for key in receipt_keys:
            settings[key] = self.get(key)
        return settings
    
    def get_payment_settings(self):
        """Get all payment-related settings"""
        payment_keys = [
            'enable_cash', 'enable_mpesa', 'enable_card', 'enable_bank_transfer', 'enable_credit',
            'till_number', 'paybill_number', 'account_number',
            'show_till_number', 'show_paybill', 'show_account_number', 'show_payment_details_on_receipt',
            'display_currency', 'display_currency_symbol', 'currency_position',
            'decimal_places', 'thousand_separator', 'decimal_separator',
            'enable_tax', 'tax_percentage', 'tax_inclusive', 'tax_label',
            'min_cash_payment', 'min_mpesa_payment', 'enable_partial_payment',
            'enable_deposit_payment', 'deposit_percentage',
            'credit_limit_enabled', 'credit_limit_amount', 'credit_days_allowed',
            'credit_interest_rate', 'credit_fee_percentage',
            'require_payment_confirmation', 'require_payment_receipt',
            'send_payment_receipt_email', 'send_payment_receipt_sms',
            'payment_footer_text', 'show_payment_instructions', 'payment_instructions'
        ]
        settings = {}
        for key in payment_keys:
            settings[key] = self.get(key)
        return settings
    
    def clear_cache(self):
        """Clear the settings cache"""
        cache.delete(self._cache_key)
        self._cache = {}
    
    def refresh(self):
        """Refresh all settings from database"""
        self.clear_cache()
        return self.get_all()


# Convenience functions
def get_tenant_settings(tenant, user=None):
    """Get settings manager for a specific tenant"""
    return SettingsManager(tenant=tenant, user=user)


def get_setting(key, tenant=None, user=None, default=None):
    """Get a single setting value"""
    manager = SettingsManager(tenant=tenant, user=user)
    return manager.get(key, default)
