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
        
        # ============================================
        # GET COUNTS FROM DATABASE
        # ============================================
        user_count = 0
        product_count = 0
        room_count = 0
        branch_count = 0
        
        # Count users
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user_count = User.objects.filter(tenant=tenant, is_active=True).count()
        except:
            pass
        
        # Count products (Tech Master)
        try:
            from apps.tronic_master.models import Product
            product_count = Product.objects.filter(tenant=tenant, is_active=True).count()
        except:
            pass
        
        # ============================================
        # COUNT ROOMS (Hotel Master) - ADD THIS
        # ============================================
        try:
            from apps.hotel_master.models import Room
            room_count = Room.objects.filter(tenant=tenant).count()
        except:
            pass
        
        # Count branches
        try:
            from apps.shared.tenants.models import Branch
            branch_count = Branch.objects.filter(tenant=tenant, is_active=True).count()
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
            
            # Users
            context['tenant_user_limit'] = current_subscription.max_users
            context['tenant_users_count'] = user_count
            context['tenant_users_remaining'] = max(0, current_subscription.max_users - user_count)
            context['tenant_users_percentage'] = (user_count / current_subscription.max_users * 100) if current_subscription.max_users > 0 else 0
            context['tenant_users_at_limit'] = user_count >= current_subscription.max_users
            
            # Products
            context['tenant_product_limit'] = current_subscription.max_products
            context['tenant_products_count'] = product_count
            context['tenant_products_remaining'] = max(0, current_subscription.max_products - product_count)
            context['tenant_products_percentage'] = (product_count / current_subscription.max_products * 100) if current_subscription.max_products > 0 else 0
            context['tenant_products_at_limit'] = product_count >= current_subscription.max_products
            
            # ============================================
            # ROOMS LIMITS (Hotel Master) - ADD THIS
            # ============================================
            # Use max_products as room limit if max_rooms doesn't exist
            room_limit = getattr(current_subscription, 'max_rooms', current_subscription.max_products)
            context['tenant_room_limit'] = room_limit
            context['tenant_rooms_count'] = room_count
            context['tenant_rooms_remaining'] = max(0, room_limit - room_count)
            context['tenant_rooms_percentage'] = (room_count / room_limit * 100) if room_limit > 0 else 0
            context['tenant_rooms_at_limit'] = room_count >= room_limit
            
            # Branches
            context['tenant_branch_limit'] = current_subscription.max_branches
            context['tenant_branches_count'] = branch_count
            context['tenant_branches_remaining'] = max(0, current_subscription.max_branches - branch_count)
            context['tenant_branches_percentage'] = (branch_count / current_subscription.max_branches * 100) if current_subscription.max_branches > 0 else 0
            context['tenant_branches_at_limit'] = branch_count >= current_subscription.max_branches
            
            context['tenant_has_limits'] = True
        else:
            # ✅ Default values when no subscription
            context['tenant_storage_limit'] = 500
            context['tenant_storage_used'] = 0
            context['tenant_storage_remaining'] = 500
            context['tenant_storage_percentage'] = 0
            context['tenant_storage_at_limit'] = False
            
            context['tenant_user_limit'] = 10
            context['tenant_users_count'] = user_count
            context['tenant_users_remaining'] = max(0, 10 - user_count)
            context['tenant_users_percentage'] = (user_count / 10 * 100) if 10 > 0 else 0
            context['tenant_users_at_limit'] = user_count >= 10
            
            context['tenant_product_limit'] = 10000
            context['tenant_products_count'] = product_count
            context['tenant_products_remaining'] = max(0, 10000 - product_count)
            context['tenant_products_percentage'] = (product_count / 10000 * 100) if 10000 > 0 else 0
            context['tenant_products_at_limit'] = product_count >= 10000
            
            # ============================================
            # ROOMS LIMITS (Default) - ADD THIS
            # ============================================
            default_room_limit = 50
            context['tenant_room_limit'] = default_room_limit
            context['tenant_rooms_count'] = room_count
            context['tenant_rooms_remaining'] = max(0, default_room_limit - room_count)
            context['tenant_rooms_percentage'] = (room_count / default_room_limit * 100) if default_room_limit > 0 else 0
            context['tenant_rooms_at_limit'] = room_count >= default_room_limit
            
            context['tenant_branch_limit'] = 5
            context['tenant_branches_count'] = branch_count
            context['tenant_branches_remaining'] = max(0, 5 - branch_count)
            context['tenant_branches_percentage'] = (branch_count / 5 * 100) if 5 > 0 else 0
            context['tenant_branches_at_limit'] = branch_count >= 5
            
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
        'is_tronic_master': False,
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
        context['is_tronic_master'] = code in ['TRONIC_MASTER', 'TECHMASTER', 'PRJ-001']
        context['is_food_master'] = code in ['FOOD_MASTER', 'FOODMASTER', 'PRJ-002']
        context['is_hotel_master'] = code in ['HOTEL_MASTER', 'HOTELMASTER', 'PRJ-003']
        context['is_retail_master'] = code in ['RETAIL_MASTER', 'RETAILMASTER', 'PRJ-004']
        context['is_health_master'] = code in ['HEALTH_MASTER', 'HEALTHMASTER', 'PRJ-005']
        context['is_fashion_master'] = code in ['FASHION_MASTER', 'FASHIONMASTER', 'PRJ-006']
        context['project_under_development'] = not context['is_tronic_master']
    
    return context