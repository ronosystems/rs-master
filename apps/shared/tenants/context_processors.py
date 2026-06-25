# apps/shared/portal/context_processors.py


def subscription_status(request):
    """Add subscription status to templates"""
    context = {
        'subscription_restricted': False,
        'subscription_expired': False,
    }
    
    if not request.user or not request.user.is_authenticated:
        return context
    
    # Check if subscription expired flag is in session
    if request.session.get('subscription_expired', False):
        context['subscription_restricted'] = True
        context['subscription_expired'] = True
    
    return context




def tenant_context(request):
    """Add tenant and subscription info to all templates"""
    context = {}
    
    if not request.user or not request.user.is_authenticated:
        return context
    
    tenant = getattr(request.user, 'tenant', None)
    
    if tenant:
        context['tenant'] = tenant
        context['tenant_id'] = tenant.id
        
        if hasattr(tenant, 'project_type') and tenant.project_type:
            context['project_type'] = tenant.project_type
        
        # ✅ Get subscription plan first
        current_subscription = None
        if hasattr(tenant, 'subscription_plan') and tenant.subscription_plan:
            try:
                from apps.shared.tenants.models import SubscriptionPlan
                current_subscription = SubscriptionPlan.objects.get(code=tenant.subscription_plan)
                context['current_subscription'] = current_subscription
            except:
                pass
        
        # ✅ Now set storage_limit after current_subscription is defined
        storage_used = 0
        storage_limit = current_subscription.max_storage_gb if current_subscription else 1
        
        # ✅ If subscription exists, set all limits
        if current_subscription:
            context['tenant_storage_limit'] = current_subscription.max_storage_gb
            context['tenant_storage_used'] = 0
            context['tenant_storage_remaining'] = current_subscription.max_storage_gb
            context['tenant_storage_percentage'] = 0
            context['tenant_storage_at_limit'] = False
            
            context['tenant_user_limit'] = current_subscription.max_users
            context['tenant_users_count'] = 0
            context['tenant_users_remaining'] = current_subscription.max_users
            context['tenant_users_percentage'] = 0
            context['tenant_users_at_limit'] = False
            
            context['tenant_product_limit'] = current_subscription.max_products
            context['tenant_products_count'] = 0
            context['tenant_products_remaining'] = current_subscription.max_products
            context['tenant_products_percentage'] = 0
            context['tenant_products_at_limit'] = False
            
            context['tenant_branch_limit'] = current_subscription.max_branches
            context['tenant_branches_count'] = 0
            context['tenant_branches_remaining'] = current_subscription.max_branches
            context['tenant_branches_percentage'] = 0
            context['tenant_branches_at_limit'] = False
            
            context['tenant_has_limits'] = True
        else:
            # ✅ Default values when no subscription
            context['tenant_storage_limit'] = 500
            context['tenant_storage_used'] = 0
            context['tenant_storage_remaining'] = 500
            context['tenant_storage_percentage'] = 0
            context['tenant_storage_at_limit'] = False
            
            context['tenant_user_limit'] = 10
            context['tenant_users_count'] = 0
            context['tenant_users_remaining'] = 10
            context['tenant_users_percentage'] = 0
            context['tenant_users_at_limit'] = False
            
            context['tenant_product_limit'] = 10000
            context['tenant_products_count'] = 0
            context['tenant_products_remaining'] = 10000
            context['tenant_products_percentage'] = 0
            context['tenant_products_at_limit'] = False
            
            context['tenant_branch_limit'] = 5
            context['tenant_branches_count'] = 0
            context['tenant_branches_remaining'] = 5
            context['tenant_branches_percentage'] = 0
            context['tenant_branches_at_limit'] = False
            
            context['tenant_has_limits'] = True
    
    return context



def project_type_access(request):
    """Add project type access to templates"""
    context = {
        'project_type': None,
        'has_restaurant': False,
        'has_hotel': False,
        'has_bookings': False,
        'has_kitchen': False,
        'has_fashion': False,
        'has_health': False,
        'has_retail': False,
        'is_tech_master': False,
        'is_food_master': False,
        'is_hotel_master': False,
        'is_retail_master': False,
        'is_health_master': False,
        'is_fashion_master': False,
        'project_under_development': False,
    }
    
    if not request.user or not request.user.is_authenticated:
        return context
    
    if request.user.is_superuser or request.user.role == 'super_admin':
        return context
    
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return context
    
    project_type = getattr(tenant, 'project_type', None)
    if project_type:
        context['project_type'] = project_type
        code = project_type.code.upper()
        context['is_tech_master'] = code in ['TECH_MASTER', 'TECHMASTER', 'PRJ-001']
        context['is_food_master'] = code in ['FOOD_MASTER', 'FOODMASTER', 'PRJ-002']
        context['is_hotel_master'] = code in ['HOTEL_MASTER', 'HOTELMASTER', 'PRJ-003']
        context['is_retail_master'] = code in ['RETAIL_MASTER', 'RETAILMASTER', 'PRJ-004']
        context['is_health_master'] = code in ['HEALTH_MASTER', 'HEALTHMASTER', 'PRJ-005']
        context['is_fashion_master'] = code in ['FASHION_MASTER', 'FASHIONMASTER', 'PRJ-006']
        context['project_under_development'] = not context['is_tech_master']
    
    return context