# apps/fashion_master/views_staff.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone

from apps.shared.users.models import User
from apps.tech_master.models import Branch
from .models import FashionStaff, FashionStaffAttendance, FashionStaffLeave, FashionRole


# ============================================
# STAFF LIST VIEW
# ============================================

@login_required
def staff_list(request):
    """List all fashion staff"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    staff = FashionStaff.objects.filter(tenant=tenant).order_by('name')
    
    # Filters
    search = request.GET.get('search', '')
    role = request.GET.get('role', '')
    branch_id = request.GET.get('branch', '')
    status = request.GET.get('status', '')
    
    if search:
        staff = staff.filter(
            Q(name__icontains=search) |
            Q(phone_number__icontains=search) |
            Q(email__icontains=search)
        )
    if role:
        staff = staff.filter(role=role)
    if branch_id:
        staff = staff.filter(branch_id=branch_id)
    if status:
        staff = staff.filter(is_active=(status == 'active'))
    
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    paginator = Paginator(staff, 20)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    context = {
        'tenant': tenant,
        'staff': page_obj,
        'branches': branches,
        'roles': FashionStaff.ROLE_CHOICES,
        'search': search,
        'role_filter': role,
        'branch_filter': branch_id,
        'status_filter': status,
        'active_tab': 'staff',
    }
    return render(request, 'fashion_master/staff_list.html', context)


# ============================================
# STAFF DETAIL VIEW
# ============================================

@login_required
def staff_detail(request, staff_id):
    """View fashion staff details"""
    tenant = request.user.tenant
    staff = get_object_or_404(FashionStaff, id=staff_id, tenant=tenant)
    
    context = {
        'tenant': tenant,
        'staff': staff,
        'active_tab': 'staff',
    }
    return render(request, 'fashion_master/staff_detail.html', context)


# ============================================
# STAFF ATTENDANCE VIEWS
# ============================================

@login_required
def staff_attendance(request):
    """View fashion staff attendance"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    staff = FashionStaff.objects.filter(tenant=tenant, is_active=True)
    
    # Get attendance for today
    today = timezone.now().date()
    attendances = FashionStaffAttendance.objects.filter(
        tenant=tenant,
        date=today
    ).select_related('staff')
    
    context = {
        'tenant': tenant,
        'attendances': attendances,
        'staff': staff,
        'today': today,
        'active_tab': 'staff',
    }
    return render(request, 'fashion_master/staff_attendance.html', context)


# ============================================
# STAFF LEAVE VIEWS
# ============================================

@login_required
def staff_leave_list(request):
    """View fashion staff leave requests"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    leaves = FashionStaffLeave.objects.filter(tenant=tenant).order_by('-created_at')
    
    # Filters
    status = request.GET.get('status', '')
    staff_id = request.GET.get('staff', '')
    
    if status:
        leaves = leaves.filter(status=status)
    if staff_id:
        leaves = leaves.filter(staff_id=staff_id)
    
    staff_members = FashionStaff.objects.filter(tenant=tenant, is_active=True)
    
    paginator = Paginator(leaves, 20)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    context = {
        'tenant': tenant,
        'leaves': page_obj,
        'staff_members': staff_members,
        'status_filter': status,
        'staff_filter': staff_id,
        'active_tab': 'staff',
    }
    return render(request, 'fashion_master/staff_leave_list.html', context)


# ============================================
# ROLE VIEWS
# ============================================

@login_required
def role_list(request):
    """List fashion roles"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    roles = FashionRole.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    for role in roles:
        role.user_count = role.users.count()
        role.permission_count = len(role.permissions)
    
    context = {
        'tenant': tenant,
        'roles': roles,
        'active_tab': 'roles',
    }
    return render(request, 'fashion_master/role_list.html', context)


@login_required
def role_create(request):
    """Create fashion role"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    from .permissions import FASHION_MASTER_PERMISSIONS
    
    # Group permissions by category
    permission_groups = {}
    for codename, name in FASHION_MASTER_PERMISSIONS.items():
        category = 'Other'
        if 'product' in codename:
            category = 'Products'
        elif 'category' in codename:
            category = 'Categories'
        elif 'stock' in codename:
            category = 'Stock'
        elif 'sale' in codename:
            category = 'Sales'
        elif 'return' in codename:
            category = 'Returns'
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
            'id': codename
        })
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        permission_list = request.POST.getlist('permissions')
        is_system_role = request.POST.get('is_system_role') == 'on'
        
        if not name:
            messages.error(request, 'Role name is required')
            return render(request, 'fashion_master/role_form.html', {
                'tenant': tenant,
                'permission_groups': permission_groups,
                'active_tab': 'roles',
            })
        
        if FashionRole.objects.filter(tenant=tenant, name=name).exists():
            messages.error(request, f'Role "{name}" already exists')
            return render(request, 'fashion_master/role_form.html', {
                'tenant': tenant,
                'permission_groups': permission_groups,
                'active_tab': 'roles',
            })
        
        role = FashionRole.objects.create(
            tenant=tenant,
            name=name,
            description=description,
            permissions=permission_list,
            is_system_role=is_system_role,
            created_by=request.user
        )
        
        messages.success(request, f'Role "{name}" created successfully!')
        return redirect('fashion_master:role_list')
    
    context = {
        'tenant': tenant,
        'permission_groups': permission_groups,
        'active_tab': 'roles',
    }
    return render(request, 'fashion_master/role_form.html', context)


@login_required
def role_assign(request):
    """Assign fashion role to user"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role_id = request.POST.get('role_id')
        action = request.POST.get('action', 'assign')
        
        if not user_id or not role_id:
            messages.error(request, 'Please select both user and role.')
            return redirect('fashion_master:role_assign')
        
        try:
            user = get_object_or_404(User, id=user_id, tenant=tenant)
            role = get_object_or_404(FashionRole, id=role_id, tenant=tenant)
            
            if action == 'assign':
                if role.users.filter(id=user.id).exists():
                    messages.info(request, f'User already has role "{role.name}"')
                else:
                    role.users.add(user)
                    messages.success(request, f'Role "{role.name}" assigned to {user.username}!')
            elif action == 'remove':
                if role.users.filter(id=user.id).exists():
                    role.users.remove(user)
                    messages.success(request, f'Role "{role.name}" removed from {user.username}!')
                else:
                    messages.warning(request, f'User does not have role "{role.name}"')
            
        except (User.DoesNotExist, FashionRole.DoesNotExist) as e:
            messages.error(request, f'Error: {str(e)}')
        
        return redirect('fashion_master:role_assign')
    
    users = User.objects.filter(tenant=tenant, is_active=True).order_by('username')
    roles = FashionRole.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    # Get current assignments
    assignments = []
    for role in roles:
        for user in role.users.all():
            assignments.append({
                'user': user,
                'role': role,
                'assignment_id': f"{role.id}_{user.id}",
            })
    
    context = {
        'tenant': tenant,
        'users': users,
        'roles': roles,
        'assignments': assignments,
        'active_tab': 'roles',
    }
    return render(request, 'fashion_master/role_assign.html', context)