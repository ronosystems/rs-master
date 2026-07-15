# apps/shared/permissions/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import Permission
from django.db import models
from .models import Role, UserRoleAssignment
from apps.shared.users.models import User



@login_required
def role_list(request):
    """List all roles - Filter by tenant's project type"""
    tenant = request.user.tenant
    user = request.user
    
    # Super Admin sees all roles
    if user.is_super_admin:
        roles = Role.objects.all().prefetch_related('permissions', 'users')
        project_type = None
        is_super_admin = True
    else:
        # Tenant Admin sees only roles for their project type
        if not tenant:
            messages.error(request, 'No tenant assigned.')
            return redirect('portal:dashboard')
        
        project_type = tenant.project_type if tenant else None
        is_super_admin = False
        
        if project_type:
            # Get the project type code
            project_code = project_type.code.upper()
            
            # Define which roles are valid for each project type
            # Map project types to their valid role codenames
            project_role_mapping = {
                'TRONIC_MASTER': ['cashier', 'manager', 'sales_agent', 'viewer'],
                'HOTEL_MASTER': ['receptionist', 'hotel_manager', 'manager', 'viewer'],
                'FOOD_MASTER': ['waiter', 'kitchen', 'chef', 'manager', 'viewer'],
                'RETAIL_MASTER': ['retail_sales', 'manager', 'viewer'],
                'HEALTH_MASTER': ['pharmacist', 'nurse', 'doctor', 'manager', 'viewer'],
                'FASHION_MASTER': ['fashion_sales', 'stylist', 'manager', 'viewer'],
            }
            
            # Get valid role codenames for this project
            valid_role_codenames = project_role_mapping.get(project_code, [])
            
            # Always include tenant_admin (global)
            valid_role_codenames.append('tenant_admin')
            
            # Filter roles
            roles = Role.objects.filter(
                models.Q(codename__in=valid_role_codenames) | 
                models.Q(project_types=project_type)
            ).distinct().prefetch_related('permissions', 'users')
            
        else:
            # If no project type, show only global roles
            roles = Role.objects.filter(codename__in=['tenant_admin']).prefetch_related('permissions', 'users')
    
    # Group permissions by model for display
    for role in roles:
        role.permissions_by_model = {}
        for perm in role.permissions.all():
            model_name = perm.content_type.model if perm.content_type else 'other'
            if model_name not in role.permissions_by_model:
                role.permissions_by_model[model_name] = []
            role.permissions_by_model[model_name].append(perm)
    
    context = {
        'roles': roles,
        'total_roles': roles.count(),
        'system_roles': roles.filter(role_type='system').count(),
        'custom_roles': roles.filter(role_type='custom').count(),
        'project_type': project_type,
        'tenant': tenant,
        'is_super_admin': is_super_admin,
        'is_tenant_admin': user.is_tenant_admin,
        'active_tab': 'permissions',
    }
    return render(request, 'shared/permissions/role_list.html', context)


@login_required
def role_create(request):
    """Create a new role - Custom page"""
    user = request.user
    tenant = user.tenant
    
    # Only Super Admin and Tenant Admin can create roles
    if not (user.is_super_admin or user.is_tenant_admin):
        messages.error(request, 'You do not have permission to create roles.')
        return redirect('permissions:role_list')
    
    project_type = None
    if tenant and tenant.project_type:
        project_type = tenant.project_type
    
    if request.method == 'POST':
        name = request.POST.get('name')
        codename = request.POST.get('codename')
        description = request.POST.get('description', '')
        role_type = request.POST.get('role_type', 'custom')
        parent_id = request.POST.get('parent')
        permission_ids = request.POST.getlist('permissions')
        
        if not name or not codename:
            messages.error(request, 'Name and codename are required.')
            return redirect('permissions:role_create')
        
        if Role.objects.filter(codename=codename).exists():
            messages.error(request, f'Role with codename "{codename}" already exists.')
            return redirect('permissions:role_create')
        
        parent = None
        if parent_id:
            parent = get_object_or_404(Role, id=parent_id)
        
        role = Role.objects.create(
            name=name,
            codename=codename,
            description=description,
            role_type=role_type,
            parent=parent,
            is_system_role=False,
            is_active=True,
        )
        
        if permission_ids:
            role.permissions.set(permission_ids)
        
        # Auto-assign current project type (unless Super Admin)
        if not user.is_super_admin and project_type:
            role.project_types.add(project_type)
        
        messages.success(request, f'Role "{name}" created successfully!')
        return redirect('permissions:role_list')
    
    # Get all permissions - Filter by project type
    permissions = Permission.objects.select_related('content_type').order_by(
        'content_type__app_label', 'content_type__model', 'codename'
    )
    
    # If not super admin, filter permissions by project type
    if not user.is_super_admin and project_type:
        project_code = project_type.code.upper()
        
        # Define which models are relevant for each project type
        project_model_mapping = {
            'TRONIC_MASTER': ['product', 'category', 'sale', 'saleitem', 'customer', 'supplier', 'branch', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'HOTEL_MASTER': ['room', 'booking', 'guest', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'FOOD_MASTER': ['product', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'RETAIL_MASTER': ['product', 'category', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'HEALTH_MASTER': ['product', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'FASHION_MASTER': ['product', 'category', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'RENTAL_MASTER': ['property', 'unit', 'tenant', 'payment', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
        }
        
        allowed_models = project_model_mapping.get(project_code, [])
        
        # Filter permissions
        filtered_permissions = []
        for perm in permissions:
            if perm.content_type:
                model_name = perm.content_type.model
                if model_name in allowed_models:
                    filtered_permissions.append(perm)
            else:
                filtered_permissions.append(perm)
        
        permissions = filtered_permissions
    
    # Group permissions by model
    grouped_permissions = {}
    for perm in permissions:
        if perm.content_type:
            model_name = perm.content_type.model
            if model_name not in grouped_permissions:
                grouped_permissions[model_name] = {
                    'model_name': model_name,
                    'permissions': []
                }
            grouped_permissions[model_name]['permissions'].append(perm)
        else:
            if 'other' not in grouped_permissions:
                grouped_permissions['other'] = {
                    'model_name': 'System',
                    'permissions': []
                }
            grouped_permissions['other']['permissions'].append(perm)
    
    roles = Role.objects.filter(is_active=True)
    
    context = {
        'grouped_permissions': grouped_permissions,
        'roles': roles,
        'current_project_type': project_type,
        'is_super_admin': user.is_super_admin,
        'is_tenant_admin': user.is_tenant_admin,
        'active_tab': 'permissions',
        'is_edit': False,
        'role_permission_ids': [],  # Empty list for new role
        'total_permissions': len(permissions),
    }
    return render(request, 'shared/permissions/role_form.html', context)


@login_required
def role_edit(request, role_id):
    """Edit a role - Custom page"""
    user = request.user
    tenant = user.tenant
    role = get_object_or_404(Role, id=role_id)
    
    # Check permissions
    if not (user.is_super_admin or user.is_tenant_admin):
        messages.error(request, 'You do not have permission to edit roles.')
        return redirect('permissions:role_list')
    
    # Tenant Admin can only edit roles for their project type
    if not user.is_super_admin and tenant and tenant.project_type:
        if role.project_types.exists() and not role.project_types.filter(id=tenant.project_type.id).exists():
            messages.error(request, 'You do not have permission to edit this role.')
            return redirect('permissions:role_list')
    
    if role.is_system_role and not user.is_super_admin:
        messages.warning(request, 'System roles cannot be modified.')
    
    # Get project type
    project_type = None
    if tenant and tenant.project_type:
        project_type = tenant.project_type
    
    if request.method == 'POST':
        if not role.is_system_role or user.is_super_admin:
            role.name = request.POST.get('name', role.name)
            role.description = request.POST.get('description', '')
            role.role_type = request.POST.get('role_type', role.role_type)
            role.is_active = request.POST.get('is_active') == 'on'
            
            parent_id = request.POST.get('parent')
            if parent_id:
                role.parent = get_object_or_404(Role, id=parent_id)
            else:
                role.parent = None
            
            permission_ids = request.POST.getlist('permissions')
            role.permissions.set(permission_ids)
            role.save()
            
            messages.success(request, f'Role "{role.name}" updated successfully!')
        else:
            messages.info(request, 'System roles cannot be modified.')
        
        return redirect('permissions:role_list')
    
    # Get all permissions - Filter by project type
    permissions = Permission.objects.select_related('content_type').order_by(
        'content_type__app_label', 'content_type__model', 'codename'
    )
    
    # If not super admin, filter permissions by project type
    if not user.is_super_admin and project_type:
        project_code = project_type.code.upper()
        
        project_model_mapping = {
            'TRONIC_MASTER': ['product', 'category', 'sale', 'saleitem', 'customer', 'supplier', 'branch', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'HOTEL_MASTER': ['room', 'booking', 'guest', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'FOOD_MASTER': ['product', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'RETAIL_MASTER': ['product', 'category', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'HEALTH_MASTER': ['product', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'FASHION_MASTER': ['product', 'category', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'RENTAL_MASTER': ['property', 'unit', 'tenant', 'payment', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
        }
        
        allowed_models = project_model_mapping.get(project_code, [])
        
        filtered_permissions = []
        for perm in permissions:
            if perm.content_type:
                model_name = perm.content_type.model
                if model_name in allowed_models:
                    filtered_permissions.append(perm)
            else:
                filtered_permissions.append(perm)
        
        permissions = filtered_permissions
    
    # Group permissions by model
    grouped_permissions = {}
    for perm in permissions:
        if perm.content_type:
            model_name = perm.content_type.model
            if model_name not in grouped_permissions:
                grouped_permissions[model_name] = {
                    'model_name': model_name,
                    'permissions': []
                }
            grouped_permissions[model_name]['permissions'].append(perm)
        else:
            if 'other' not in grouped_permissions:
                grouped_permissions['other'] = {
                    'model_name': 'System',
                    'permissions': []
                }
            grouped_permissions['other']['permissions'].append(perm)
    
    roles = Role.objects.filter(is_active=True).exclude(id=role.id)
    role_permission_ids = list(role.permissions.values_list('id', flat=True))
    
    context = {
        'role': role,
        'grouped_permissions': grouped_permissions,
        'roles': roles,
        'role_permission_ids': role_permission_ids,
        'current_project_type': project_type,
        'is_system_role': role.is_system_role,
        'is_super_admin': user.is_super_admin,
        'is_tenant_admin': user.is_tenant_admin,
        'is_edit': True,
        'total_permissions': len(permissions),
        'active_tab': 'permissions',
    }
    return render(request, 'shared/permissions/role_form.html', context)


@login_required
def user_roles(request, user_id):
    """Manage user role assignments"""
    user = request.user
    target_user = get_object_or_404(User, id=user_id)
    
    # Check permissions
    if user.is_super_admin:
        pass  # Super Admin can manage any user
    else:
        # Tenant Admin can only manage users in their tenant
        if not user.is_tenant_admin:
            messages.error(request, 'You do not have permission to manage user roles.')
            return redirect('permissions:role_list')
        
        if target_user.tenant != user.tenant:
            messages.error(request, 'You cannot manage users from other tenants.')
            return redirect('permissions:role_list')
    
    if request.method == 'POST':
        role_ids = request.POST.getlist('roles')
        
        # Clear existing active assignments
        UserRoleAssignment.objects.filter(user=target_user, is_active=True).update(is_active=False)
        
        # Add new assignments
        for role_id in role_ids:
            role = get_object_or_404(Role, id=role_id)
            
            # Check if role is applicable to user's tenant
            if not user.is_super_admin and target_user.tenant and target_user.tenant.project_type:
                if role.project_types.exists() and not role.project_types.filter(id=target_user.tenant.project_type.id).exists():
                    continue  # Skip this role if not applicable
            
            UserRoleAssignment.objects.create(
                user=target_user,
                role=role,
                assigned_by=request.user,
                is_active=True,
                notes=f'Assigned by {request.user.username}'
            )
        
        messages.success(request, f'Roles for "{target_user.username}" updated successfully!')
        return redirect('permissions:user_roles', user_id=target_user.id)
    
    # Get available roles for the user's project type
    if user.is_super_admin:
        available_roles = Role.objects.filter(is_active=True)
    else:
        tenant = target_user.tenant
        if tenant and tenant.project_type:
            available_roles = Role.objects.filter(
                models.Q(project_types=tenant.project_type) | models.Q(project_types__isnull=True)
            ).distinct()
        else:
            available_roles = Role.objects.filter(project_types__isnull=True)
    
    assigned_role_ids = UserRoleAssignment.objects.filter(
        user=target_user, 
        is_active=True
    ).values_list('role_id', flat=True)
    
    context = {
        'target_user': target_user,
        'available_roles': available_roles,
        'assigned_role_ids': list(assigned_role_ids),
        'is_super_admin': user.is_super_admin,
        'is_tenant_admin': user.is_tenant_admin,
        'active_tab': 'permissions',
    }
    return render(request, 'shared/permissions/user_roles.html', context)


@login_required
def role_view(request, role_id):
    """View role details and permissions"""
    role = get_object_or_404(Role, id=role_id)
    user = request.user
    
    # Check if user can view this role
    if not user.is_super_admin:
        tenant = user.tenant
        if tenant and tenant.project_type:
            if role.project_types.exists() and not role.project_types.filter(id=tenant.project_type.id).exists():
                messages.error(request, 'You do not have permission to view this role.')
                return redirect('permissions:role_list')
    
    context = {
        'role': role,
        'is_super_admin': user.is_super_admin,
        'active_tab': 'permissions',
    }
    return render(request, 'shared/permissions/role_view.html', context)


@login_required
@require_http_methods(["POST"])
def role_delete(request, role_id):
    """Delete a role"""
    role = get_object_or_404(Role, id=role_id)
    
    if role.is_system_role:
        messages.error(request, 'System roles cannot be deleted.')
        return redirect('permissions:role_list')
    
    if role.users.exists():
        messages.error(request, f'Cannot delete role "{role.name}" as it has users assigned.')
        return redirect('permissions:role_list')
    
    role.delete()
    messages.success(request, f'Role "{role.name}" deleted successfully!')
    return redirect('permissions:role_list')


@login_required
@require_http_methods(["POST"])
def sync_permissions(request):
    """Sync permissions from Django"""
    try:
        from django.core.management import call_command
        call_command('sync_permissions')
        messages.success(request, 'Permissions synced successfully!')
    except Exception as e:
        messages.error(request, f'Error syncing permissions: {str(e)}')
    
    return redirect('permissions:system_permissions')


@login_required
def check_permission(request, permission_codename):
    """API endpoint to check if current user has a permission"""
    has_perm = request.user.has_system_permission(permission_codename)
    return JsonResponse({'has_permission': has_perm})


@login_required
@require_http_methods(["POST"])
def assign_user_role(request, user_id):
    """Assign a role to a user"""
    user = get_object_or_404(User, id=user_id)
    role_id = request.POST.get('role_id')
    
    if not role_id:
        messages.error(request, 'Please select a role.')
        return redirect('permissions:user_roles', user_id=user.id)
    
    role = get_object_or_404(Role, id=role_id)
    
    # Check if already assigned
    if UserRoleAssignment.objects.filter(user=user, role=role, is_active=True).exists():
        messages.warning(request, f'User already has role "{role.name}".')
        return redirect('permissions:user_roles', user_id=user.id)
    
    UserRoleAssignment.objects.create(
        user=user,
        role=role,
        assigned_by=request.user,
    )
    
    messages.success(request, f'Role "{role.name}" assigned to {user.username}.')
    return redirect('permissions:user_roles', user_id=user.id)


@login_required
@require_http_methods(["POST"])
def remove_user_role(request, user_id, role_id):
    """Remove a role from a user"""
    assignment = get_object_or_404(
        UserRoleAssignment,
        user_id=user_id,
        role_id=role_id,
        is_active=True
    )
    
    assignment.is_active = False
    assignment.save()
    
    messages.success(request, f'Role "{assignment.role.name}" removed from {assignment.user.username}.')
    return redirect('permissions:user_roles', user_id=user_id)


@login_required
def get_user_permissions(request):
    """API endpoint to get current user's permissions"""
    if not request.user.is_authenticated:
        return JsonResponse({'permissions': []})
    
    permissions = []
    for perm in request.user.get_user_permissions():
        permissions.append({
            'codename': perm.codename,
            'name': perm.name,
            'action': perm.codename.split('_')[0] if '_' in perm.codename else 'view',
            'model': perm.content_type.model if perm.content_type else None,
        })
    
    return JsonResponse({'permissions': permissions})


@login_required
def get_user_roles(request):
    """API endpoint to get current user's roles"""
    if not request.user.is_authenticated:
        return JsonResponse({'roles': []})
    
    roles = Role.objects.filter(users=request.user, is_active=True)
    role_data = []
    for role in roles:
        role_data.append({
            'id': role.id,
            'name': role.name,
            'codename': role.codename,
            'permissions': role.get_permission_codenames(),
        })
    
    return JsonResponse({'roles': role_data})


@login_required
def system_permissions(request):
    """View system permissions - Filtered by tenant and project type"""
    from django.contrib.auth.models import Permission
    
    user = request.user
    tenant = user.tenant
    
    # Get all permissions
    all_permissions = Permission.objects.select_related('content_type').order_by(
        'content_type__app_label', 'content_type__model', 'codename'
    )
    
    # ============================================
    # FILTER PERMISSIONS BY PROJECT TYPE
    # ============================================
    filtered_permissions = []
    
    if user.is_super_admin:
        # Super Admin sees ALL permissions
        filtered_permissions = all_permissions
    elif tenant and tenant.project_type:
        project_code = tenant.project_type.code.upper()
        
        # Define which models are relevant for each project type
        project_model_mapping = {
            'TRONIC_MASTER': ['product', 'category', 'sale', 'saleitem', 'customer', 'supplier', 'branch', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'HOTEL_MASTER': ['room', 'booking', 'guest', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'FOOD_MASTER': ['product', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'RETAIL_MASTER': ['product', 'category', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'HEALTH_MASTER': ['product', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'FASHION_MASTER': ['product', 'category', 'sale', 'customer', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
            'RENTAL_MASTER': ['property', 'unit', 'tenant', 'payment', 'expense', 'user', 'role', 'settings', 'receiptsetting', 'paymentsetting', 'report'],
        }
        
        allowed_models = project_model_mapping.get(project_code, [])
        
        # Filter permissions
        for perm in all_permissions:
            if perm.content_type:
                model_name = perm.content_type.model
                # Check if this model is allowed for this project
                if model_name in allowed_models or 'user' in allowed_models:
                    filtered_permissions.append(perm)
            else:
                # Include permissions without content_type (like system permissions)
                filtered_permissions.append(perm)
    else:
        # No tenant or project type - show only basic permissions
        basic_models = ['user', 'role', 'settings']
        for perm in all_permissions:
            if perm.content_type and perm.content_type.model in basic_models:
                filtered_permissions.append(perm)
    
    # ============================================
    # GROUP PERMISSIONS BY MODEL
    # ============================================
    grouped_permissions = {}
    for perm in filtered_permissions:
        if perm.content_type:
            model_name = f"{perm.content_type.app_label}.{perm.content_type.model}"
            if model_name not in grouped_permissions:
                grouped_permissions[model_name] = {
                    'app_label': perm.content_type.app_label,
                    'model_name': perm.content_type.model,
                    'permissions': []
                }
            grouped_permissions[model_name]['permissions'].append(perm)
        else:
            if 'other' not in grouped_permissions:
                grouped_permissions['other'] = {
                    'app_label': 'other',
                    'model_name': 'System',
                    'permissions': []
                }
            grouped_permissions['other']['permissions'].append(perm)
    
    # Get first model for default selection
    first_model = None
    first_permissions = []
    if grouped_permissions:
        first_key = list(grouped_permissions.keys())[0]
        first_model = grouped_permissions[first_key]
        first_permissions = first_model['permissions']
    
    context = {
        'grouped_permissions': grouped_permissions,
        'total_permissions': len(filtered_permissions),
        'first_model': first_model,
        'first_permissions': first_permissions,
        'project_code': tenant.project_type.code.upper() if tenant and tenant.project_type else None,
        'tenant': tenant,
        'active_tab': 'permissions',
    }
    return render(request, 'shared/permissions/system_permissions.html', context)


@login_required
def role_assign(request):
    """Assign a role to a user"""
    if not (request.user.is_super_admin or request.user.is_tenant_admin):
        messages.error(request, 'Access denied. Admin only.')
        return redirect('dashboard')
    
    tenant = request.user.tenant
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role_id = request.POST.get('role_id')
        
        if not user_id or not role_id:
            messages.error(request, 'Please select both user and role.')
            return redirect('permissions:role_assign')
        
        user = get_object_or_404(User, id=user_id, tenant=tenant)
        role = get_object_or_404(Role, id=role_id, tenant=tenant)
        
        # Check if assignment already exists
        assignment, created = UserRoleAssignment.objects.get_or_create(
            user=user,
            role=role,
            defaults={'is_active': True}
        )
        
        if created:
            messages.success(request, f'Role "{role.name}" assigned to {user.username} successfully!')
        else:
            assignment.is_active = True
            assignment.save()
            messages.info(request, f'Role "{role.name}" already assigned to {user.username}, activated.')
        
        return redirect('permissions:role_assign')
    
    # GET request - show form
    users = User.objects.filter(tenant=tenant, is_active=True).order_by('username')
    roles = Role.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    # Get current assignments
    assignments = UserRoleAssignment.objects.filter(
        user__tenant=tenant,
        is_active=True
    ).select_related('user', 'role')
    
    context = {
        'users': users,
        'roles': roles,
        'assignments': assignments,
        'tenant': tenant,
        'active_tab': 'roles',
    }
    return render(request, 'shared/permissions/role_assign.html', context)


@login_required
def role_assign_user(request, role_id):
    """Assign a specific role to a user (with role_id in URL)"""
    if not (request.user.is_super_admin or request.user.is_tenant_admin):
        messages.error(request, 'Access denied. Admin only.')
        return redirect('dashboard')
    
    tenant = request.user.tenant
    role = get_object_or_404(Role, id=role_id, tenant=tenant)
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        
        if not user_id:
            messages.error(request, 'Please select a user.')
            return redirect('permissions:role_assign_user', role_id=role.id)
        
        user = get_object_or_404(User, id=user_id, tenant=tenant)
        
        assignment, created = UserRoleAssignment.objects.get_or_create(
            user=user,
            role=role,
            defaults={'is_active': True}
        )
        
        if created:
            messages.success(request, f'Role "{role.name}" assigned to {user.username} successfully!')
        else:
            assignment.is_active = True
            assignment.save()
            messages.info(request, f'Role "{role.name}" already assigned to {user.username}, activated.')
        
        return redirect('permissions:role_list')
    
    users = User.objects.filter(tenant=tenant, is_active=True).order_by('username')
    
    context = {
        'role': role,
        'users': users,
        'tenant': tenant,
        'active_tab': 'roles',
    }
    return render(request, 'shared/permissions/role_assign_user.html', context)