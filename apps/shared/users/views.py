# apps/shared/users/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.db.models import Q
from django.db.models import Sum
import logging

from .models import User, UserActivityLog
from apps.shared.tenants.models import Tenant, SyncQueue

logger = logging.getLogger(__name__)


def has_user_management_access(user):
    """Check if user has permission to manage users"""
    # Super Admin has FULL access to everything
    if user.is_superuser:
        return True, 'full'
    # Tenant Admin has full access to their tenant
    if user.role in ['admin', 'tenant_admin']:
        return True, 'full'
    # Manager has limited access (only agents and cashiers)
    elif user.role == 'manager':
        return True, 'limited'
    return False, None


def get_accessible_tenants(user):
    """Get tenants the user can manage"""
    if user.is_superuser:
        return Tenant.objects.all().order_by('company_name')
    elif user.role in ['admin', 'tenant_admin', 'manager'] and user.tenant:
        return Tenant.objects.filter(id=user.tenant.id)
    return Tenant.objects.none()


@login_required
def user_list(request):
    """List all users - Super Admin sees all, others see their tenant"""
    has_access, access_type = has_user_management_access(request.user)
    
    if not has_access:
        messages.error(request, 'Access denied. Only Admins and Managers can manage users.')
        return redirect('dashboard')
    
    # ✅ SUPER ADMIN - See ALL users across ALL tenants
    if request.user.is_superuser:
        users = User.objects.all().order_by('-created_at')
        tenant = None
        is_admin = True
        is_manager = False
        is_super_admin = True
    else:
        # ✅ Regular users - only see their tenant
        tenant = request.user.tenant
        if not tenant:
            messages.error(request, 'No tenant assigned to your account.')
            return redirect('dashboard')
        
        if access_type == 'full':
            users = User.objects.filter(tenant=tenant).order_by('-created_at')
            is_admin = True
            is_manager = False
        else:
            users = User.objects.filter(
                tenant=tenant,
                role__in=['cashier', 'sales_agent']
            ).order_by('-created_at')
            is_admin = False
            is_manager = True
        is_super_admin = False
    
    # ✅ Search functionality
    search_query = request.GET.get('q', '')
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
    
    # ✅ Role filter
    role_filter = request.GET.get('role', '')
    if role_filter:
        users = users.filter(role=role_filter)
    
    context = {
        'tenant': tenant,
        'users': users,
        'active_tab': 'users',
        'access_type': access_type,
        'is_admin': is_admin,
        'is_manager': is_manager,
        'is_super_admin': is_super_admin,
        'search_query': search_query,
        'role_filter': role_filter,
        'total_users': users.count(),
    }
    return render(request, 'shared/user_list.html', context)


@login_required
def add_user(request):
    """Add new user - Super Admin can add to any tenant"""
    has_access, access_type = has_user_management_access(request.user)
    
    if not has_access:
        messages.error(request, 'Access denied. Only Admins and Managers can add users.')
        return redirect('dashboard')
    
    # ✅ SUPER ADMIN - Can add users to ANY tenant
    if request.user.is_superuser:
        # Get selected tenant from GET or POST
        selected_tenant_id = request.GET.get('tenant_id') or request.POST.get('tenant_id')
        
        if request.method == 'POST':
            if selected_tenant_id:
                tenant = get_object_or_404(Tenant, id=selected_tenant_id)
            else:
                messages.error(request, 'Please select a tenant.')
                return redirect('users:add_user')
        elif request.method == 'GET' and not selected_tenant_id:
            # Show tenant selection for Super Admin
            tenants = Tenant.objects.all().order_by('company_name')
            context = {
                'tenants': tenants,
                'is_super_admin': True,
                'active_tab': 'users',
            }
            return render(request, 'shared/select_tenant_for_user.html', context)
        else:
            tenant = get_object_or_404(Tenant, id=selected_tenant_id)
    else:
        # ✅ Regular users - add to their own tenant
        tenant = request.user.tenant
        if not tenant:
            messages.error(request, 'No tenant assigned to your account.')
            return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        role = request.POST.get('role', 'cashier')
        phone_number = request.POST.get('phone_number', '')
        pin_code = request.POST.get('pin_code', '')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        require_pin = request.POST.get('require_pin_for_pos') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        
        # Validate
        if not username or not password:
            messages.error(request, 'Username and password are required')
            return redirect('users:add_user')
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('users:add_user')
        
        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return redirect('users:add_user')
        
        # Manager can only add cashiers and sales_agents
        if access_type == 'limited' and role not in ['cashier', 'sales_agent']:
            messages.error(request, 'Managers can only add Cashiers and Sales Agents.')
            return redirect('users:add_user')
        
        if User.objects.filter(tenant=tenant, username=username).exists():
            messages.error(request, f'User {username} already exists')
            return redirect('users:add_user')
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        user.tenant = tenant
        user.role = role
        user.phone_number = phone_number
        user.pin_code = pin_code
        user.require_pin_for_pos = require_pin
        user.is_active = is_active
        user.save()
        
        # Log activity
        UserActivityLog.log_activity(
            user=request.user,
            action='user_created',
            details={
                'created_user': username,
                'role': role,
                'tenant': tenant.company_name,
            },
            request=request
        )
        
        # Queue sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='User',
                    object_id=str(user.id),
                    operation='CREATE',
                    data={
                        'id': user.id,
                        'username': username,
                        'email': email,
                        'first_name': first_name,
                        'last_name': last_name,
                        'role': role,
                        'phone_number': phone_number,
                        'pin_code': pin_code,
                        'require_pin_for_pos': require_pin,
                        'is_active': is_active,
                        'tenant_id': tenant.id,
                    },
                    priority=7
                )
                logger.debug(f"✅ Queued User creation sync: {username}")
            except Exception as e:
                logger.error(f"Failed to queue User creation sync: {e}")
        
        messages.success(request, f'User {username} created successfully!')
        return redirect('users:user_list')
    
    # Role choices based on access type
    if access_type == 'full':
        roles = [
            ('admin', 'Tenant Admin'),
            ('manager', 'Manager'),
            ('cashier', 'Cashier'),
            ('sales_agent', 'Sales Agent'),
        ]
    else:
        roles = [
            ('cashier', 'Cashier'),
            ('sales_agent', 'Sales Agent'),
        ]
    
    context = {
        'tenant': tenant,
        'roles': roles,
        'active_tab': 'users',
        'access_type': access_type,
        'is_admin': access_type == 'full',
        'is_manager': access_type == 'limited',
        'is_super_admin': request.user.is_superuser,
        'all_tenants': Tenant.objects.all() if request.user.is_superuser else [],
    }
    return render(request, 'shared/add_user.html', context)


@login_required
def edit_user(request, user_id):
    """Edit user"""
    has_access, access_type = has_user_management_access(request.user)
    
    if not has_access:
        messages.error(request, 'Access denied. Only Admins and Managers can edit users.')
        return redirect('dashboard')
    
    # Super Admin can edit ANY user
    if request.user.is_superuser:
        edit_user = get_object_or_404(User, id=user_id)
        tenant = edit_user.tenant
    else:
        tenant = request.user.tenant
        if not tenant:
            messages.error(request, 'No tenant assigned')
            return redirect('dashboard')
        edit_user = get_object_or_404(User, id=user_id, tenant=tenant)
    
    # Manager can only edit cashiers and sales_agents
    if access_type == 'limited' and edit_user.role not in ['cashier', 'sales_agent']:
        messages.error(request, 'Managers can only edit Cashiers and Sales Agents.')
        return redirect('users:user_list')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        phone_number = request.POST.get('phone_number', '')
        pin_code = request.POST.get('pin_code', '')
        role = request.POST.get('role', edit_user.role)
        is_active = request.POST.get('is_active') == 'on'
        require_pin = request.POST.get('require_pin_for_pos') == 'on'
        
        old_data = {
            'username': edit_user.username,
            'email': edit_user.email,
            'role': edit_user.role,
            'phone_number': edit_user.phone_number,
            'is_active': edit_user.is_active,
        }
        
        if access_type == 'limited':
            if role not in ['cashier', 'sales_agent']:
                messages.error(request, 'Managers can only assign Cashier or Sales Agent roles.')
                return redirect('users:edit_user', user_id=edit_user.id)
        
        if User.objects.filter(tenant=tenant, username=username).exclude(id=edit_user.id).exists():
            messages.error(request, f'Username "{username}" is already taken.')
            return redirect('users:edit_user', user_id=edit_user.id)
        
        edit_user.username = username
        edit_user.email = email
        edit_user.first_name = first_name
        edit_user.last_name = last_name
        edit_user.phone_number = phone_number
        edit_user.pin_code = pin_code
        edit_user.role = role
        edit_user.is_active = is_active
        edit_user.require_pin_for_pos = require_pin
        
        if request.POST.get('password'):
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            if password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return redirect('users:edit_user', user_id=edit_user.id)
            if len(password) < 6:
                messages.error(request, 'Password must be at least 6 characters.')
                return redirect('users:edit_user', user_id=edit_user.id)
            edit_user.set_password(password)
        
        edit_user.save()
        
        UserActivityLog.log_activity(
            user=request.user,
            action='user_updated',
            details={
                'updated_user': username,
                'changes': old_data,
                'tenant': tenant.company_name if tenant else 'System',
            },
            request=request
        )
        
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant.id if tenant else None,
                    model_name='User',
                    object_id=str(edit_user.id),
                    operation='UPDATE',
                    data={
                        'id': edit_user.id,
                        'username': username,
                        'email': email,
                        'first_name': first_name,
                        'last_name': last_name,
                        'role': role,
                        'phone_number': phone_number,
                        'pin_code': pin_code,
                        'require_pin_for_pos': require_pin,
                        'is_active': is_active,
                        'previous_data': old_data,
                        'tenant_id': tenant.id if tenant else None,
                    },
                    priority=7
                )
                logger.debug(f"✅ Queued User update sync: {username}")
            except Exception as e:
                logger.error(f"Failed to queue User update sync: {e}")
        
        messages.success(request, f'User {edit_user.username} updated successfully!')
        return redirect('users:user_list')
    
    if access_type == 'full':
        roles = [
            ('admin', 'Tenant Admin'),
            ('manager', 'Manager'),
            ('cashier', 'Cashier'),
            ('sales_agent', 'Sales Agent'),
        ]
    else:
        roles = [
            ('cashier', 'Cashier'),
            ('sales_agent', 'Sales Agent'),
        ]
    
    context = {
        'edit_user': edit_user,
        'user': request.user,
        'tenant': tenant,
        'roles': roles,
        'active_tab': 'users',
        'access_type': access_type,
        'is_admin': access_type == 'full',
        'is_manager': access_type == 'limited',
        'is_super_admin': request.user.is_superuser,
    }
    return render(request, 'shared/edit_user.html', context)


@login_required
def delete_user(request, user_id):
    """Delete user"""
    has_access, access_type = has_user_management_access(request.user)
    
    if not has_access:
        messages.error(request, 'Access denied. Only Admins and Managers can delete users.')
        return redirect('dashboard')
    
    # Super Admin can delete ANY user
    if request.user.is_superuser:
        user = get_object_or_404(User, id=user_id)
        tenant = user.tenant
    else:
        tenant = request.user.tenant
        if not tenant:
            messages.error(request, 'No tenant assigned')
            return redirect('dashboard')
        user = get_object_or_404(User, id=user_id, tenant=tenant)
    
    if access_type == 'limited' and user.role not in ['cashier', 'sales_agent']:
        messages.error(request, 'Managers can only delete Cashiers and Sales Agents.')
        return redirect('users:user_list')
    
    if user == request.user:
        messages.error(request, 'You cannot delete your own account')
        return redirect('users:user_list')
    
    username = user.username
    
    UserActivityLog.log_activity(
        user=request.user,
        action='user_deleted',
        details={
            'deleted_user': username,
            'role': user.role,
            'tenant': tenant.company_name if tenant else 'System',
        },
        request=request
    )
    
    if getattr(settings, 'OFFLINE_MODE', False):
        try:
            SyncQueue.objects.create(
                tenant_id=tenant.id if tenant else None,
                model_name='User',
                object_id=str(user.id),
                operation='DELETE',
                data={
                    'id': user.id,
                    'username': username,
                    'email': user.email,
                    'tenant_id': tenant.id if tenant else None,
                },
                priority=7
            )
            logger.debug(f"✅ Queued User deletion sync: {username}")
        except Exception as e:
            logger.error(f"Failed to queue User deletion sync: {e}")
    
    user.delete()
    messages.success(request, f'User {username} deleted successfully!')
    return redirect('users:user_list')


@login_required
def toggle_user_status(request, user_id):
    """Activate/Deactivate user"""
    has_access, access_type = has_user_management_access(request.user)
    
    if not has_access:
        messages.error(request, 'Access denied. Only Admins and Managers can manage users.')
        return redirect('dashboard')
    
    # Super Admin can toggle ANY user
    if request.user.is_superuser:
        user = get_object_or_404(User, id=user_id)
        tenant = user.tenant
    else:
        tenant = request.user.tenant
        if not tenant:
            messages.error(request, 'No tenant assigned')
            return redirect('dashboard')
        user = get_object_or_404(User, id=user_id, tenant=tenant)
    
    if access_type == 'limited' and user.role not in ['cashier', 'sales_agent']:
        messages.error(request, 'Managers can only manage Cashiers and Sales Agents.')
        return redirect('users:user_list')
    
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account')
        return redirect('users:user_list')
    
    user.is_active = not user.is_active
    user.save()
    
    status = "activated" if user.is_active else "deactivated"
    
    UserActivityLog.log_activity(
        user=request.user,
        action='user_updated',
        details={
            'updated_user': user.username,
            'status_change': status,
            'tenant': tenant.company_name if tenant else 'System',
        },
        request=request
    )
    
    if getattr(settings, 'OFFLINE_MODE', False):
        try:
            SyncQueue.objects.create(
                tenant_id=tenant.id if tenant else None,
                model_name='User',
                object_id=str(user.id),
                operation='UPDATE',
                data={
                    'id': user.id,
                    'username': user.username,
                    'is_active': user.is_active,
                    'tenant_id': tenant.id if tenant else None,
                },
                priority=7
            )
            logger.debug(f"✅ Queued User status update sync: {user.username}")
        except Exception as e:
            logger.error(f"Failed to queue User status update sync: {e}")
    
    messages.success(request, f'User {user.username} has been {status}!')
    return redirect('users:user_list')


@login_required
def user_profile(request, user_id=None):
    """View user profile"""
    if user_id:
        has_access, access_type = has_user_management_access(request.user)
        
        if not has_access:
            messages.error(request, 'Access denied')
            return redirect('dashboard')
        
        # Super Admin can view ANY user
        if request.user.is_superuser:
            profile_user = get_object_or_404(User, id=user_id)
        else:
            tenant = request.user.tenant
            if not tenant:
                messages.error(request, 'No tenant assigned')
                return redirect('dashboard')
            profile_user = get_object_or_404(User, id=user_id, tenant=tenant)
        
        if access_type == 'limited' and profile_user.role not in ['cashier', 'sales_agent']:
            messages.error(request, 'Managers can only view Cashiers and Sales Agents.')
            return redirect('users:user_list')
    else:
        profile_user = request.user
    
    # Get user statistics
    from apps.tech_master.sales.models import Sale
    from apps.tech_master.inventory.models import ProductUnit
    
    total_sales = Sale.objects.filter(cashier=profile_user).count()
    total_revenue = Sale.objects.filter(cashier=profile_user).aggregate(
        total=Sum('total')
    )['total'] or 0
    
    assigned_units = ProductUnit.objects.filter(
        current_owner=profile_user,
        status__in=['available', 'reserved']
    ).count()
    
    sold_units = ProductUnit.objects.filter(
        current_owner=profile_user,
        status='sold'
    ).count()
    
    recent_activity = UserActivityLog.objects.filter(
        user=profile_user
    ).order_by('-created_at')[:10]
    
    context = {
        'profile_user': profile_user,
        'is_own_profile': profile_user == request.user,
        'tenant': request.user.tenant,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'assigned_units': assigned_units,
        'sold_units': sold_units,
        'recent_activity': recent_activity,
    }
    return render(request, 'shared/user_profile.html', context)