# apps/shared/settings/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password
from django.db import transaction
from decimal import Decimal
from .models import CompanySetting
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from .models import ReceiptSetting, ProfileSetting, SystemSetting
from apps.shared.users.models import User
from apps.shared.tenants.models import Tenant
from django.core.exceptions import PermissionDenied
from apps.shared.settings.models import (
    SystemSetting, 
    ReceiptSetting, 
    ProfileSetting, 
    PaymentSetting
)
import logging
import json

logger = logging.getLogger(__name__)


# ============================================
# SYSTEM SETTINGS - SUPER ADMIN ONLY
# ============================================

@staff_member_required
def system_settings(request):
    """
    System settings view for Super Admin only.
    Manage global platform settings.
    """
    
    # Get all system settings
    settings_dict = {}
    for setting in SystemSetting.objects.all():
        settings_dict[setting.key] = setting.value
    
    # Get platform stats for context
    total_tenants = Tenant.objects.count()
    active_tenants = Tenant.objects.filter(status='active').count()
    pending_tenants = Tenant.objects.filter(status='pending').count()
    
    context = {
        'settings': settings_dict,
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'pending_tenants': pending_tenants,
        'is_super_admin': request.user.is_superuser,
    }
    
    return render(request, 'shared/settings/system_settings.html', context)


@staff_member_required
@transaction.atomic
def update_system_settings(request):
    """
    Update system settings via POST request.
    """
    if request.method != 'POST':
        return redirect('settings:system_settings')
    
    try:
        # Platform Settings
        SystemSetting.set('platform_name', request.POST.get('platform_name', 'Tech Master Platform'))
        SystemSetting.set('platform_description', request.POST.get('platform_description', ''))
        
        # Company Settings
        SystemSetting.set('company_name', request.POST.get('company_name', 'Tech Master'))
        SystemSetting.set('company_address', request.POST.get('company_address', ''))
        SystemSetting.set('company_phone', request.POST.get('company_phone', ''))
        SystemSetting.set('company_email', request.POST.get('company_email', ''))
        
        # Security Settings
        SystemSetting.set('max_login_attempts', request.POST.get('max_login_attempts', '5'))
        SystemSetting.set('session_timeout_minutes', request.POST.get('session_timeout_minutes', '60'))
        SystemSetting.set('force_ssl', request.POST.get('force_ssl', 'False'))
        
        # Feature Toggles
        SystemSetting.set('allow_tenant_registration', request.POST.get('allow_tenant_registration', 'True'))
        SystemSetting.set('require_email_verification', request.POST.get('require_email_verification', 'True'))
        SystemSetting.set('maintenance_mode', request.POST.get('maintenance_mode', 'False'))
        
        # Notification Settings
        SystemSetting.set('admin_notification_email', request.POST.get('admin_notification_email', ''))
        SystemSetting.set('send_welcome_emails', request.POST.get('send_welcome_emails', 'True'))
        
        # Clear cache
        cache.delete('system_settings')
        
        messages.success(request, '✅ System settings updated successfully!')
        
    except Exception as e:
        messages.error(request, f'❌ Error updating settings: {str(e)}')
        logger.error(f"System settings update error: {e}")
    
    return redirect('settings:system_settings')


@staff_member_required
def system_settings_export(request):
    """
    Export system settings as JSON.
    """
    settings_dict = {}
    for setting in SystemSetting.objects.all():
        settings_dict[setting.key] = setting.value
    
    return JsonResponse({
        'status': 'success',
        'settings': settings_dict,
        'exported_at': timezone.now().isoformat()
    })


# ============================================
# RECEIPT SETTINGS - TENANT ADMIN ONLY
# ============================================


@login_required
def receipt_settings(request):
    """Receipt settings view"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    # Get or create receipt settings
    settings, created = ReceiptSetting.objects.get_or_create(tenant=tenant)
    
    if request.method == 'POST':
        # Business Details
        settings.business_name = request.POST.get('business_name', '')
        settings.business_address = request.POST.get('business_address', '')
        settings.business_phone = request.POST.get('business_phone', '')
        settings.business_email = request.POST.get('business_email', '')
        settings.business_tax_pin = request.POST.get('business_tax_pin', '')
        
        # ============================================
        # HANDLE LOGO UPLOAD
        # ============================================
        if request.FILES.get('logo'):
            settings.logo = request.FILES['logo']
        
        # ============================================
        # LOGO TOGGLE
        # ============================================
        settings.show_logo_on_receipts = request.POST.get('show_logo_on_receipts') == 'on'
        
        # Business Header Toggles
        settings.show_business_name = request.POST.get('show_business_name') == 'on'
        settings.show_address = request.POST.get('show_address') == 'on'
        settings.show_phone = request.POST.get('show_phone') == 'on'
        settings.show_email = request.POST.get('show_email') == 'on'
        settings.show_tax_pin = request.POST.get('show_tax_pin') == 'on'
        
        # Receipt Details Toggles
        settings.show_receipt_number = request.POST.get('show_receipt_number') == 'on'
        settings.show_sale_date = request.POST.get('show_sale_date') == 'on'
        settings.show_sale_time = request.POST.get('show_sale_time') == 'on'
        settings.show_agent_user = request.POST.get('show_agent_user') == 'on'
        
        # Buyer Information Toggles
        settings.show_buyer_name = request.POST.get('show_buyer_name') == 'on'
        settings.show_buyer_phone = request.POST.get('show_buyer_phone') == 'on'
        settings.show_buyer_id = request.POST.get('show_buyer_id') == 'on'
        settings.show_next_of_kin_name = request.POST.get('show_next_of_kin_name') == 'on'
        settings.show_next_of_kin_phone = request.POST.get('show_next_of_kin_phone') == 'on'
        
        # Line Items Toggles
        settings.show_items_table = request.POST.get('show_items_table') == 'on'
        settings.show_imei = request.POST.get('show_imei') == 'on'
        settings.show_quantity = request.POST.get('show_quantity') == 'on'
        settings.show_unit_price = request.POST.get('show_unit_price') == 'on'
        settings.show_line_total = request.POST.get('show_line_total') == 'on'
        settings.show_gross_total = request.POST.get('show_gross_total') == 'on'
        
        # Footer
        settings.show_footer_message = request.POST.get('show_footer_message') == 'on'
        settings.footer_text = request.POST.get('footer_text', 'Thank you for your business!')
        
        # ============================================
        # VAT / TAX SETTINGS - NEW
        # ============================================
        settings.show_vat_on_receipt = request.POST.get('show_vat_on_receipt') == 'on'
        
        # VAT Rate - Convert to Decimal safely
        vat_rate = request.POST.get('vat_rate', 16)
        try:
            settings.vat_rate = Decimal(str(vat_rate))
        except (ValueError, TypeError):
            settings.vat_rate = Decimal('16.00')
        
        # VAT Label
        settings.vat_label = request.POST.get('vat_label', 'VAT')
        
        # Tax Type
        settings.tax_type = request.POST.get('tax_type', 'exclusive')
        
        settings.save()
        
        messages.success(request, 'Receipt settings updated successfully!')
        return redirect('settings:receipt_settings')
    
    context = {
        'settings': settings,
        'tenant': tenant,
    }
    return render(request, 'shared/settings/receipt_settings.html', context)



# ============================================
# PROFILE SETTINGS - ALL USERS
# ============================================

@login_required
def profile_settings(request):
    """Profile settings view"""
    user = request.user
    settings, created = ProfileSetting.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        # ============================================
        # UPDATE PERSONAL INFO
        # ============================================
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone_number = request.POST.get('phone_number', user.phone_number)
        
        # ============================================
        # UPDATE USERNAME (with validation)
        # ============================================
        new_username = request.POST.get('username', '').strip()
        if new_username and new_username != user.username:
            if User.objects.filter(username=new_username).exists():
                messages.error(request, f'Username "{new_username}" is already taken.')
            else:
                user.username = new_username
                messages.success(request, 'Username updated successfully!')
        
        # ============================================
        # CHANGE PASSWORD
        # ============================================
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if current_password and new_password:
            # Check current password
            if not check_password(current_password, user.password):
                messages.error(request, 'Current password is incorrect.')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
            elif len(new_password) < 6:
                messages.error(request, 'Password must be at least 6 characters long.')
            else:
                user.set_password(new_password)
                # ✅ Don't save yet - save after all updates
                messages.success(request, 'Password changed successfully!')
        
        # ============================================
        # UPDATE PIN
        # ============================================
        current_pin = request.POST.get('current_pin')
        new_pin = request.POST.get('new_pin')
        
        if current_pin and new_pin:
            if user.pin_code and current_pin != user.pin_code:
                messages.error(request, 'Current PIN is incorrect.')
            elif not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 6:
                messages.error(request, 'PIN must be 4-6 digits.')
            else:
                user.pin_code = new_pin
                messages.success(request, 'PIN updated successfully!')
        
        # ============================================
        # UPDATE PROFILE SETTINGS
        # ============================================
        settings.theme = request.POST.get('theme', settings.theme)
        settings.language = request.POST.get('language', settings.language)
        settings.currency = request.POST.get('currency', settings.currency)
        settings.date_format = request.POST.get('date_format', settings.date_format)
        settings.time_format = request.POST.get('time_format', settings.time_format)
        settings.notifications_enabled = request.POST.get('notifications_enabled') == 'on'
        settings.email_notifications = request.POST.get('email_notifications') == 'on'
        
        # ✅ Only update optional fields if they exist in the model
        optional_fields = ['sms_notifications', 'push_notifications', 'notify_on_sale', 'notify_on_stock']
        for field in optional_fields:
            if hasattr(settings, field):
                setattr(settings, field, request.POST.get(field) == 'on')
        
        # ✅ Save all changes
        user.save()
        settings.save()
        
        # ✅ Keep the user logged in after password change
        update_session_auth_hash(request, user)
        
        messages.success(request, 'Profile settings updated successfully!')
        return redirect('settings:profile_settings')
    
    # Available options
    themes = [
        {'value': 'light', 'label': 'Light'},
        {'value': 'dark', 'label': 'Dark'},
        {'value': 'auto', 'label': 'Auto (System Default)'},
    ]
    
    languages = [
        {'value': 'en', 'label': 'English'},
        {'value': 'sw', 'label': 'Swahili'},
        {'value': 'fr', 'label': 'French'},
        {'value': 'es', 'label': 'Spanish'},
    ]
    
    currencies = [
        {'value': 'KES', 'label': 'Kenyan Shilling (KES)'},
        {'value': 'USD', 'label': 'US Dollar (USD)'},
        {'value': 'EUR', 'label': 'Euro (EUR)'},
        {'value': 'GBP', 'label': 'British Pound (GBP)'},
        {'value': 'UGX', 'label': 'Ugandan Shilling (UGX)'},
        {'value': 'TZS', 'label': 'Tanzanian Shilling (TZS)'},
    ]
    
    date_formats = [
        {'value': 'YYYY-MM-DD', 'label': '2024-01-15'},
        {'value': 'DD/MM/YYYY', 'label': '15/01/2024'},
        {'value': 'MM/DD/YYYY', 'label': '01/15/2024'},
        {'value': 'DD MMM YYYY', 'label': '15 Jan 2024'},
        {'value': 'MMMM DD, YYYY', 'label': 'January 15, 2024'},
    ]
    
    time_formats = [
        {'value': 'HH:mm', 'label': '14:30 (24-hour)'},
        {'value': 'hh:mm A', 'label': '02:30 PM (12-hour)'},
        {'value': 'hh:mm:ss A', 'label': '02:30:45 PM'},
    ]
    
    context = {
        'settings': settings,
        'themes': themes,
        'languages': languages,
        'currencies': currencies,
        'date_formats': date_formats,
        'time_formats': time_formats,
        'user': user,
        'tenant': request.user.tenant,
    }
    return render(request, 'shared/settings/profile_settings.html', context)


# apps/shared/settings/views.py - Add this if not exists

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.hashers import check_password


@login_required
def change_pin(request):
    """Change user's PIN"""
    user = request.user
    
    if request.method == 'POST':
        current_pin = request.POST.get('current_pin', '').strip()
        new_pin = request.POST.get('new_pin', '').strip()
        confirm_pin = request.POST.get('confirm_pin', '').strip()
        
        # Validate current PIN
        if user.pin_code and not user.check_pin(current_pin):
            messages.error(request, 'Current PIN is incorrect.')
            return redirect('settings:change_pin')
        
        # Validate new PIN
        if len(new_pin) < 4 or len(new_pin) > 6 or not new_pin.isdigit():
            messages.error(request, 'New PIN must be 4-6 digits (numbers only).')
            return redirect('settings:change_pin')
        
        if new_pin != confirm_pin:
            messages.error(request, 'PINs do not match.')
            return redirect('settings:change_pin')
        
        # Set new PIN
        user.pin_code = new_pin
        user.save()
        
        # Log activity
        from apps.shared.users.models import UserActivityLog
        UserActivityLog.log_activity(
            user=user,
            action='pin_change',
            details={'pin_changed': True},
            request=request
        )
        
        messages.success(request, 'PIN changed successfully!')
        return redirect('settings:profile_settings')
    
    context = {
        'user': user,
        'has_pin': user.has_pin(),
        'active_tab': 'security',
    }
    return render(request, 'shared/settings/change_pin.html', context)


# ============ PAYMENT SETTINGS VIEWS ============

@login_required
def payment_settings_view(request):
    """Render payment settings page"""
    tenant = request.user.tenant
    if not tenant:
        raise PermissionDenied("No tenant associated with user")
    
    # Get or create payment settings
    payment_settings, created = PaymentSetting.objects.get_or_create(tenant=tenant)
    
    context = {
        'payment_settings': payment_settings,
        'tenant': tenant,
    }
    return render(request, 'shared/settings/payment_settings.html', context)


@login_required
def api_payment_settings(request):
    """Get payment settings as JSON"""
    tenant = request.user.tenant
    if not tenant:
        return JsonResponse({'error': 'No tenant associated'}, status=403)
    
    try:
        payment_settings = PaymentSetting.objects.get(tenant=tenant)
        data = {
            'id': payment_settings.id,
            'tenant_id': payment_settings.tenant_id,
            'enable_cash': payment_settings.enable_cash,
            'enable_mpesa': payment_settings.enable_mpesa,
            'enable_card': payment_settings.enable_card,
            'enable_bank_transfer': payment_settings.enable_bank_transfer,
            'enable_credit': payment_settings.enable_credit,
            'mpesa_shortcode': payment_settings.mpesa_shortcode,
            'mpesa_consumer_key': payment_settings.mpesa_consumer_key,
            'mpesa_consumer_secret': payment_settings.mpesa_consumer_secret,
            'mpesa_passkey': payment_settings.mpesa_passkey,
            'mpesa_environment': payment_settings.mpesa_environment,
            'card_payment_gateway': payment_settings.card_payment_gateway,
            'card_public_key': payment_settings.card_public_key,
            'card_secret_key': payment_settings.card_secret_key,
            'card_webhook_secret': payment_settings.card_webhook_secret,

            # ============================================
            # RECEIPT PAYMENT DETAILS - ADD THESE
            # ============================================
            'till_number': payment_settings.till_number or '',
            'paybill_number': payment_settings.paybill_number or '',
            'account_number': payment_settings.account_number or '',
            'show_till_number': payment_settings.show_till_number,
            'show_paybill': payment_settings.show_paybill,
            'show_account_number': payment_settings.show_account_number,
            'show_payment_details_on_receipt': payment_settings.show_payment_details_on_receipt,
            

            'bank_name': payment_settings.bank_name,
            'bank_account_name': payment_settings.bank_account_name,
            'bank_account_number': payment_settings.bank_account_number,
            'bank_branch': payment_settings.bank_branch,
            'bank_swift_code': payment_settings.bank_swift_code,
            'credit_limit_enabled': payment_settings.credit_limit_enabled,
            'credit_limit_amount': str(payment_settings.credit_limit_amount),
            'credit_days_allowed': payment_settings.credit_days_allowed,
            'credit_interest_rate': str(payment_settings.credit_interest_rate),
            'credit_fee_percentage': str(payment_settings.credit_fee_percentage),
            'require_payment_confirmation': payment_settings.require_payment_confirmation,
            'require_payment_receipt': payment_settings.require_payment_receipt,
            'send_payment_receipt_email': payment_settings.send_payment_receipt_email,
            'send_payment_receipt_sms': payment_settings.send_payment_receipt_sms,
            'max_cash_payment': str(payment_settings.max_cash_payment) if payment_settings.max_cash_payment else None,
            'min_cash_payment': str(payment_settings.min_cash_payment),
            'max_mpesa_payment': str(payment_settings.max_mpesa_payment) if payment_settings.max_mpesa_payment else None,
            'min_mpesa_payment': str(payment_settings.min_mpesa_payment),
            'enable_partial_payment': payment_settings.enable_partial_payment,
            'enable_deposit_payment': payment_settings.enable_deposit_payment,
            'deposit_percentage': str(payment_settings.deposit_percentage),
            'display_currency': payment_settings.display_currency,
            'display_currency_symbol': payment_settings.display_currency_symbol,
            'currency_position': payment_settings.currency_position,
            'decimal_places': payment_settings.decimal_places,
            'thousand_separator': payment_settings.thousand_separator,
            'decimal_separator': payment_settings.decimal_separator,
            'enable_tax': payment_settings.enable_tax,
            'tax_percentage': str(payment_settings.tax_percentage),
            'tax_inclusive': payment_settings.tax_inclusive,
            'tax_label': payment_settings.tax_label,
            'payment_footer_text': payment_settings.payment_footer_text,
            'show_payment_instructions': payment_settings.show_payment_instructions,
            'payment_instructions': payment_settings.payment_instructions,
            'enabled_payment_methods': payment_settings.get_enabled_payment_methods(),
        }
        return JsonResponse(data)
    except PaymentSetting.DoesNotExist:
        return JsonResponse({'error': 'Payment settings not found'}, status=404)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_update_payment_settings(request):
    """Update payment settings"""
    tenant = request.user.tenant
    if not tenant:
        return JsonResponse({'error': 'No tenant associated'}, status=403)
    
    try:
        data = json.loads(request.body)
        payment_settings, created = PaymentSetting.objects.get_or_create(tenant=tenant)
        
        # Update fields
        fields_to_update = [
            'enable_cash', 'enable_mpesa', 'enable_card', 'enable_bank_transfer', 'enable_credit',
            'mpesa_shortcode', 'mpesa_consumer_key', 'mpesa_consumer_secret', 'mpesa_passkey',
            'mpesa_environment', 'card_payment_gateway', 'card_public_key', 'card_secret_key',
            'card_webhook_secret', 'bank_name', 'bank_account_name', 'bank_account_number',
            'bank_branch', 'bank_swift_code', 'credit_limit_enabled', 'credit_days_allowed',
            'require_payment_confirmation', 'require_payment_receipt', 'send_payment_receipt_email',
            'send_payment_receipt_sms', 'enable_partial_payment', 'enable_deposit_payment',
            'display_currency', 'display_currency_symbol', 'currency_position',
            'decimal_places', 'thousand_separator', 'decimal_separator',
            'enable_tax', 'tax_inclusive', 'tax_label',
            'payment_footer_text', 'show_payment_instructions', 'payment_instructions',
            
            # ============================================
            # RECEIPT PAYMENT DETAILS - ADD THESE
            # ============================================
            'till_number', 'paybill_number', 'account_number',
            'show_till_number', 'show_paybill', 'show_account_number',
            'show_payment_details_on_receipt'
        ]
        
        for field in fields_to_update:
            if field in data:
                setattr(payment_settings, field, data[field])
        
        # Decimal fields
        decimal_fields = [
            'credit_limit_amount', 'credit_interest_rate', 'credit_fee_percentage',
            'max_cash_payment', 'min_cash_payment', 'max_mpesa_payment', 'min_mpesa_payment',
            'deposit_percentage', 'tax_percentage'
        ]
        
        for field in decimal_fields:
            if field in data and data[field] is not None:
                try:
                    setattr(payment_settings, field, Decimal(str(data[field])))
                except (ValueError, TypeError):
                    pass
        
        payment_settings.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Payment settings updated successfully',
            'id': payment_settings.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error updating payment settings: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_payment_methods(request):
    """Get available payment methods for current tenant"""
    tenant = request.user.tenant
    if not tenant:
        return JsonResponse({'error': 'No tenant associated'}, status=403)
    
    try:
        payment_settings = PaymentSetting.objects.get(tenant=tenant)
        methods = payment_settings.get_enabled_payment_methods()
        
        # Get method details
        method_details = []
        for method in methods:
            method_details.append({
                'id': method,
                'name': payment_settings.get_payment_method_display(method),
                'enabled': True,
                'limits': {
                    'min': None,  # You can add min/max limits per method if needed
                    'max': None,
                }
            })
        
        return JsonResponse({
            'payment_methods': method_details,
            'default_currency': payment_settings.display_currency,
            'currency_symbol': payment_settings.display_currency_symbol,
        })
    except PaymentSetting.DoesNotExist:
        return JsonResponse({'error': 'Payment settings not found'}, status=404)

@login_required
def company_settings(request):
    """Company Settings View"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get or create company settings
    settings, created = CompanySetting.objects.get_or_create(tenant=tenant)
    
    if request.method == 'POST':
        # Company Details
        settings.company_name = request.POST.get('company_name', '')
        settings.company_address = request.POST.get('company_address', '')
        settings.company_phone = request.POST.get('company_phone', '')
        settings.company_email = request.POST.get('company_email', '')
        settings.company_website = request.POST.get('company_website', '')
        settings.company_tax_pin = request.POST.get('company_tax_pin', '')
        
        # Branding Colors
        settings.primary_color = request.POST.get('primary_color', '#0d6efd')
        settings.secondary_color = request.POST.get('secondary_color', '#6c757d')
        settings.accent_color = request.POST.get('accent_color', '#ffc107')
        
        # Display Settings
        settings.show_logo_on_receipts = request.POST.get('show_logo_on_receipts') == 'on'
        settings.show_logo_on_invoices = request.POST.get('show_logo_on_invoices') == 'on'
        settings.show_logo_on_reports = request.POST.get('show_logo_on_reports') == 'on'
        settings.show_logo_on_dashboard = request.POST.get('show_logo_on_dashboard') == 'on'
        
        # Handle Logo Upload
        if request.FILES.get('logo'):
            settings.logo = request.FILES['logo']
        
        # Handle Favicon Upload
        if request.FILES.get('favicon'):
            settings.favicon = request.FILES['favicon']
        
        settings.save()
        
        # ✅ FORCE CLEAR ALL CACHES for this tenant
        cache.delete(f"settings_{tenant.id}_global")
        cache.delete(f"settings_{tenant.id}_None_global")
        
        # ✅ Also clear the system settings cache
        cache.delete("settings_system_global")
        
        messages.success(request, '✅ Company settings updated successfully!')
        return redirect('settings:company_settings')
    
    context = {
        'tenant': tenant,
        'settings': settings,
        'active_tab': 'settings',
    }
    return render(request, 'shared/settings/company_settings.html', context)


