# apps/shared/tenants/templatetags/tenant_filters.py

from django import template
from apps.shared.tenants.models import SubscriptionPlan

register = template.Library()

@register.filter
def get_plan_price(plan_code):
    """Get the price for a subscription plan code"""
    if not plan_code:
        return None
    try:
        plan = SubscriptionPlan.objects.filter(code=plan_code).first()
        if plan:
            return plan.price_monthly
    except:
        pass
    return None
