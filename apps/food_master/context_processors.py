# apps/food_master/context_processors.py

from apps.shared.permissions.models import UserRoleAssignment


def user_permissions(request):
    """Add user permissions to template context"""
    context = {}
    
    if request.user.is_authenticated:
        # Get all permissions for the user
        user_perms = []
        
        if request.user.is_super_admin or request.user.is_tenant_admin:
            # Admins have all permissions
            user_perms = [
                'food_master.can_take_orders',
                'food_master.can_view_orders',
                'food_master.can_process_payments',
                'food_master.can_manage_menu',
                'food_master.can_manage_branches',
                'food_master.can_manage_tables',
                'food_master.can_manage_reservations',
                'food_master.can_manage_customers',
                'food_master.can_view_reports',
                'food_master.can_manage_settings',
                'food_master.can_manage_orders',
            ]
        else:
            # Get user's permissions from role assignments
            assignments = UserRoleAssignment.objects.filter(
                user=request.user,
                is_active=True
            ).select_related('role')
            
            for assignment in assignments:
                role = assignment.role
                for perm in role.permissions.all():
                    perm_str = f'{perm.content_type.app_label}.{perm.codename}'
                    if perm_str.startswith('food_master.') and perm_str not in user_perms:
                        user_perms.append(perm_str)
        
        context['user_permissions'] = user_perms
        
        # Add individual permission checks
        context['can_take_orders'] = 'food_master.can_take_orders' in user_perms
        context['can_view_orders'] = 'food_master.can_view_orders' in user_perms
        context['can_process_payments'] = 'food_master.can_process_payments' in user_perms
        context['can_manage_menu'] = 'food_master.can_manage_menu' in user_perms
        context['can_manage_branches'] = 'food_master.can_manage_branches' in user_perms
        context['can_manage_tables'] = 'food_master.can_manage_tables' in user_perms
        context['can_manage_reservations'] = 'food_master.can_manage_reservations' in user_perms
        context['can_manage_customers'] = 'food_master.can_manage_customers' in user_perms
        context['can_view_reports'] = 'food_master.can_view_reports' in user_perms
        context['can_manage_settings'] = 'food_master.can_manage_settings' in user_perms
        context['can_manage_orders'] = 'food_master.can_manage_orders' in user_perms
    
    return context