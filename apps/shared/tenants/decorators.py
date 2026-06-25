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
                messages.error(
                    request,
                    f'Product limit reached! You can only have {service.get_product_limit()} products. '
                    'Please upgrade your plan.'
                )
                return redirect('product_list')
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
                messages.error(
                    request,
                    f'Branch limit reached! You can only have {service.get_branch_limit()} branches. '
                    'Please upgrade your plan.'
                )
                return redirect('branch_list')
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
                messages.error(
                    request,
                    f'User limit reached! You can only have {service.get_user_limit()} users. '
                    'Please upgrade your plan.'
                )
                return redirect('user_list')
        return view_func(request, *args, **kwargs)
    return wrapper
