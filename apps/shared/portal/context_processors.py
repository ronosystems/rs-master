# apps/shared/portal/context_processors.py

from apps.tronic_master.models import Product, Branch
from apps.shared.users.models import User
from apps.shared.tenants.models import SubscriptionPlan


def user_role(request):
    """Add user role and tenant info to templates"""
    context = {
        # System roles - only 3
        'is_super_admin': False,
        'is_tenant_admin': False,
        'is_regular_user': False,
        # Project type flags
        'tenant': None,
        'project_type': None,
        'project_under_development': False,
        'is_tronic_master': False,
        'is_food_master': False,
        'is_hotel_master': False,
        'is_retail_master': False,
        'is_health_master': False,
        'is_fashion_master': False,
        'is_rental_master': False,
    }
    
    if not request.user or not request.user.is_authenticated:
        return context
    
    user = request.user
    
    # Set role flags using User model properties
    context['is_super_admin'] = user.is_super_admin
    context['is_tenant_admin'] = user.is_tenant_admin
    context['is_regular_user'] = user.is_regular_user
    
    # Get tenant
    tenant = getattr(user, 'tenant', None)
    if tenant:
        context['tenant'] = tenant
        project_type = getattr(tenant, 'project_type', None)
        if project_type:
            context['project_type'] = project_type
            code = project_type.code.upper() if project_type.code else ''
            context['is_tronic_master'] = code in ['TRONIC_MASTER', 'TECHMASTER', 'PRJ-001']
            context['is_food_master'] = code in ['FOOD_MASTER', 'FOODMASTER', 'PRJ-002']
            context['is_hotel_master'] = code in ['HOTEL_MASTER', 'HOTELMASTER', 'PRJ-003']
            context['is_retail_master'] = code in ['RETAIL_MASTER', 'RETAILMASTER', 'PRJ-004']
            context['is_health_master'] = code in ['HEALTH_MASTER', 'HEALTHMASTER', 'PRJ-005']
            context['is_fashion_master'] = code in ['FASHION_MASTER', 'FASHIONMASTER', 'PRJ-006']
            context['is_rental_master'] = code in ['RENTAL_MASTER', 'RENTALMASTER', 'PRJ-007']
            context['project_under_development'] = not context['is_tronic_master']
    
    return context


def tenant_context(request):
    """Add tenant and subscription info to all templates"""
    context = {
        # Tenant limits
        'tenant_has_limits': False,
        'tenant_users_count': 0,
        'tenant_user_limit': 999,
        'tenant_users_remaining': 999,
        'tenant_users_percentage': 0,
        'tenant_users_at_limit': False,
        'tenant_products_count': 0,
        'tenant_product_limit': 999,
        'tenant_products_remaining': 999,
        'tenant_products_percentage': 0,
        'tenant_products_at_limit': False,
        'tenant_branches_count': 0,
        'tenant_branch_limit': 999,
        'tenant_branches_remaining': 999,
        'tenant_branches_percentage': 0,
        'tenant_branches_at_limit': False,
        'tenant_storage_limit': 0,
        'tenant_storage_used': 0,
        'tenant_storage_remaining': 0,
        'tenant_storage_percentage': 0,
        'tenant_storage_at_limit': False,
        'current_subscription': None,
        'project_code': None,
        'project_url': None,
        'is_rental_master': False,
        # System role helpers
        'is_super_admin': False,
        'is_tenant_admin': False,
        'is_regular_user': False,
    }
    
    if not request.user or not request.user.is_authenticated:
        return context
    
    tenant = getattr(request.user, 'tenant', None)
    
    if tenant:
        context['tenant'] = tenant
        context['tenant_id'] = tenant.id
        
        # Get project type
        if hasattr(tenant, 'project_type') and tenant.project_type:
            context['project_type'] = tenant.project_type
            code = tenant.project_type.code.upper()
            context['project_code'] = code
            context['is_rental_master'] = code == 'RENTAL_MASTER'
        
        # ✅ Get subscription plan
        current_subscription = None
        try:
            if hasattr(tenant, 'subscription_plan') and tenant.subscription_plan:
                try:
                    current_subscription = SubscriptionPlan.objects.get(code=tenant.subscription_plan)
                    context['subscription_plan'] = current_subscription
                    context['current_subscription'] = current_subscription
                except SubscriptionPlan.DoesNotExist:
                    pass
        except:
            pass
        
        # ✅ Check subscription status
        context['subscription_restricted'] = False
        try:
            if hasattr(tenant, 'subscription_end') and tenant.subscription_end:
                from django.utils import timezone
                if tenant.subscription_end < timezone.now():
                    context['subscription_restricted'] = True
        except:
            pass


        # ============================================
        # ADD COMPANY LOGO AND SETTINGS
        # ============================================
        try:
            from apps.shared.settings.models import CompanySetting
            company_settings = CompanySetting.objects.filter(tenant=tenant).first()
            if company_settings:
                context['company_settings'] = company_settings
                
                # Logo URL for use in templates
                if company_settings.has_valid_logo():
                    context['tenant_logo_url'] = company_settings.logo.url
                    context['tenant_has_valid_logo'] = True
                else:
                    context['tenant_has_valid_logo'] = False
        except:
            pass
        
        # Fallback to tenant logo if company settings don't have logo
        if not context.get('tenant_has_valid_logo') and tenant.has_valid_logo():
            context['tenant_logo_url'] = tenant.get_logo_url()
            context['tenant_has_valid_logo'] = True


        
        # ✅ CALCULATE TENANT LIMITS
        plan = current_subscription
        
        # User limits
        user_limit = getattr(plan, 'max_users', 999) if plan else 999
        user_count = User.objects.filter(tenant=tenant, is_active=True).count()
        context['tenant_user_limit'] = user_limit
        context['tenant_users_count'] = user_count
        context['tenant_users_remaining'] = max(0, user_limit - user_count)
        context['tenant_users_percentage'] = min(100, (user_count / user_limit * 100) if user_limit > 0 else 0)
        context['tenant_users_at_limit'] = user_count >= user_limit
        
        # Product limits
        product_limit = getattr(plan, 'max_products', 999) if plan else 999
        product_count = Product.objects.filter(tenant=tenant, is_active=True).count()
        context['tenant_product_limit'] = product_limit
        context['tenant_products_count'] = product_count
        context['tenant_products_remaining'] = max(0, product_limit - product_count)
        context['tenant_products_percentage'] = min(100, (product_count / product_limit * 100) if product_limit > 0 else 0)
        context['tenant_products_at_limit'] = product_count >= product_limit
        
        # Branch limits
        branch_limit = getattr(plan, 'max_branches', 999) if plan else 999
        branch_count = Branch.objects.filter(tenant=tenant, is_active=True).count()
        context['tenant_branch_limit'] = branch_limit
        context['tenant_branches_count'] = branch_count
        context['tenant_branches_remaining'] = max(0, branch_limit - branch_count)
        context['tenant_branches_percentage'] = min(100, (branch_count / branch_limit * 100) if branch_limit > 0 else 0)
        context['tenant_branches_at_limit'] = branch_count >= branch_limit
        
        # ✅ Storage limits
        storage_limit = getattr(plan, 'max_storage_gb', 999) if plan else 999
        storage_used = 0
        context['tenant_storage_limit'] = storage_limit
        context['tenant_storage_used'] = storage_used
        context['tenant_storage_remaining'] = max(0, storage_limit - storage_used)
        context['tenant_storage_percentage'] = min(100, (storage_used / storage_limit * 100) if storage_limit > 0 else 0)
        context['tenant_storage_at_limit'] = storage_used >= storage_limit
        
        context['tenant_has_limits'] = True
        
        # ✅ Add system role helpers using User model properties
        user = request.user
        context['is_super_admin'] = user.is_super_admin
        context['is_tenant_admin'] = user.is_tenant_admin
        context['is_regular_user'] = user.is_regular_user
        
    else:
        context['tenant'] = None
        context['tenant_id'] = None
        context['tenant_has_limits'] = False
        context['subscription_restricted'] = False
        context['current_subscription'] = None
    
    return context


def user_role_context(request):
    """Add user role helpers to templates"""
    context = {
        'user_role': None,
        'is_super_admin': False,
        'is_tenant_admin': False,
        'is_regular_user': False,
    }
    
    if request.user and request.user.is_authenticated:
        user = request.user
        context['user_role'] = user.role
        context['is_super_admin'] = user.is_super_admin
        context['is_tenant_admin'] = user.is_tenant_admin
        context['is_regular_user'] = user.is_regular_user
    
    return context


def project_context(request):
    """Add project context to all templates"""
    context = {
        'project_code': None,
        'project_name': None,
        'project_url': None,
        'project_base_template': 'tronic_master/base_tech.html',
    }
    
    if request.user and request.user.is_authenticated:
        # Get project from session
        project_code = request.session.get('project_code')
        project_name = request.session.get('project_name')
        
        if project_code:
            context['project_code'] = project_code
            context['project_name'] = project_name
            
            # ✅ Map project code to URL path
            project_url_map = {
                'TRONIC_MASTER': '/tronic/',
                'HOTEL_MASTER': '/hotel/',
                'FOOD_MASTER': '/food/',
                'RETAIL_MASTER': '/retail/',
                'HEALTH_MASTER': '/health/',
                'FASHION_MASTER': '/fashion/',
                'RENTAL_MASTER': '/rental/',
            }
            context['project_url'] = project_url_map.get(project_code, '/')
            
            # Map project code to base template
            template_map = {
                'TRONIC_MASTER': 'tronic_master/base_tech.html',
                'HOTEL_MASTER': 'hotel_master/base_hotel.html',
                'FOOD_MASTER': 'food_master/base_food.html',
                'RETAIL_MASTER': 'retail_master/base_retail.html',
                'HEALTH_MASTER': 'health_master/base_health.html',
                'FASHION_MASTER': 'fashion_master/base_fashion.html',
                'RENTAL_MASTER': 'rental_master/base_rental.html',
            }
            context['project_base_template'] = template_map.get(project_code, 'tronic_master/base_tech.html')
            
            # Also check tenant for fallback
            tenant = getattr(request.user, 'tenant', None)
            if tenant:
                project_type = getattr(tenant, 'project_type', None)
                if project_type:
                    context['project_type'] = {
                        'code': project_type.code.upper(),
                        'name': project_type.name,
                        'slug': project_type.code.lower(),
                        'icon': getattr(project_type, 'icon', 'fa-building'),
                    }
    
    return context


def permissions_context(request):
    """Add permission checks to all templates"""
    context = {}
    
    if request.user and request.user.is_authenticated:
        user = request.user
        
        # Basic permission checks using has_permission method
        context['can_view_products'] = user.has_permission('view_product')
        context['can_add_product'] = user.has_permission('add_product')
        context['can_change_product'] = user.has_permission('change_product')
        context['can_delete_product'] = user.has_permission('delete_product')
        
        context['can_view_sales'] = user.has_permission('view_sale')
        context['can_add_sale'] = user.has_permission('add_sale')
        context['can_change_sale'] = user.has_permission('change_sale')
        context['can_delete_sale'] = user.has_permission('delete_sale')
        
        context['can_view_rooms'] = user.has_permission('view_room')
        context['can_add_room'] = user.has_permission('add_room')
        context['can_change_room'] = user.has_permission('change_room')
        context['can_delete_room'] = user.has_permission('delete_room')
        
        context['can_view_bookings'] = user.has_permission('view_booking')
        context['can_add_booking'] = user.has_permission('add_booking')
        context['can_change_booking'] = user.has_permission('change_booking')
        context['can_delete_booking'] = user.has_permission('delete_booking')
        
        context['can_view_users'] = user.has_permission('view_user')
        context['can_add_user'] = user.has_permission('add_user')
        context['can_change_user'] = user.has_permission('change_user')
        context['can_delete_user'] = user.has_permission('delete_user')
        
        context['can_view_settings'] = user.has_permission('view_settings')
        context['can_change_settings'] = user.has_permission('change_settings')
        
        # Add user role info
        context['is_super_admin'] = user.is_super_admin
        context['is_tenant_admin'] = user.is_tenant_admin
    
    return context

