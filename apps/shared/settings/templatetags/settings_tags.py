# apps/shared/settings/templatetags/settings_tags.py

from django import template
from django.conf import settings
from apps.shared.settings.models import SystemSetting

register = template.Library()

@register.simple_tag
def get_platform_logo():
    """Get platform logo path"""
    return SystemSetting.get('platform_logo', '')

@register.simple_tag
def get_platform_name():
    """Get platform name"""
    return SystemSetting.get('platform_name', 'RS Master Platform')

@register.simple_tag
def get_platform_setting(key, default=''):
    """Get any platform setting"""
    return SystemSetting.get(key, default)