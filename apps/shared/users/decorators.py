# apps/shared/users/decorators.py

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import user_passes_test


def super_admin_required(function=None, redirect_field_name=REDIRECT_FIELD_NAME, login_url='login'):
    """Decorator to check if user is super admin"""
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated and u.is_super_admin,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    if function:
        return actual_decorator(function)
    return actual_decorator


def tenant_admin_required(function=None, redirect_field_name=REDIRECT_FIELD_NAME, login_url='login'):
    """Decorator to check if user is super admin or tenant admin"""
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated and (u.is_super_admin or u.is_tenant_admin),
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    if function:
        return actual_decorator(function)
    return actual_decorator