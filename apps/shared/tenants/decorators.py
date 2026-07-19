# apps/shared/tenants/decorators.py

from django.contrib import messages
from django.shortcuts import redirect
from functools import wraps
from .services import TenantLimitService


def check_product_limit(view_func):
    """
    Decorator to check if tenant has reached product limit
    Usage: @check_product_limit
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant = request.user.tenant
        if tenant:
            service = TenantLimitService(tenant)
            if service.is_product_limit_reached():
                # ✅ Store intent in session
                request.session['upgrade_intent'] = {
                    'action': 'add_product',
                    'current_count': service.get_product_count(),
                    'max_limit': service.get_product_limit(),
                    'return_url': request.path
                }
                
                messages.error(
                    request,
                    f'<strong>⚠️ Product Limit Reached!</strong><br>'
                    f'Your current plan allows a maximum of <strong>{service.get_product_limit()}</strong> products. '
                    f'You currently have <strong>{service.get_product_count()}</strong> products.<br><br>'
                    f'Please upgrade your subscription to add more products.'
                )
                return redirect('tenants:upgrade_subscription')
        return view_func(request, *args, **kwargs)
    return wrapper


def check_branch_limit(view_func):
    """
    Decorator to check if tenant has reached branch limit
    Usage: @check_branch_limit
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant = request.user.tenant
        if tenant:
            service = TenantLimitService(tenant)
            if service.is_branch_limit_reached():
                # ✅ Store intent in session
                request.session['upgrade_intent'] = {
                    'action': 'add_branch',
                    'current_count': service.get_branch_count(),
                    'max_limit': service.get_branch_limit(),
                    'return_url': request.path
                }
                
                messages.error(
                    request,
                    f'<strong>⚠️ Branch Limit Reached!</strong><br>'
                    f'Your current plan allows a maximum of <strong>{service.get_branch_limit()}</strong> branches. '
                    f'You currently have <strong>{service.get_branch_count()}</strong> branches.<br><br>'
                    f'Please upgrade your subscription to add more branches.'
                )
                return redirect('tenants:upgrade_subscription')
        return view_func(request, *args, **kwargs)
    return wrapper


def check_user_limit(view_func):
    """
    Decorator to check if tenant has reached user limit
    Usage: @check_user_limit
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant = request.user.tenant
        if tenant:
            service = TenantLimitService(tenant)
            if service.is_user_limit_reached():
                # ✅ Store intent in session
                request.session['upgrade_intent'] = {
                    'action': 'add_user',
                    'current_count': service.get_user_count(),
                    'max_limit': service.get_user_limit(),
                    'return_url': request.path
                }
                
                messages.error(
                    request,
                    f'<strong>⚠️ User Limit Reached!</strong><br>'
                    f'Your current plan allows a maximum of <strong>{service.get_user_limit()}</strong> users. '
                    f'You currently have <strong>{service.get_user_count()}</strong> users.<br><br>'
                    f'Please upgrade your subscription to add more users.'
                )
                return redirect('tenants:upgrade_subscription')
        return view_func(request, *args, **kwargs)
    return wrapper