# apps/shared/portal/context_processors.py

from apps.tech_master.inventory.models import Product, Branch
from apps.shared.users.models import User
from apps.shared.tenants.models import SubscriptionPlan


def user_role(request):
    """Add user role and tenant info to templates"""
    context = {
        'is_super_admin': False,
        'is_admin': False,
        'is_manager': False,
        'is_cashier': False,
        'is_sales_agent': False,
        'tenant': None,
        'project_type': None,
        'project_under_development': False,
        'is_tech_master': False,
        'is_food_master': False,
        'is_hotel_master': False,
        'is_retail_master': False,
        'is_health_master': False,
        'is_fashion_master': False,
    }
    
    if not request.user or not request.user.is_authenticated:
        return context
    
    user = request.user
    
    # Set role flags
    context['is_super_admin'] = user.is_superuser or user.role == 'super_admin'
    context['is_admin'] = user.role == 'admin'
    context['is_manager'] = user.role == 'manager'
    context['is_cashier'] = user.role == 'cashier'
    context['is_sales_agent'] = user.role == 'sales_agent'
    
    # Get tenant
    tenant = getattr(user, 'tenant', None)
    if tenant:
        context['tenant'] = tenant
        project_type = getattr(tenant, 'project_type', None)
        if project_type:
            context['project_type'] = project_type
            code = project_type.code.upper() if project_type.code else ''
            context['is_tech_master'] = code in ['TECH_MASTER', 'TECHMASTER', 'PRJ-001']
            context['is_food_master'] = code in ['FOOD_MASTER', 'FOODMASTER', 'PRJ-002']
            context['is_hotel_master'] = code in ['HOTEL_MASTER', 'HOTELMASTER', 'PRJ-003']
            context['is_retail_master'] = code in ['RETAIL_MASTER', 'RETAILMASTER', 'PRJ-004']
            context['is_health_master'] = code in ['HEALTH_MASTER', 'HEALTHMASTER', 'PRJ-005']
            context['is_fashion_master'] = code in ['FASHION_MASTER', 'FASHIONMASTER', 'PRJ-006']
            context['project_under_development'] = not context['is_tech_master']
    
    return context


def tenant_context(request):
    """Add tenant and subscription info to all templates"""
    context = {
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
        'current_subscription': None,  # ✅ Add this
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
        
        # ✅ Get subscription plan
        current_subscription = None
        try:
            if hasattr(tenant, 'subscription_plan') and tenant.subscription_plan:
                try:
                    current_subscription = SubscriptionPlan.objects.get(code=tenant.subscription_plan)
                    context['subscription_plan'] = current_subscription
                    context['current_subscription'] = current_subscription  # ✅ Pass as current_subscription
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
        
        # ✅ CALCULATE TENANT LIMITS
        plan = current_subscription  # Use current_subscription
        
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
        storage_used = 0  # Calculate actual usage if needed
        context['tenant_storage_limit'] = storage_limit
        context['tenant_storage_used'] = storage_used
        context['tenant_storage_remaining'] = max(0, storage_limit - storage_used)
        context['tenant_storage_percentage'] = min(100, (storage_used / storage_limit * 100) if storage_limit > 0 else 0)
        context['tenant_storage_at_limit'] = storage_used >= storage_limit
        
        context['tenant_has_limits'] = True
        
        # ✅ Add user role helpers
        context['is_admin'] = request.user.role in ['admin', 'tenant_admin']
        context['is_manager'] = request.user.role == 'manager'
        context['is_cashier'] = request.user.role == 'cashier'
        context['is_sales_agent'] = request.user.role == 'sales_agent'
        
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
        'is_admin': False,
        'is_manager': False,
        'is_cashier': False,
        'is_sales_agent': False,
    }
    
    if request.user and request.user.is_authenticated:
        user = request.user
        context['user_role'] = user.role
        context['is_super_admin'] = user.is_superuser or user.role == 'super_admin'
        context['is_tenant_admin'] = user.role in ['admin', 'tenant_admin']
        context['is_admin'] = user.role in ['admin', 'tenant_admin']
        context['is_manager'] = user.role == 'manager'
        context['is_cashier'] = user.role == 'cashier'
        context['is_sales_agent'] = user.role == 'sales_agent'
    
    return context