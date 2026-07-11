# apps/shared/users/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from apps.shared.tenants.models import Tenant
from apps.shared.permissions.models import Role, UserRoleAssignment
from django.utils import timezone
from django.db import models
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


# ============================================
# HELPER FUNCTIONS
# ============================================

def check_super_admin(view_func):
    """Decorator to check if user is super admin"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_super_admin:
            messages.error(request, 'Access denied. Super Admin only.')
            return redirect('portal:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def check_tenant_admin(view_func):
    """Decorator to check if user is tenant admin"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login first.')
            return redirect('login')
        
        if not (request.user.is_super_admin or request.user.is_tenant_admin):
            messages.error(request, 'Access denied. Tenant Admin only.')
            return redirect('portal:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def get_available_roles(user):
    """Get available roles for the user's tenant project type"""
    from apps.shared.permissions.models import Role
    
    if user.is_super_admin:
        return Role.objects.filter(is_active=True)
    
    tenant = user.tenant
    if not tenant:
        return Role.objects.none()
    
    project_type = tenant.project_type
    if project_type:
        # Get roles that apply to this project type OR all projects
        return Role.objects.filter(
            models.Q(project_types=project_type) | models.Q(project_types__isnull=True)
        ).distinct().filter(is_active=True)
    else:
        # If no project type, show only global roles
        return Role.objects.filter(project_types__isnull=True, is_active=True)


# ============================================
# SUPER ADMIN VIEWS - Full System Access
# ============================================

@login_required
@check_super_admin
def super_admin_dashboard(request):
    """Super Admin Dashboard"""
    context = {
        'total_tenants': Tenant.objects.count(),
        'active_tenants': Tenant.objects.filter(status='active').count(),
        'total_users': User.objects.count(),
        'total_super_admins': User.objects.filter(role='super_admin').count(),
        'total_tenant_admins': User.objects.filter(role='admin').count(),
        'active_tab': 'dashboard',
    }
    return render(request, 'shared/super_admin/dashboard.html', context)


# ============================================
# TENANT MANAGEMENT (Super Admin Only)
# ============================================

@login_required
@check_super_admin
def tenant_list(request):
    """List all tenants"""
    tenants = Tenant.objects.all().order_by('-created_at')
    
    search_query = request.GET.get('q', '')
    if search_query:
        tenants = tenants.filter(company_name__icontains=search_query)
    
    paginator = Paginator(tenants, 20)
    page = request.GET.get('page')
    tenants_page = paginator.get_page(page)
    
    context = {
        'tenants': tenants_page,
        'total_tenants': tenants.count(),
        'search_query': search_query,
        'active_tab': 'tenants',
    }
    return render(request, 'shared/super_admin/tenant_list.html', context)


@login_required
@check_super_admin
def tenant_create(request):
    """Create a new tenant"""
    from apps.shared.tenants.models import ProjectType, SubscriptionPlan
    
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        company_address = request.POST.get('company_address')
        company_phone = request.POST.get('company_phone')
        company_email = request.POST.get('company_email')
        project_type_id = request.POST.get('project_type')
        subscription_plan_id = request.POST.get('subscription_plan')
        
        if not company_name:
            messages.error(request, 'Company name is required.')
            return redirect('tenants:tenant_create')
        
        # Create tenant
        tenant = Tenant.objects.create(
            company_name=company_name,
            company_address=company_address,
            company_phone=company_phone,
            company_email=company_email,
            status='active',
        )
        
        # Assign project type
        if project_type_id:
            project_type = get_object_or_404(ProjectType, id=project_type_id)
            tenant.project_type = project_type
            tenant.save()
        
        # Assign subscription plan
        if subscription_plan_id:
            plan = get_object_or_404(SubscriptionPlan, id=subscription_plan_id)
            tenant.subscription_plan = plan.code
            tenant.subscription_start = timezone.now()
            tenant.subscription_end = timezone.now() + timezone.timedelta(days=30)
            tenant.save()
        
        # Create default tenant admin user
        admin_username = f"admin_{tenant.code.lower()}"
        admin_email = f"admin@{tenant.code.lower()}.com"
        admin_password = Tenant.objects.make_random_password(length=12)
        
        admin_user = User.objects.create_user(
            username=admin_username,
            email=admin_email,
            password=admin_password,
            tenant=tenant,
            role='admin',
            is_active=True,
            is_staff=True,
        )
        
        messages.success(
            request, 
            f'Tenant "{company_name}" created successfully! '
            f'Admin user: {admin_username} (Password: {admin_password})'
        )
        return redirect('tenants:tenant_list')
    
    from apps.shared.tenants.models import ProjectType, SubscriptionPlan
    project_types = ProjectType.objects.filter(is_active=True)
    subscription_plans = SubscriptionPlan.objects.filter(is_active=True)
    
    context = {
        'project_types': project_types,
        'subscription_plans': subscription_plans,
        'active_tab': 'tenants',
    }
    return render(request, 'shared/super_admin/tenant_create.html', context)


@login_required
@check_super_admin
def tenant_edit(request, tenant_id):
    """Edit tenant"""
    tenant = get_object_or_404(Tenant, id=tenant_id)
    from apps.shared.tenants.models import ProjectType, SubscriptionPlan
    
    if request.method == 'POST':
        tenant.company_name = request.POST.get('company_name', tenant.company_name)
        tenant.company_address = request.POST.get('company_address', tenant.company_address)
        tenant.company_phone = request.POST.get('company_phone', tenant.company_phone)
        tenant.company_email = request.POST.get('company_email', tenant.company_email)
        tenant.status = request.POST.get('status', tenant.status)
        
        project_type_id = request.POST.get('project_type')
        if project_type_id:
            tenant.project_type = get_object_or_404(ProjectType, id=project_type_id)
        else:
            tenant.project_type = None
        
        subscription_plan_id = request.POST.get('subscription_plan')
        if subscription_plan_id:
            plan = get_object_or_404(SubscriptionPlan, id=subscription_plan_id)
            tenant.subscription_plan = plan.code
        else:
            tenant.subscription_plan = None
        
        tenant.save()
        messages.success(request, f'Tenant "{tenant.company_name}" updated successfully!')
        return redirect('tenants:tenant_list')
    
    project_types = ProjectType.objects.filter(is_active=True)
    subscription_plans = SubscriptionPlan.objects.filter(is_active=True)
    
    context = {
        'tenant': tenant,
        'project_types': project_types,
        'subscription_plans': subscription_plans,
        'active_tab': 'tenants',
    }
    return render(request, 'shared/super_admin/tenant_edit.html', context)


@login_required
@check_super_admin
@require_http_methods(["POST"])
def tenant_delete(request, tenant_id):
    """Delete tenant"""
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    # Prevent deleting tenants with users
    if User.objects.filter(tenant=tenant).exists():
        messages.error(request, f'Cannot delete tenant "{tenant.company_name}" as it has users.')
        return redirect('tenants:tenant_list')
    
    tenant.delete()
    messages.success(request, f'Tenant "{tenant.company_name}" deleted successfully!')
    return redirect('tenants:tenant_list')


@login_required
@check_super_admin
def tenant_assign_project(request, tenant_id):
    """Assign project type to tenant"""
    tenant = get_object_or_404(Tenant, id=tenant_id)
    from apps.shared.tenants.models import ProjectType
    
    if request.method == 'POST':
        project_type_id = request.POST.get('project_type')
        if project_type_id:
            project_type = get_object_or_404(ProjectType, id=project_type_id)
            tenant.project_type = project_type
            tenant.save()
            messages.success(request, f'Project type assigned to "{tenant.company_name}" successfully!')
        else:
            messages.error(request, 'Please select a project type.')
        return redirect('tenants:tenant_list')
    
    project_types = ProjectType.objects.filter(is_active=True)
    
    context = {
        'tenant': tenant,
        'project_types': project_types,
        'active_tab': 'tenants',
    }
    return render(request, 'shared/super_admin/tenant_assign_project.html', context)


@login_required
@check_super_admin
def tenant_assign_subscription(request, tenant_id):
    """Assign subscription plan to tenant"""
    tenant = get_object_or_404(Tenant, id=tenant_id)
    from apps.shared.tenants.models import SubscriptionPlan
    
    if request.method == 'POST':
        subscription_plan_id = request.POST.get('subscription_plan')
        if subscription_plan_id:
            plan = get_object_or_404(SubscriptionPlan, id=subscription_plan_id)
            tenant.subscription_plan = plan.code
            tenant.subscription_start = timezone.now()
            tenant.subscription_end = timezone.now() + timezone.timedelta(days=30)
            tenant.save()
            messages.success(request, f'Subscription assigned to "{tenant.company_name}" successfully!')
        else:
            messages.error(request, 'Please select a subscription plan.')
        return redirect('tenants:tenant_list')
    
    subscription_plans = SubscriptionPlan.objects.filter(is_active=True)
    
    context = {
        'tenant': tenant,
        'subscription_plans': subscription_plans,
        'active_tab': 'tenants',
    }
    return render(request, 'shared/super_admin/tenant_assign_subscription.html', context)


# ============================================
# USER MANAGEMENT (Super Admin & Tenant Admin)
# ============================================

@login_required
@check_tenant_admin
def user_list(request):
    """List users - Super Admin sees all, Tenant Admin sees their tenant"""
    user = request.user
    
    if user.is_super_admin:
        users = User.objects.all().order_by('-created_at')
        tenant = None
        is_super_admin = True
    else:
        tenant = user.tenant
        if not tenant:
            messages.error(request, 'No tenant assigned.')
            return redirect('portal:dashboard')
        users = User.objects.filter(tenant=tenant).order_by('-created_at')
        is_super_admin = False
    
    search_query = request.GET.get('q', '')
    if search_query:
        users = users.filter(
            models.Q(username__icontains=search_query) |
            models.Q(email__icontains=search_query) |
            models.Q(first_name__icontains=search_query) |
            models.Q(last_name__icontains=search_query)
        )
    
    paginator = Paginator(users, 20)
    page = request.GET.get('page')
    users_page = paginator.get_page(page)
    
    context = {
        'users': users_page,
        'tenant': tenant,
        'total_users': users.count(),
        'is_super_admin': is_super_admin,
        'search_query': search_query,
        'active_tab': 'users',
    }
    return render(request, 'shared/users/user_list.html', context)

@login_required
@check_tenant_admin
def user_edit(request, user_id):
    """Edit a user"""
    user = request.user
    edit_user = get_object_or_404(User, id=user_id)
    
    # Get available project roles for the tenant
    available_roles = get_available_roles(user)
    
    # Check if user can edit this user
    if not user.is_super_admin:
        if edit_user.tenant != user.tenant:
            messages.error(request, 'You cannot edit users from other tenants.')
            return redirect('users:user_list')
        if edit_user.role == 'super_admin':
            messages.error(request, 'You cannot edit Super Admin users.')
            return redirect('users:user_list')
    
    # Get current assigned project role
    current_assignment = UserRoleAssignment.objects.filter(
        user=edit_user,
        is_active=True
    ).first()
    current_role_id = current_assignment.role_id if current_assignment else None
    
    if request.method == 'POST':
        # Get all form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        role = request.POST.get('role', edit_user.role)
        selected_role_id = request.POST.get('selected_role')
        
        # Update basic info
        edit_user.first_name = first_name
        edit_user.last_name = last_name
        edit_user.email = email
        edit_user.phone_number = phone_number
        edit_user.is_active = is_active
        
        # Update system role (if allowed)
        if not user.is_super_admin:
            if role == 'super_admin':
                messages.error(request, 'Only Super Admin can assign Super Admin role.')
                return redirect('users:user_edit', user_id=edit_user.id)
            if edit_user.id == user.id and role != edit_user.role:
                messages.error(request, 'You cannot change your own system role.')
                return redirect('users:user_edit', user_id=edit_user.id)
        edit_user.role = role
        
        # ✅ FIX: Update project role - Handle duplicate properly
        if selected_role_id:
            try:
                role_obj = Role.objects.get(id=selected_role_id)
                
                # ✅ First, deactivate ALL existing assignments for this user
                UserRoleAssignment.objects.filter(user=edit_user, is_active=True).update(is_active=False)
                
                # ✅ Then create a new one or reactivate existing
                assignment, created = UserRoleAssignment.objects.get_or_create(
                    user=edit_user,
                    role=role_obj,
                    defaults={
                        'assigned_by': request.user,
                        'is_active': True,
                        'notes': f'Assigned by {request.user.username}'
                    }
                )
                
                # If it already exists but is inactive, reactivate it
                if not created and not assignment.is_active:
                    assignment.is_active = True
                    assignment.assigned_by = request.user
                    assignment.notes = f'Reactivated by {request.user.username}'
                    assignment.save()
                    messages.info(request, f'Reactivated project role: {role_obj.name}')
                elif created:
                    messages.success(request, f'Assigned project role: {role_obj.name}')
                else:
                    messages.info(request, f'Project role {role_obj.name} already assigned')
                    
            except Role.DoesNotExist:
                messages.warning(request, 'Selected role not found.')
        else:
            # ✅ No role selected - deactivate all active assignments
            UserRoleAssignment.objects.filter(user=edit_user, is_active=True).update(is_active=False)
            messages.info(request, 'Removed project role assignment.')
        
        # Update password if provided
        new_password = request.POST.get('new_password', '')
        if new_password:
            confirm_password = request.POST.get('confirm_password', '')
            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return redirect('users:user_edit', user_id=edit_user.id)
            if len(new_password) < 6:
                messages.error(request, 'Password must be at least 6 characters.')
                return redirect('users:user_edit', user_id=edit_user.id)
            edit_user.set_password(new_password)
            messages.info(request, 'Password updated successfully!')
        
        # Save the user
        edit_user.save()
        
        messages.success(request, f'User "{edit_user.username}" updated successfully!')
        return redirect('users:user_list')
    
    # Prepare project role choices for the form
    role_choices = []
    for role_obj in available_roles:
        role_choices.append({
            'id': role_obj.id,
            'name': role_obj.name,
            'codename': role_obj.codename,
            'is_system': role_obj.is_system_role,
            'selected': role_obj.id == current_role_id,
        })
    
    # System roles for the dropdown
    if user.is_super_admin:
        system_roles = [
            ('super_admin', 'Super Admin'),
            ('admin', 'Admin'),
            ('user', 'User'),
        ]
    else:
        system_roles = [
            ('admin', 'Admin'),
            ('user', 'User'),
        ]
    
    context = {
        'edit_user': edit_user,
        'system_roles': system_roles,
        'available_roles': role_choices,
        'current_role_id': current_role_id,
        'is_super_admin': user.is_super_admin,
        'active_tab': 'users',
    }
    return render(request, 'shared/users/user_edit.html', context)


@login_required
@check_tenant_admin
def user_create(request):
    """Create a new user"""
    user = request.user
    selected_tenant_id = None
    
    # Get available project roles for the tenant
    available_roles = get_available_roles(user)
    
    if user.is_super_admin:
        # Super Admin can choose tenant
        tenants = Tenant.objects.filter(is_active=True)
        selected_tenant_id = request.POST.get('tenant') or request.GET.get('tenant')
        if selected_tenant_id:
            tenant = get_object_or_404(Tenant, id=selected_tenant_id)
            if tenant and tenant.project_type:
                available_roles = Role.objects.filter(
                    models.Q(project_types=tenant.project_type) | models.Q(project_types__isnull=True)
                ).distinct().filter(is_active=True)
            else:
                available_roles = Role.objects.filter(project_types__isnull=True, is_active=True)
        else:
            tenant = None
    else:
        tenant = user.tenant
        if not tenant:
            messages.error(request, 'No tenant assigned.')
            return redirect('portal:dashboard')
        tenants = None
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        role = request.POST.get('role', 'user')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        phone_number = request.POST.get('phone_number', '')
        is_active = request.POST.get('is_active') == 'on'
        selected_role_id = request.POST.get('selected_role')
        
        # Validation
        if not username or not email or not password:
            messages.error(request, 'Username, email, and password are required.')
            return redirect('users:user_create')
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return redirect('users:user_create')
        
        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return redirect('users:user_create')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" is already taken.')
            return redirect('users:user_create')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" is already registered.')
            return redirect('users:user_create')
        
        # Prevent non-super-admin from creating super_admin or admin
        if role in ['super_admin', 'admin'] and not user.is_super_admin:
            messages.error(request, 'Only Super Admin can create Admin or Super Admin users.')
            return redirect('users:user_create')
        
        # If tenant not set, use user's tenant
        if not tenant and not user.is_super_admin:
            tenant = user.tenant
        
        if not tenant:
            messages.error(request, 'Please select a tenant.')
            return redirect('users:user_create')
        
        try:
            with transaction.atomic():
                # Create user with system role
                new_user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    tenant=tenant,
                    role=role,
                    is_active=is_active,
                    is_staff=True if role in ['super_admin', 'admin'] else False,
                    is_superuser=True if role == 'super_admin' else False,
                )
                
                # ✅ Assign project role - Use get_or_create
                if selected_role_id:
                    try:
                        role_obj = Role.objects.get(id=selected_role_id)
                        # ✅ Use get_or_create to avoid duplicate
                        assignment, created = UserRoleAssignment.objects.get_or_create(
                            user=new_user,
                            role=role_obj,
                            defaults={
                                'assigned_by': request.user,
                                'is_active': True,
                                'notes': f'Assigned by {request.user.username}'
                            }
                        )
                        if created:
                            logger.info(f"Assigned project role {role_obj.name} to {new_user.username}")
                        else:
                            # If it already exists but is inactive, reactivate it
                            if not assignment.is_active:
                                assignment.is_active = True
                                assignment.assigned_by = request.user
                                assignment.notes = f'Reactivated by {request.user.username}'
                                assignment.save()
                                logger.info(f"Reactivated project role {role_obj.name} for {new_user.username}")
                    except Role.DoesNotExist:
                        logger.warning(f"Role ID {selected_role_id} not found")
                
                messages.success(request, f'User "{username}" created successfully!')
                return redirect('users:user_list')
                
        except Exception as e:
            messages.error(request, f'Error creating user: {str(e)}')
            return redirect('users:user_create')
    
    # Prepare project role choices for the form
    role_choices = []
    for role_obj in available_roles:
        role_choices.append({
            'id': role_obj.id,
            'name': role_obj.name,
            'codename': role_obj.codename,
            'is_system': role_obj.is_system_role,
        })
    
    # System roles for the dropdown
    if user.is_super_admin:
        system_roles = [
            ('super_admin', 'Super Admin'),
            ('admin', 'Admin'),
            ('user', 'User'),
        ]
    else:
        system_roles = [
            ('user', 'User'),
        ]
    
    context = {
        'tenants': tenants,
        'selected_tenant_id': selected_tenant_id if user.is_super_admin else None,
        'system_roles': system_roles,
        'available_roles': role_choices,
        'tenant': tenant,
        'is_super_admin': user.is_super_admin,
        'active_tab': 'users',
    }
    return render(request, 'shared/users/user_create.html', context)


@login_required
@check_tenant_admin
@require_http_methods(["POST"])
def user_delete(request, user_id):
    """Delete a user"""
    user = request.user
    delete_user = get_object_or_404(User, id=user_id)
    
    # Prevent deleting self
    if delete_user == user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('users:user_list')
    
    # Check permissions
    if not user.is_super_admin:
        if delete_user.tenant != user.tenant:
            messages.error(request, 'You cannot delete users from other tenants.')
            return redirect('users:user_list')
        if delete_user.role == 'super_admin':
            messages.error(request, 'You cannot delete Platform Admin users.')
            return redirect('users:user_list')
    
    delete_user.delete()
    messages.success(request, f'User "{delete_user.username}" deleted successfully!')
    return redirect('users:user_list')


@login_required
@check_tenant_admin
@require_http_methods(["POST"])
def user_toggle_status(request, user_id):
    """Toggle user active status"""
    user = request.user
    toggle_user = get_object_or_404(User, id=user_id)
    
    # Check permissions
    if not user.is_super_admin:
        if toggle_user.tenant != user.tenant:
            messages.error(request, 'You cannot manage users from other tenants.')
            return redirect('users:user_list')
        if toggle_user.role == 'super_admin':
            messages.error(request, 'You cannot manage Platform Admin users.')
            return redirect('users:user_list')
    
    toggle_user.is_active = not toggle_user.is_active
    toggle_user.save()
    
    status = "activated" if toggle_user.is_active else "deactivated"
    messages.success(request, f'User "{toggle_user.username}" has been {status}!')
    return redirect('users:user_list')


# ============================================
# ROLE MANAGEMENT (Tenant Admin Only)
# ============================================

@login_required
@check_tenant_admin
def role_list(request):
    """List roles for the tenant"""
    from apps.shared.permissions.models import Role
    
    user = request.user
    
    if user.is_super_admin:
        roles = Role.objects.all()
    else:
        tenant = user.tenant
        if not tenant:
            messages.error(request, 'No tenant assigned.')
            return redirect('portal:dashboard')
        project_type = tenant.project_type
        if project_type:
            roles = Role.objects.filter(
                models.Q(project_types=project_type) | models.Q(project_types__isnull=True)
            ).distinct()
        else:
            roles = Role.objects.filter(project_types__isnull=True)
    
    context = {
        'roles': roles,
        'is_super_admin': user.is_super_admin,
        'active_tab': 'roles',
    }
    return render(request, 'shared/users/role_list.html', context)