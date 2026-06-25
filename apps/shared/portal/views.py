from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import update_session_auth_hash
from django.db.models import Sum, F
from django.utils import timezone
from apps.shared.users.models import User
from apps.tech_master.inventory.models import Product, Category, Branch
from apps.tech_master.sales.models import Sale
from apps.shared.customers.models import Customer
from django.http import JsonResponse
from django.core.cache import cache
import logging


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
            
            # Set tenant in session
            if hasattr(user, 'tenant') and user.tenant:
                request.session['tenant_id'] = user.tenant.id
            
            messages.success(request, f'Welcome back {user.username}!')
            return redirect('portal:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'shared/login.html')


def portal_logout(request):
    """Logout"""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('portal:login')


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
            return redirect('change_password')
        
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('change_password')
        
        if len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return redirect('change_password')
        
        request.user.set_password(new_password)
        request.user.save()
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Password changed successfully!')
        return redirect('portal:profile')
    
    return render(request, 'shared/change_password.html')


# ============================================
# DASHBOARD ROUTER
# ============================================

@login_required
def project_dashboard(request):
    """Route to the correct project dashboard based on user role"""
    user = request.user
    
    # ✅ SUPER ADMIN - Go to super admin dashboard FIRST (no tenant check)
    if user.is_superuser or user.role == 'super_admin':
        return redirect('portal:super_admin_dashboard')
    
    # ✅ For all other users, check tenant
    tenant = getattr(user, 'tenant', None)
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('portal:login')
    
    # ✅ CASHIER - Redirect to POS directly
    if user.role == 'cashier':
        return redirect('tech_master:pos')
    
    # ✅ SALES AGENT - Redirect to Sales Agent dashboard
    if user.role == 'sales_agent':
        return redirect('tech_master:my_sales')
    
    # ✅ MANAGER - Redirect to Manager dashboard
    if user.role == 'manager':
        return redirect('tech_master:dashboard')
    
    # ✅ ADMIN / TENANT_ADMIN - Redirect to Admin dashboard
    if user.role == 'admin' or user.role == 'tenant_admin':
        project_type = getattr(tenant, 'project_type', None)
        if not project_type:
            return redirect('admin_dashboard')
        
        code = project_type.code.upper()
        
        # Route to project-specific dashboard
        if code in ['TECH_MASTER', 'TECHMASTER', 'PRJ-001']:
            return redirect('tech_master:dashboard')
        elif code in ['HOTEL_MASTER', 'HOTELMASTER', 'PRJ-003']:
            return redirect('hotel_master:dashboard')
        elif code in ['FOOD_MASTER', 'FOODMASTER', 'PRJ-002']:
            return redirect('food_master:dashboard')
        elif code in ['RETAIL_MASTER', 'RETAILMASTER', 'PRJ-004']:
            return redirect('retail_master:dashboard')
        elif code in ['HEALTH_MASTER', 'HEALTHMASTER', 'PRJ-005']:
            return redirect('health_master:dashboard')
        elif code in ['FASHION_MASTER', 'FASHIONMASTER', 'PRJ-006']:
            return redirect('fashion_master:dashboard')
        else:
            return redirect('admin_dashboard')
    
    # Fallback
    return redirect('portal:dashboard')


# ============================================
# SUPER ADMIN DASHBOARD
# ============================================


@login_required
def super_admin_dashboard(request):
    """Super Admin Dashboard - Platform Overview"""
    
    # ✅ Super Admin check ONLY - NO tenant check
    if not request.user.is_superuser:
        messages.error(request, 'Access denied. Super Admin only.')
        return redirect('dashboard')
    
    # ✅ Skip tenant check completely
    
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
def verify_pin(request):
    """Verify user PIN before accessing POS"""
    if request.method == 'POST':
        pin = request.POST.get('pin', '').strip()
        
        if not pin:
            messages.error(request, 'Please enter your PIN')
            return redirect('tech_master:verify_pin')
        
        # Check if PIN matches
        if request.user.pin_code and pin == request.user.pin_code:
            # Store PIN verification in session
            request.session['pos_pin_verified'] = True
            request.session['pos_pin_verified_at'] = timezone.now().isoformat()
            messages.success(request, 'PIN verified successfully!')
            return redirect('tech_master:pos')
        else:
            messages.error(request, 'Invalid PIN. Please try again.')
            return redirect('tech_master:verify_pin')
    
    # GET request - show PIN form
    return render(request, 'tech_master/verify_pin.html', {
        'tenant': request.user.tenant,
        'user': request.user,
    })


@login_required
def verify_pin_ajax(request):
    """AJAX endpoint for PIN verification"""
    import json
    from django.http import JsonResponse
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            pin = data.get('pin', '').strip()
        except:
            return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
        
        if not pin:
            return JsonResponse({'success': False, 'error': 'PIN is required'})
        
        if request.user.pin_code and pin == request.user.pin_code:
            request.session['pos_pin_verified'] = True
            request.session['pos_pin_verified_at'] = timezone.now().isoformat()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid PIN'})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)


@login_required
def clear_pin_verification(request):
    """Clear PIN verification (logout from POS)"""
    if 'pos_pin_verified' in request.session:
        del request.session['pos_pin_verified']
    if 'pos_pin_verified_at' in request.session:
        del request.session['pos_pin_verified_at']
    messages.info(request, 'PIN verification cleared')
    return redirect('tech_master:pos')


@login_required
def tech_pos(request):
    """TECH MASTER Point of Sale - Requires PIN verification"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # ✅ Check if PIN is required and verified
    # Check if user has a PIN set
    if not request.user.pin_code:
        messages.warning(request, 'Please set a PIN code in your profile settings before accessing POS.')
        return redirect('settings:profile_settings')
    
    # Check if PIN is verified in session
    if not request.session.get('pos_pin_verified', False):
        return redirect('tech_master:verify_pin')
    
    # Optional: Check if PIN verification expired (e.g., after 30 minutes)
    verified_at = request.session.get('pos_pin_verified_at')
    if verified_at:
        from datetime import datetime, timedelta
        try:
            verified_time = datetime.fromisoformat(verified_at)
            if timezone.now() - verified_time > timedelta(minutes=30):
                # PIN expired, clear and redirect
                del request.session['pos_pin_verified']
                del request.session['pos_pin_verified_at']
                messages.warning(request, 'PIN verification expired. Please verify again.')
                return redirect('tech_master:verify_pin')
        except:
            pass
    
    context = {
        'tenant': tenant,
        'active_tab': 'pos',
    }
    return render(request, 'tech_master/pos.html', context)


@login_required
def tech_dashboard(request):
    """TECH MASTER Dashboard - Only for Admin, Tenant Admin, and Manager"""
    user = request.user
    
    # ✅ Cashiers and Sales Agents should not access this page
    if user.role == 'cashier':
        messages.error(request, 'Cashiers are redirected to POS.')
        return redirect('tech_master:pos')
    
    if user.role == 'sales_agent':
        messages.error(request, 'Sales Agents are redirected to their dashboard.')
        return redirect('tech_master:my_sales')
    
    tenant = request.user.tenant
    
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
    }
    return render(request, 'tech_master/dashboard_tech.html', context)


@login_required
def report_dashboard(request):
    """Reports dashboard"""
    context = {
        'tenant': request.user.tenant,
        'active_tab': 'reports',
    }
    return render(request, 'tech_master/reports.html', context)

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
# HOTEL MASTER VIEWS
# ============================================

@login_required
def hotel_dashboard(request):
    """HOTEL MASTER Dashboard"""
    context = {
        'tenant': request.user.tenant,
        'active_tab': 'dashboard',
        'total_rooms': 0,
        'available_rooms': 0,
        'today_bookings': 0,
        'occupancy_rate': 0,
    }
    return render(request, 'hotel_master/dashboard_hotel.html', context)


@login_required
def hotel_rooms(request):
    """Hotel rooms management"""
    context = {'active_tab': 'rooms', 'tenant': request.user.tenant}
    return render(request, 'hotel_master/rooms.html', context)


@login_required
def hotel_add_room(request):
    """Add hotel room"""
    context = {'tenant': request.user.tenant}
    return render(request, 'hotel_master/add_room.html', context)


@login_required
def hotel_bookings(request):
    """Hotel bookings management"""
    context = {'active_tab': 'bookings', 'tenant': request.user.tenant}
    return render(request, 'hotel_master/bookings.html', context)


@login_required
def hotel_new_booking(request):
    """Create new hotel booking"""
    context = {'tenant': request.user.tenant}
    return render(request, 'hotel_master/new_booking.html', context)


@login_required
def hotel_guests(request):
    """Hotel guests management"""
    context = {'active_tab': 'guests', 'tenant': request.user.tenant}
    return render(request, 'hotel_master/guests.html', context)


@login_required
def hotel_checkin(request):
    """Check in guest"""
    context = {'tenant': request.user.tenant}
    return render(request, 'hotel_master/checkin.html', context)


@login_required
def hotel_checkout(request):
    """Check out guest"""
    context = {'tenant': request.user.tenant}
    return render(request, 'hotel_master/checkout.html', context)


# ============================================
# FOOD MASTER VIEWS
# ============================================

@login_required
def food_dashboard(request):
    """FOOD MASTER Dashboard"""
    context = {
        'tenant': request.user.tenant,
        'active_tab': 'dashboard',
    }
    return render(request, 'food_master/dashboard_food.html', context)


@login_required
def food_menu(request):
    """Restaurant menu management"""
    context = {'active_tab': 'menu', 'tenant': request.user.tenant}
    return render(request, 'food_master/menu.html', context)


@login_required
def food_orders(request):
    """Restaurant orders management"""
    context = {'active_tab': 'orders', 'tenant': request.user.tenant}
    return render(request, 'food_master/orders.html', context)


@login_required
def food_tables(request):
    """Restaurant tables management"""
    context = {'active_tab': 'tables', 'tenant': request.user.tenant}
    return render(request, 'food_master/tables.html', context)


@login_required
def food_kitchen(request):
    """Kitchen display"""
    context = {'active_tab': 'kitchen', 'tenant': request.user.tenant}
    return render(request, 'food_master/kitchen.html', context)


# ============================================
# RETAIL MASTER VIEWS
# ============================================

@login_required
def retail_dashboard(request):
    """RETAIL MASTER Dashboard"""
    context = {
        'tenant': request.user.tenant,
        'active_tab': 'dashboard',
    }
    return render(request, 'retail_master/dashboard_retail.html', context)


# ============================================
# HEALTH MASTER VIEWS
# ============================================

@login_required
def health_dashboard(request):
    """HEALTH MASTER Dashboard"""
    context = {
        'tenant': request.user.tenant,
        'active_tab': 'dashboard',
    }
    return render(request, 'health_master/dashboard_health.html', context)


# ============================================
# FASHION MASTER VIEWS
# ============================================

@login_required
def fashion_dashboard(request):
    """FASHION MASTER Dashboard"""
    context = {
        'tenant': request.user.tenant,
        'active_tab': 'dashboard',
    }
    return render(request, 'fashion_master/dashboard_fashion.html', context)


# ============================================
# USER MANAGEMENT VIEWS
# ============================================

@login_required
def user_list(request):
    """List all users"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    users = User.objects.filter(tenant=tenant).order_by('-created_at')
    
    context = {
        'tenant': tenant,
        'users': users,
        'active_tab': 'users',
    }
    return render(request, 'shared/user_list.html', context)


@login_required
def add_user(request):
    """Add new user"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role', 'cashier')
        phone_number = request.POST.get('phone_number', '')
        pin_code = request.POST.get('pin_code', '')
        
        if not username or not password:
            messages.error(request, 'Username and password are required')
            return redirect('add_user')
        
        if User.objects.filter(tenant=tenant, username=username).exists():
            messages.error(request, f'User {username} already exists')
            return redirect('add_user')
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            tenant=tenant,
            role=role,
            phone_number=phone_number,
            pin_code=pin_code,
            is_active=True
        )
        
        messages.success(request, f'User {username} created successfully!')
        return redirect('user_list')
    
    context = {
        'tenant': tenant,
        'roles': User.ROLE_CHOICES,
        'active_tab': 'users',
    }
    return render(request, 'shared/add_user.html', context)

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
    from apps.tech_master.inventory.models import Product, Branch
    from apps.shared.settings.models import SystemSetting
    from django.core.cache import cache
    
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
        
        messages.success(request, 'Settings saved successfully!')
        return redirect('portal:platform_settings')
    
    # GET - Load settings
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
    }
    return render(request, 'shared/platform_settings.html', context)


@login_required
def platform_settings_stats(request):
    """API endpoint for stats refresh"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    from apps.shared.tenants.models import Tenant, ProjectType, SubscriptionPlan
    from apps.shared.users.models import User
    from apps.tech_master.inventory.models import Product, Branch
    
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
    """Manager Dashboard"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    context = {
        'tenant': tenant,
        'active_tab': 'dashboard',
    }
    return render(request, 'tech_master/manager_dashboard.html', context)
