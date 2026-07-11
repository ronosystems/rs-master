from django import template

register = template.Library()

@register.filter
def split(value, arg):
    """Split a string by the given delimiter and return the first part"""
    if not value:
        return ''
    parts = str(value).split(arg)
    return parts[0] if parts else str(value)

@register.filter
def get_first_word(value):
    """Get the first word from a string"""
    if not value:
        return ''
    return str(value).split('_')[0] if '_' in str(value) else str(value)

@register.filter
def get_action_class(value):
    """Get CSS class for permission action"""
    if not value:
        return 'bg-secondary'
    codename = str(value)
    if 'view' in codename:
        return 'bg-primary'
    elif 'add' in codename:
        return 'bg-success'
    elif 'change' in codename:
        return 'bg-warning text-dark'
    elif 'delete' in codename:
        return 'bg-danger'
    elif 'manage' in codename:
        return 'bg-purple'
    elif 'export' in codename:
        return 'bg-info'
    else:
        return 'bg-secondary'

@register.filter
def get_action_display(value):
    """Get display name for permission action"""
    if not value:
        return ''
    codename = str(value)
    if 'view' in codename:
        return 'View'
    elif 'add' in codename:
        return 'Add'
    elif 'change' in codename:
        return 'Change'
    elif 'delete' in codename:
        return 'Delete'
    elif 'manage' in codename:
        return 'Manage'
    elif 'export' in codename:
        return 'Export'
    else:
        return codename.split('_')[0].title() if '_' in codename else codename.title()
