# apps/shared/portal/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import update_session_auth_hash
from django.db.models import Sum, F
from django.utils import timezone
from apps.shared.users.models import User
from apps.tronic_master.models import Product, Category, Branch
from apps.tronic_master.models import Sale
from apps.shared.customers.models import Customer
from apps.shared.permissions.models import UserRoleAssignment
from django.http import JsonResponse
from django.core.cache import cache
import logging
from apps.shared.utils.project_helpers import (
    PROJECT_ROLE_MAPPINGS,
    PROJECT_DASHBOARDS,
)
from .helpers import has_pos_access, is_admin_user


logger = logging.getLogger(__name__)


# ============================================
# AUTHENTICATION VIEWS
# ============================================

def portal_login(request):
    """Login page"""
    if request.user.is_authenticated:
        return redirect('portal:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            messages.success(request, f'Welcome back {user.username}!')

            # ✅ Get tenant and project type
            tenant = user.tenant
            project_type = None
            project_code = None

            if tenant:
                project_type = getattr(tenant, 'project_type', None)
                if project_type:
                    project_code = project_type.code.upper()

            # ✅ If user is Super Admin, redirect to Super Admin dashboard
            if user.is_super_admin:
                return redirect('portal:super_admin_dashboard')

            # ✅ If user has no tenant, redirect to support
            if not tenant:
                messages.error(request, 'No tenant assigned to your account. Please contact support.')
                return redirect('portal:support')

            # ✅ If user has project type, redirect to the correct project
            if project_code:
                redirect_by_code = {
                    '001': 'tronic_master:dashboard',
                    '002': 'hotel_master:dashboard',
                    '003': 'food_master:dashboard',
                    '004': 'retail_master:dashboard',
                    '005': 'health_master:dashboard',
                    '006': 'fashion_master:dashboard',
                    '007': 'rental_master:dashboard',
                    '008': 'hardware_master:dashboard',
                    '009': 'carwash_master:dashboard',
                    '010': 'linquor_master:dashboard',
                }
                redirect_url = redirect_by_code.get(project_code)
                if redirect_url:
                    return redirect(redirect_url)
                
                # Try by project name as fallback
                project_name = project_type.name.lower().strip()
                project_app_map = {
                    'tronic_master': 'tronic_master:dashboard',
                    'hotel_master': 'hotel_master:dashboard',
                    'food_master': 'food_master:dashboard',
                    'retail_master': 'retail_master:dashboard',
                    'health_master': 'health_master:dashboard',
                    'fashion_master': 'fashion_master:dashboard',
                    'rental_master': 'rental_master:dashboard',
                    'hardware_master': 'hardware_master:dashboard',
                    'carwash_master': 'carwash_master:dashboard',
                    'linquor_master': 'linquor_master:dashboard',
                }
                for app_name, url in project_app_map.items():
                    if app_name in project_name or project_name in app_name:
                        return redirect(url)

            # ✅ If user has tenant but no project type, redirect to support
            messages.warning(request, 'No project type assigned to your tenant. Please contact support.')
            return redirect('portal:support')

        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'shared/login.html')

def portal_logout(request):
    """Logout"""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('portal:login')

@login_required
def no_project_assigned(request):
    """Professional fallback page for users with no project assigned"""
    return redirect('portal:support')

@login_required
def profile(request):
    """User profile view"""
    tenant = request.user.tenant

    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')

        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.phone_number = phone_number
        user.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('portal:profile')

    context = {
        'tenant': tenant,
        'user': request.user,
    }
    return render(request, 'shared/profile.html', context)

@login_required
def change_password(request):
    """Change password"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('portal:change_password')

        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('portal:change_password')

        if len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return redirect('portal:change_password')

        request.user.set_password(new_password)
        request.user.save()
        update_session_auth_hash(request, request.user)

        messages.success(request, 'Password changed successfully!')
        return redirect('portal:profile')

    # ✅ Add company_settings to context
    context = {
        'tenant': request.user.tenant,
        'user': request.user,
        'company_settings': None,  # Add this
    }

    # Get company settings if tenant exists
    from apps.shared.settings.models import CompanySetting
    if request.user.tenant:
        try:
            context['company_settings'] = CompanySetting.objects.get(tenant=request.user.tenant)
        except CompanySetting.DoesNotExist:
            pass

    return render(request, 'shared/change_password.html', context)

def debug_redirect(request):
    """Debug view to show current project type"""
    user = request.user
    print("=" * 60)
    print("🔍 DEBUG_REDIRECT VIEW")
    print(f"👤 User: {user.username}")
    print(f"🔑 Role: {user.role}")
    print(f"🏢 Tenant: {user.tenant}")

    if user.tenant:
        print(f"📋 Tenant Name: {user.tenant.company_name}")
        print(f"📋 Tenant ID: {user.tenant.id}")
        project_type = getattr(user.tenant, 'project_type', None)
        print(f"📋 Project Type Object: {project_type}")

        if project_type:
            print(f"📋 Project Code: {project_type.code}")
            print(f"📋 Project Name: {project_type.name}")
            print(f"📋 Project Code Upper: {project_type.code.upper()}")
        else:
            print("❌ project_type is None!")
    else:
        print("❌ No tenant!")

    print("=" * 60)

    return JsonResponse({
        'username': user.username,
        'role': user.role,
        'tenant': str(user.tenant),
        'tenant_name': user.tenant.company_name if user.tenant else None,
        'project_type': str(getattr(user.tenant, 'project_type', None)) if user.tenant else None,
        'project_code': getattr(user.tenant, 'project_type', None).code if user.tenant and getattr(user.tenant, 'project_type', None) else None,
    })


# ============================================
# DASHBOARD ROUTER
# ============================================

@login_required
def project_dashboard(request):
    """Route to the correct project dashboard"""
    user = request.user

    # Super Admin
    if user.is_super_admin:
        return redirect('portal:super_admin_dashboard')

    # ✅ Check if user has a tenant
    tenant = getattr(user, 'tenant', None)
    if not tenant:
        messages.error(request, 'No tenant assigned to your account. Please contact support.')
        return redirect('portal:support')

    # ✅ Get project type
    project_type = getattr(tenant, 'project_type', None)
    
    # ✅ If no project type, redirect to support
    if not project_type:
        messages.warning(request, 'No project type assigned to your tenant. Please contact support.')
        return redirect('portal:support')
    
    # ✅ Get project name and code
    project_name = project_type.name.lower().strip()
    project_code = project_type.code.upper()
    
    # ✅ Log for debugging
    logger.info(f"Project Dashboard - User: {user.username}, Project Name: {project_name}, Code: {project_code}")
    
    # ✅ Redirect by code
    redirect_by_code = {
        '001': 'tronic_master:dashboard',
        '002': 'hotel_master:dashboard',
        '003': 'food_master:dashboard',
        '004': 'retail_master:dashboard',
        '005': 'health_master:dashboard',
        '006': 'fashion_master:dashboard',
        '007': 'rental_master:dashboard',
        '008': 'hardware_master:dashboard',
        '009': 'carwash_master:dashboard',
        '010': 'linquor_master:dashboard',
    }
    
    # ✅ Try to find redirect by code first
    redirect_url = redirect_by_code.get(project_code)
    
    # ✅ If not found by code, try by name
    if not redirect_url:
        redirect_by_name = {
            'tronic master': 'tronic_master:dashboard',
            'tech master': 'tronic_master:dashboard',
            'tronic_master': 'tronic_master:dashboard',
            'tech_master': 'tronic_master:dashboard',
            'hotel master': 'hotel_master:dashboard',
            'hotel_master': 'hotel_master:dashboard',
            'food master': 'food_master:dashboard',
            'food_master': 'food_master:dashboard',
            'retail master': 'retail_master:dashboard',
            'retail_master': 'retail_master:dashboard',
            'health master': 'health_master:dashboard',
            'health_master': 'health_master:dashboard',
            'fashion master': 'fashion_master:dashboard',
            'fashion_master': 'fashion_master:dashboard',
            'rental master': 'rental_master:dashboard',
            'rental_master': 'rental_master:dashboard',
            'hardware master': 'hardware_master:dashboard',
            'hardware_master': 'hardware_master:dashboard',
            'carwash master': 'carwash_master:dashboard',
            'carwash_master': 'carwash_master:dashboard',
            'liquor master': 'linquor_master:dashboard',
            'linquor master': 'linquor_master:dashboard',
            'linquor_master': 'linquor_master:dashboard',
        }
        
        # Try exact match
        redirect_url = redirect_by_name.get(project_name)
        
        # Try partial match
        if not redirect_url:
            for key, value in redirect_by_name.items():
                if key in project_name or project_name in key:
                    redirect_url = value
                    break
    
    # ✅ If we found a redirect URL, use it
    if redirect_url:
        logger.info(f"Redirecting to: {redirect_url}")
        return redirect(redirect_url)
    
    # ✅ Last resort - redirect to support
    messages.warning(request, f'No dashboard found for project: {project_name}. Please contact support.')
    return redirect('portal:support')

@login_required
def tenant_dashboard(request):
    """Tenant Dashboard - Shows tenant info but redirects to support if no tenant"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account. Please contact support.')
        return redirect('portal:support')
    
    # Get project type
    project_type = getattr(tenant, 'project_type', None)
    
    # If no project type, redirect to support
    if not project_type:
        messages.warning(request, 'No project type assigned to your tenant. Please contact support.')
        return redirect('portal:support')
    
    # Get user roles
    from apps.shared.permissions.models import UserRoleAssignment
    user_roles = UserRoleAssignment.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('role')
    
    context = {
        'tenant': tenant,
        'project_type': project_type,
        'user_roles': user_roles,
        'has_roles': user_roles.exists(),
        'active_tab': 'dashboard',
    }
    return render(request, 'shared/tenant_dashboard.html', context)

# ============================================
# Helper function to show available project mappings
# ============================================

def get_project_roles(request):
    """
    API endpoint to get available roles for a project (for debugging/admin)
    """
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Access denied'}, status=403)

    project_code = request.GET.get('project_code')
    if not project_code:
        return JsonResponse({'error': 'project_code required'}, status=400)

    project_config = PROJECT_ROLE_MAPPINGS.get(project_code.upper(), {})

    return JsonResponse({
        'project_code': project_code,
        'roles': project_config,
        'dashboard': PROJECT_DASHBOARDS.get(project_code.upper()),
    })

@login_required
def support(request):
    """Support page showing project information"""
    from apps.shared.tenants.models import Tenant
    from apps.shared.users.models import User
    from apps.tronic_master.models import Sale
    from apps.tronic_master.models import Product
    from apps.shared.settings.models import SystemSetting

    # Get platform stats
    total_tenants = Tenant.objects.filter(status='active').count()
    total_users = User.objects.filter(is_active=True).count()
    total_sales = Sale.objects.filter(status='completed').count()
    total_products = Product.objects.filter(is_active=True).count()

    # Get platform settings
    platform_name = SystemSetting.get('platform_name', 'RS Master Africa')
    platform_description = SystemSetting.get('platform_description',
        'RS Master Africa is a comprehensive business management platform designed to help businesses streamline their operations, manage inventory, process sales, and grow their customer base.'
    )
    support_email = SystemSetting.get('support_email', 'support@rsmaster.com')
    sales_email = SystemSetting.get('sales_email', 'sales@rsmaster.com')
    support_phone = SystemSetting.get('support_phone', '+254 722 527 955')
    support_hours = SystemSetting.get('support_hours', 'Monday - Friday, 8:00 AM - 6:00 PM EAT')
    company_address = SystemSetting.get('company_address', 'Nairobi, Kenya')
    whatsapp_number = SystemSetting.get('whatsapp_number', '254722527955')

    # Social media links
    social_facebook = SystemSetting.get('social_facebook', '#')
    social_twitter = SystemSetting.get('social_twitter', '#')
    social_linkedin = SystemSetting.get('social_linkedin', '#')
    social_youtube = SystemSetting.get('social_youtube', '#')
    social_instagram = SystemSetting.get('social_instagram', '#')
    social_whatsapp = SystemSetting.get('social_whatsapp', '#')

    # Documentation and tutorial URLs
    docs_url = SystemSetting.get('docs_url', '/docs/')
    tutorials_url = SystemSetting.get('tutorials_url', '/tutorials/')
    tickets_url = SystemSetting.get('tickets_url', '/support/tickets/')

    context = {
        'user': request.user,
        'tenant': request.user.tenant,
        # Platform stats
        'total_tenants': total_tenants,
        'total_users': total_users,
        'total_sales': total_sales,
        'total_products': total_products,
        # Platform info
        'platform_name': platform_name,
        'platform_description': platform_description,
        # Contact info
        'support_email': support_email,
        'sales_email': sales_email,
        'support_phone': support_phone,
        'support_hours': support_hours,
        'company_address': company_address,
        'whatsapp_number': whatsapp_number,
        # Social media
        'social_facebook': social_facebook,
        'social_twitter': social_twitter,
        'social_linkedin': social_linkedin,
        'social_youtube': social_youtube,
        'social_instagram': social_instagram,
        'social_whatsapp': social_whatsapp,
        # Docs
        'docs_url': docs_url,
        'tutorials_url': tutorials_url,
        'tickets_url': tickets_url,
    }
    return render(request, 'shared/support.html', context)


# ============================================
# SUPER ADMIN DASHBOARD
# ============================================

@login_required
def super_admin_dashboard(request):
    """Super Admin Dashboard - Platform Overview"""

    if not request.user.is_superuser:
        messages.error(request, 'Access denied. Super Admin only.')
        return redirect('portal:dashboard')

    from apps.shared.tenants.models import Tenant
    from apps.shared.users.models import User
    from apps.shared.tenants.models import SubscriptionInvoice
    from django.db.models import Sum

    total_tenants = Tenant.objects.count()
    active_tenants = Tenant.objects.filter(status='active').count()
    pending_tenants = Tenant.objects.filter(status='pending').count()
    total_users = User.objects.count()

    # Platform revenue
    platform_revenue = SubscriptionInvoice.objects.filter(
        status='paid'
    ).aggregate(total=Sum('amount'))['total'] or 0

    recent_tenants = Tenant.objects.all().order_by('-created_at')[:10]

    context = {
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'pending_tenants': pending_tenants,
        'total_users': total_users,
        'platform_revenue': platform_revenue,
        'recent_tenants': recent_tenants,
        'is_super_admin': True,
    }
    return render(request, 'shared/super_admin_dashboard.html', context)


# ============================================
# TECH MASTER DASHBOARD
# ============================================

@login_required
def tech_pos(request):
    """TECH MASTER Point of Sale - Requires PIN verification"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    # ✅ Check if user has POS access (includes admin/superadmin)
    if not has_pos_access(request.user):
        messages.error(
            request, 
            'You do not have permission to access POS. Admin, Superadmin, or Cashier role required.'
        )
        return redirect('tronic_master:dashboard')

    # ✅ Check if user is admin (skip PIN for admin roles)
    is_admin = is_admin_user(request.user)

    # ✅ PIN verification (only for non-admin users)
    if not is_admin:
        if not request.user.pin_code:
            messages.warning(
                request, 
                'Please set a PIN code in your profile settings before accessing POS.'
            )
            return redirect('settings:profile_settings')

        if not request.session.get('pos_pin_verified', False):
            return redirect('tronic_master:verify_pin')

        # Check PIN verification expiration
        verified_at = request.session.get('pos_pin_verified_at')
        if verified_at:
            from datetime import datetime, timedelta
            try:
                verified_time = datetime.fromisoformat(verified_at)
                if timezone.now() - verified_time > timedelta(minutes=30):
                    # PIN expired, clear session
                    request.session.pop('pos_pin_verified', None)
                    request.session.pop('pos_pin_verified_at', None)
                    messages.warning(request, 'PIN verification expired. Please verify again.')
                    return redirect('tronic_master:verify_pin')
            except (ValueError, TypeError):
                pass

    context = {
        'tenant': tenant,
        'active_tab': 'pos',
        'is_admin': is_admin,
    }
    return render(request, 'tronic_master/pos.html', context)

@login_required
def verify_pin(request):
    """Verify user PIN before accessing POS"""
    # Check if user has a PIN set
    if not request.user.pin_code:
        messages.warning(request, 'Please set a PIN code in your profile settings first.')
        return redirect('settings:profile_settings')

    # Check if user has cashier role
    has_cashier_role = UserRoleAssignment.objects.filter(
        user=request.user,
        role__codename='cashier',
        is_active=True
    ).exists()

    if not has_cashier_role:
        messages.error(request, 'You do not have permission to access POS.')
        return redirect('tronic_master:dashboard')

    if request.method == 'POST':
        pin = request.POST.get('pin', '').strip()

        if not pin:
            messages.error(request, 'Please enter your PIN')
            return redirect('tronic_master:verify_pin')

        # Check if PIN matches
        if request.user.pin_code and pin == request.user.pin_code:
            request.session['pos_pin_verified'] = True
            request.session['pos_pin_verified_at'] = timezone.now().isoformat()
            messages.success(request, 'PIN verified successfully!')
            return redirect('tronic_master:pos')
        else:
            messages.error(request, 'Invalid PIN. Please try again.')
            return redirect('tronic_master:verify_pin')

    # GET request - show PIN form
    return render(request, 'tronic_master/verify_pin.html', {
        'tenant': request.user.tenant,
        'user': request.user,
    })

@login_required
def verify_pin_ajax(request):
    """AJAX endpoint for PIN verification - DEPRECATED"""
    return JsonResponse({'success': False, 'error': 'PIN verification is no longer supported'}, status=400)

@login_required
def clear_pin_verification(request):
    """Clear PIN verification - DEPRECATED"""
    messages.info(request, 'PIN verification cleared')
    return redirect('tronic_master:pos')

@login_required
def tech_dashboard(request):
    """TECH MASTER Dashboard - Check for system role and project role"""
    user = request.user

    # ✅ Retrieve manager context from session if it exists
    manager_context = request.session.pop('manager_context', {})

    # ✅ Super Admin and Tenant Admin have full access
    if user.is_super_admin or user.is_tenant_admin:
        tenant = user.tenant
        if not tenant:
            messages.error(request, 'No tenant assigned')
            return redirect('portal:dashboard')

        # Get stats
        total_products = Product.objects.filter(tenant=tenant, is_active=True).count()
        total_categories = Category.objects.filter(tenant=tenant, is_active=True).count()
        total_branches = Branch.objects.filter(tenant=tenant, is_active=True).count()
        total_users = User.objects.filter(tenant=tenant, is_active=True).count()
        total_customers = Customer.objects.filter(tenant=tenant).count()
        total_suppliers = 0

        # Today's sales
        today = timezone.now().date()
        today_sales = Sale.objects.filter(
            tenant=tenant,
            created_at__date=today,
            status='completed'
        ).aggregate(total=Sum('total'))['total'] or 0

        recent_sales = Sale.objects.filter(
            tenant=tenant,
            status='completed'
        ).order_by('-created_at')[:5]

        low_stock_count = Product.objects.filter(
            tenant=tenant,
            available_quantity__lte=F('reorder_level'),
            is_active=True
        ).count()

        # ✅ Merge manager_context if it exists
        context = {
            'tenant': tenant,
            'active_tab': 'dashboard',
            'total_products': total_products,
            'total_categories': total_categories,
            'total_branches': total_branches,
            'total_users': total_users,
            'total_customers': total_customers,
            'total_suppliers': total_suppliers,
            'today_sales': today_sales,
            'recent_sales': recent_sales,
            'low_stock_count': low_stock_count,
            **manager_context,  # ✅ Merge manager context
        }
        return render(request, 'tronic_master/dashboard_tech.html', context)

    # ✅ Regular users - Check project roles
    has_manager_role = UserRoleAssignment.objects.filter(
        user=user,
        role__codename='manager',
        is_active=True
    ).exists()

    has_cashier_role = UserRoleAssignment.objects.filter(
        user=user,
        role__codename='cashier',
        is_active=True
    ).exists()

    has_sales_agent_role = UserRoleAssignment.objects.filter(
        user=user,
        role__codename='sales_agent',
        is_active=True
    ).exists()

    if has_manager_role:
        # Manager dashboard
        tenant = user.tenant
        # ✅ Merge manager_context if it exists
        context = {
            'tenant': tenant,
            'active_tab': 'dashboard',
            **manager_context,  # ✅ Merge manager context
        }
        return render(request, 'tronic_master/manager_dashboard.html', context)

    if has_cashier_role:
        messages.info(request, 'Redirecting to POS...')
        return redirect('tronic_master:pos')

    if has_sales_agent_role:
        messages.info(request, 'Redirecting to Sales Dashboard...')
        return redirect('tronic_master:my_sales')

    # No project role assigned
    messages.warning(request, 'You have not been assigned a project role. Please contact your administrator.')
    return redirect('portal:dashboard')

@login_required
def report_dashboard(request):
    """Reports dashboard - Admin only"""
    user = request.user

    # Only Super Admin and Tenant Admin can access reports
    if not (user.is_super_admin or user.is_tenant_admin):
        messages.error(request, 'Access denied. Admin only.')
        return redirect('portal:dashboard')

    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    from django.db.models import Sum
    from apps.tronic_master.models import Sale
    from apps.tronic_master.models import Product
    from apps.shared.expenses.models import Expense
    from apps.shared.customers.models import Customer
    from django.utils import timezone
    from datetime import timedelta

    # Date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if date_from:
        date_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
    else:
        date_from = timezone.now().date() - timedelta(days=30)

    if date_to:
        date_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
    else:
        date_to = timezone.now().date()

    # Sales stats
    sales = Sale.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__date__gte=date_from,
        created_at__date__lte=date_to
    )
    total_sales = sales.aggregate(total=Sum('total'))['total'] or 0

    # Today's sales
    today = timezone.now().date()
    todays_sales = Sale.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__date=today
    ).aggregate(total=Sum('total'))['total'] or 0

    # Monthly sales
    start_of_month = today.replace(day=1)
    monthly_sales = Sale.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__date__gte=start_of_month
    ).aggregate(total=Sum('total'))['total'] or 0

    # Products
    total_products = Product.objects.filter(tenant=tenant, is_active=True).count()
    low_stock_count = Product.objects.filter(
        tenant=tenant,
        available_quantity__lte=5,
        is_active=True
    ).count()

    # Expenses
    total_expenses = Expense.objects.filter(
        tenant=tenant,
        status='paid',
        date__gte=date_from,
        date__lte=date_to
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Customers
    total_customers = Customer.objects.filter(tenant=tenant).count()
    new_customers = Customer.objects.filter(
        tenant=tenant,
        created_at__date__gte=start_of_month
    ).count()

    context = {
        'tenant': tenant,
        'date_from': date_from,
        'date_to': date_to,
        'total_sales': total_sales,
        'todays_sales': todays_sales,
        'monthly_sales': monthly_sales,
        'total_products': total_products,
        'low_stock_count': low_stock_count,
        'total_expenses': total_expenses,
        'total_customers': total_customers,
        'new_customers': new_customers,
        'sales_growth': 12,
        'expense_growth': 8,
        'active_tab': 'reports',
    }
    return render(request, 'tronic_master/reports.html', context)

@login_required
def platform_analytics(request):
    """Platform Analytics - Super Admin only"""
    if not request.user.is_superuser:
        messages.error(request, 'Access denied. Super Admin only.')
        return redirect('portal:dashboard')

    from apps.shared.tenants.models import Tenant, SubscriptionPlan, SubscriptionInvoice
    from apps.shared.users.models import User
    from django.db.models import Sum
    from django.utils import timezone
    from datetime import timedelta

    # Basic Stats
    total_tenants = Tenant.objects.count()
    active_tenants = Tenant.objects.filter(status='active').count()
    pending_tenants = Tenant.objects.filter(status='pending').count()
    total_users = User.objects.count()

    # Revenue Stats
    total_revenue = SubscriptionInvoice.objects.filter(
        status='paid'
    ).aggregate(total=Sum('amount'))['total'] or 0

    # This month revenue
    start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue = SubscriptionInvoice.objects.filter(
        status='paid',
        created_at__gte=start_of_month
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Tenant growth (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    new_tenants_last_30 = Tenant.objects.filter(
        created_at__gte=thirty_days_ago
    ).count()

    # Subscription plan distribution
    plan_distribution = {}
    for plan in SubscriptionPlan.objects.filter(is_active=True):
        count = Tenant.objects.filter(subscription_plan=plan.code).count()
        if count > 0:
            plan_distribution[plan.name] = count

    # Recent activity (last 5 tenants)
    recent_tenants = Tenant.objects.all().order_by('-created_at')[:5]

    context = {
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'pending_tenants': pending_tenants,
        'total_users': total_users,
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        'new_tenants_last_30': new_tenants_last_30,
        'plan_distribution': plan_distribution,
        'recent_tenants': recent_tenants,
        'is_super_admin': True,
    }
    return render(request, 'shared/platform_analytics.html', context)


# ============================================
# FOOD MASTER VIEWS
# ============================================

@login_required
def food_dashboard(request):
    """FOOD MASTER Dashboard"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    # Check for project roles
    has_manager_role = UserRoleAssignment.objects.filter(
        user=request.user,
        role__codename='manager',
        is_active=True
    ).exists()

    has_waiter_role = UserRoleAssignment.objects.filter(
        user=request.user,
        role__codename='waiter',
        is_active=True
    ).exists()

    context = {
        'tenant': tenant,
        'active_tab': 'dashboard',
        'is_manager': has_manager_role,
        'is_waiter': has_waiter_role,
    }
    return render(request, 'food_master/dashboard_food.html', context)

@login_required
def food_menu(request):
    """Restaurant menu management - Admin only"""
    if not (request.user.is_super_admin or request.user.is_tenant_admin):
        messages.error(request, 'Access denied. Admin only.')
        return redirect('food_master:dashboard')

    context = {'active_tab': 'menu', 'tenant': request.user.tenant}
    return render(request, 'food_master/menu.html', context)

@login_required
def food_orders(request):
    """Restaurant orders management"""
    context = {'active_tab': 'orders', 'tenant': request.user.tenant}
    return render(request, 'food_master/orders.html', context)

@login_required
def food_tables(request):
    """Restaurant tables management - Admin only"""
    if not (request.user.is_super_admin or request.user.is_tenant_admin):
        messages.error(request, 'Access denied. Admin only.')
        return redirect('food_master:dashboard')

    context = {'active_tab': 'tables', 'tenant': request.user.tenant}
    return render(request, 'food_master/tables.html', context)

@login_required
def food_kitchen(request):
    """Kitchen display - Check for kitchen staff role"""
    has_kitchen_role = UserRoleAssignment.objects.filter(
        user=request.user,
        role__codename='kitchen',
        is_active=True
    ).exists()

    if not has_kitchen_role:
        messages.error(request, 'Access denied. Kitchen staff only.')
        return redirect('food_master:dashboard')

    context = {'active_tab': 'kitchen', 'tenant': request.user.tenant}
    return render(request, 'food_master/kitchen.html', context)


# ============================================
# RETAIL MASTER VIEWS
# ============================================

@login_required
def retail_dashboard(request):
    """RETAIL MASTER Dashboard"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    context = {
        'tenant': tenant,
        'active_tab': 'dashboard',
    }
    return render(request, 'retail_master/dashboard_retail.html', context)


# ============================================
# HEALTH MASTER VIEWS
# ============================================

@login_required
def health_dashboard(request):
    """HEALTH MASTER Dashboard"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    context = {
        'tenant': tenant,
        'active_tab': 'dashboard',
    }
    return render(request, 'health_master/dashboard_health.html', context)


# ============================================
# FASHION MASTER VIEWS
# ============================================

@login_required
def fashion_dashboard(request):
    """FASHION MASTER Dashboard"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    context = {
        'tenant': tenant,
        'active_tab': 'dashboard',
    }
    return render(request, 'fashion_master/dashboard_fashion.html', context)


# ============================================
# USER MANAGEMENT VIEWS (Deprecated - use apps.shared.users.views)
# ============================================

@login_required
def user_list(request):
    """List all users - Deprecated, redirect to users:user_list"""
    return redirect('users:user_list')


@login_required
def add_user(request):
    """Add new user - Deprecated, redirect to users:user_create"""
    return redirect('users:user_create')


# ============================================
# PLATFORM SETTINGS
# ============================================


@login_required
def platform_settings(request):
    """Platform Settings for Super Admin"""
    if not request.user.is_superuser:
        messages.error(request, 'Access denied')
        return redirect('portal:dashboard')

    from apps.shared.tenants.models import Tenant, ProjectType, SubscriptionPlan
    from apps.shared.users.models import User
    from apps.tronic_master.models import Product, Branch
    from apps.shared.settings.models import SystemSetting
    from django.core.cache import cache
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    import os

    # Handle POST - Save settings
    if request.method == 'POST':
        # Save platform settings
        SystemSetting.set('platform_name', request.POST.get('platform_name', 'RS Master Platform'))
        SystemSetting.set('platform_email', request.POST.get('platform_email', 'admin@rsmaster.com'))
        SystemSetting.set('timezone', request.POST.get('timezone', 'Africa/Nairobi'))
        SystemSetting.set('currency', request.POST.get('currency', 'KES'))
        SystemSetting.set('allow_registration', str(request.POST.get('allow_registration') == 'on'))
        SystemSetting.set('debug_mode', str(request.POST.get('debug_mode') == 'on'))
        SystemSetting.set('email_notifications', str(request.POST.get('email_notifications') == 'on'))

        # Handle logo upload
        if request.FILES.get('platform_logo'):
            logo_file = request.FILES['platform_logo']

            # Validate file type
            allowed_types = ['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp']
            if logo_file.content_type not in allowed_types:
                messages.error(request, 'Invalid file type. Please upload PNG, JPG, SVG, or WebP.')
                return redirect('portal:platform_settings')

            # Validate file size (max 5MB)
            if logo_file.size > 5 * 1024 * 1024:
                messages.error(request, 'File size too large. Maximum 5MB allowed.')
                return redirect('portal:platform_settings')

            # Save the logo
            file_extension = os.path.splitext(logo_file.name)[1]
            filename = f'platform_logo{file_extension}'
            filepath = os.path.join('settings', filename)

            # Delete old logo if exists
            if default_storage.exists(filepath):
                default_storage.delete(filepath)

            # Save new logo
            saved_path = default_storage.save(filepath, ContentFile(logo_file.read()))
            SystemSetting.set('platform_logo', saved_path)

        # Handle logo removal
        if request.POST.get('remove_logo') == 'true':
            logo_path = SystemSetting.get('platform_logo', None)
            if logo_path and default_storage.exists(logo_path):
                default_storage.delete(logo_path)
            SystemSetting.set('platform_logo', '')

        messages.success(request, 'Settings saved successfully!')
        return redirect('portal:platform_settings')

    # GET - Load settings
    platform_logo = SystemSetting.get('platform_logo', '')

    context = {
        'is_super_admin': True,
        'total_tenants': Tenant.objects.count(),
        'total_users': User.objects.count(),
        'total_project_types': ProjectType.objects.count(),
        'total_subscription_plans': SubscriptionPlan.objects.filter(is_active=True).count(),
        'total_products': Product.objects.count(),
        'total_branches': Branch.objects.count(),
        'platform_name': SystemSetting.get('platform_name', 'RS Master Platform'),
        'platform_email': SystemSetting.get('platform_email', 'admin@rsmaster.com'),
        'timezone': SystemSetting.get('timezone', 'Africa/Nairobi'),
        'currency': SystemSetting.get('currency', 'KES'),
        'allow_registration': SystemSetting.get('allow_registration', 'True') == 'True',
        'debug_mode': SystemSetting.get('debug_mode', 'False') == 'True',
        'email_notifications': SystemSetting.get('email_notifications', 'True') == 'True',
        'maintenance_mode': cache.get('maintenance_mode', False),
        'platform_logo': platform_logo,  # Add logo to context
    }
    return render(request, 'shared/platform_settings.html', context)


@login_required
def platform_settings_stats(request):
    """API endpoint for stats refresh"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Access denied'}, status=403)

    from apps.shared.tenants.models import Tenant, ProjectType, SubscriptionPlan
    from apps.shared.users.models import User
    from apps.tronic_master.models import Product, Branch

    return JsonResponse({
        'total_tenants': Tenant.objects.count(),
        'total_users': User.objects.count(),
        'total_project_types': ProjectType.objects.count(),
        'total_subscription_plans': SubscriptionPlan.objects.filter(is_active=True).count(),
        'total_products': Product.objects.count(),
        'total_branches': Branch.objects.count(),
    })


@login_required
def toggle_maintenance_mode(request):
    """Toggle maintenance mode - Super Admin only"""
    if not request.user.is_superuser:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Access denied - Super Admin only'
            }, status=403)
        messages.error(request, 'Access denied')
        return redirect('portal:dashboard')

    if request.method == 'POST':
        try:
            import json

            # Parse the request body
            try:
                data = json.loads(request.body) if request.body else {}
                enabled = data.get('enabled')
            except json.JSONDecodeError:
                enabled = None

            # Determine the new status
            if enabled is None:
                # If no value provided, toggle (fallback)
                current_status = cache.get('maintenance_mode', False)
                new_status = not current_status
            else:
                # Use the provided value - convert to boolean
                if isinstance(enabled, bool):
                    new_status = enabled
                else:
                    new_status = enabled == 'true' or enabled == True

            # Save to cache
            cache.set('maintenance_mode', new_status, timeout=None)

            # Also save to database for persistence
            try:
                from apps.shared.settings.models import SystemSetting
                SystemSetting.objects.update_or_create(
                    key='maintenance_mode',
                    defaults={'value': str(new_status)}
                )
            except Exception as db_error:
                logger.warning(f"Could not save maintenance mode to database: {db_error}")

            status_text = 'enabled' if new_status else 'disabled'
            logger.info(f"Maintenance mode set to: {new_status} by {request.user.username}")

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'maintenance_mode': new_status,
                    'message': f'Maintenance mode {status_text}!'
                })

            messages.success(request, f'Maintenance mode {status_text}!')
            return redirect('portal:platform_settings')

        except Exception as e:
            logger.error(f"Error toggling maintenance: {str(e)}", exc_info=True)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)

            messages.error(request, f'Failed to toggle maintenance: {str(e)}')
            return redirect('portal:platform_settings')

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)


def maintenance_page(request):
    """Maintenance mode page"""
    # Check if maintenance mode is actually enabled
    maintenance_mode = cache.get('maintenance_mode', False)

    # Also check database
    if not maintenance_mode:
        try:
            from apps.shared.settings.models import SystemSetting
            db_value = SystemSetting.get('maintenance_mode', 'False')
            maintenance_mode = db_value == 'True'
            if maintenance_mode:
                cache.set('maintenance_mode', True, timeout=None)
        except:
            pass

    return render(request, 'shared/maintenance.html', {
        'maintenance': maintenance_mode
    })



@login_required
def manager_dashboard(request):
    """Manager Dashboard - Deprecated, redirect to tech_dashboard with full context"""

    # Build comprehensive context
    tenant = request.user.tenant

    # Get stats
    from apps.tronic_master.models import Product, Category, Branch
    from apps.shared.customers.models import Customer
    from django.utils import timezone

    context = {
        'tenant': tenant,
        'active_tab': 'dashboard',
        'from_manager': True,
        'redirect_timestamp': timezone.now().isoformat(),
        'message': 'You were redirected from the manager dashboard',
        # Stats
        'total_products': Product.objects.filter(tenant=tenant, is_active=True).count(),
        'total_categories': Category.objects.filter(tenant=tenant, is_active=True).count(),
        'total_branches': Branch.objects.filter(tenant=tenant, is_active=True).count(),
        'total_customers': Customer.objects.filter(tenant=tenant).count(),
    }

    # Store in session
    request.session['manager_context'] = context

    # Redirect with success message
    messages.success(request, 'Redirected to tech dashboard with full context')

    return redirect('tronic_master:dashboard')




@login_required
def live_chat(request):
    """Live Chat page - Super Admin only"""
    if not request.user.is_superuser:
        messages.error(request, 'Access denied. Only Super Admins can access live chat.')
        return redirect('portal:dashboard')

    context = {
        'conversations': [],
        'online_count': 0,
        'is_super_admin': True,
    }
    return render(request, 'shared/live_chat.html', context)


@login_required
def documentation(request):
    """Documentation page"""
    context = {
        'user': request.user,
        'tenant': request.user.tenant,
        'active_tab': 'documentation',
    }
    return render(request, 'shared/documentation.html', context)


@login_required
def tutorials(request):
    """Video tutorials page"""
    context = {
        'user': request.user,
        'tenant': request.user.tenant,
        'active_tab': 'tutorials',
    }
    return render(request, 'shared/tutorials.html', context)


@login_required
def support_tickets(request):
    """Support tickets page"""
    context = {
        'user': request.user,
        'tenant': request.user.tenant,
        'active_tab': 'tickets',
    }
    return render(request, 'shared/support_tickets.html', context)