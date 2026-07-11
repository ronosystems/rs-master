#!/bin/bash

echo "🔧 Fixing permission_filters conflict..."

# 1. Rename shared permission_filters to permission_helpers
mv apps/shared/permissions/templatetags/permission_filters.py apps/shared/permissions/templatetags/permission_helpers.py 2>/dev/null || echo "File already renamed"

# 2. Update the content
cat > apps/shared/permissions/templatetags/permission_helpers.py << 'EOT'
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
EOT

# 3. Update templates that use the shared permission_filters
echo "Updating templates..."
find templates/ -name "*.html" -type f ! -path "*/food_master/*" -exec grep -l "{% load permission_filters %}" {} \; | while read file; do
    sed -i 's/{% load permission_filters %}/{% load permission_helpers %}/g' "$file"
    echo "Updated: $file"
done

# 4. Clear cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

echo "✅ Done! The food_master permission_filters remains intact."
echo "✅ Shared permission_filters renamed to permission_helpers."
