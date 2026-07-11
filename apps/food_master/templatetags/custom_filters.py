# apps/food_master/templatetags/custom_filters.py

from django import template

register = template.Library()

@register.filter
def status_color(status):
    """Return color class for order status"""
    colors = {
        'pending': 'warning',
        'confirmed': 'info',
        'preparing': 'primary',
        'ready': 'success',
        'served': 'purple',
        'completed': 'success',
        'cancelled': 'danger',
    }
    return colors.get(status, 'secondary')