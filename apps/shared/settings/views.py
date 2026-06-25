# apps/shared/settings/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from .models import ReceiptSetting, ProfileSetting, SystemSetting
from apps.shared.users.models import User
from apps.shared.tenants.models import Tenant
import logging

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