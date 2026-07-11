# apps/food_master/templatetags/food_filters.py

from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def sum_attribute(items, attr):
    """Sum a list of dictionaries by attribute"""
    total = Decimal('0.00')
    for item in items:
        try:
            if hasattr(item, attr):
                value = getattr(item, attr, 0)
            else:
                value = item.get(attr, 0)
            total += Decimal(str(value))
        except:
            pass
    return total