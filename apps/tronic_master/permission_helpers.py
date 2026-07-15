# apps/tronic_master/permission_helpers.py

from apps.tronic_master.permissions import TRONIC_MASTER_PERMISSIONS

def get_permission_groups():
    """
    Get all Tech Master permissions grouped by category
    Returns: dict with category as key and list of permissions
    """
    permission_groups = {}
    
    for codename, name in TRONIC_MASTER_PERMISSIONS.items():
        # Extract category from codename
        category = 'Other'
        if 'product' in codename:
            category = 'Products'
        elif 'category' in codename:
            category = 'Categories'
        elif 'branch' in codename:
            category = 'Branches'
        elif 'stock' in codename:
            category = 'Stock'
        elif 'sale' in codename:
            category = 'Sales'
        elif 'staff' in codename:
            category = 'Staff'
        elif 'report' in codename:
            category = 'Reports'
        elif 'setting' in codename:
            category = 'Settings'
        elif 'dashboard' in codename:
            category = 'Dashboard'
        
        if category not in permission_groups:
            permission_groups[category] = []
        
        permission_groups[category].append({
            'codename': codename,
            'name': name,
            'id': codename  # Use codename as ID
        })
    
    return permission_groups