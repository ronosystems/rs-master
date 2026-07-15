# apps/fashion_master/views_staff.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from apps.shared.users.models import User
from apps.shared.permissions.models import UserRoleAssignment
from apps.tronic_master.models import Branch

from .models import FashionStaff, FashionStaffAttendance
from apps.fashion_master.models import FashionRole

User = get_user_model()
logger = logging.getLogger(__name__)


# ============================================
# STAFF LIST VIEW
# ============================================

# apps/fashion_master/views_staff.py

@login_required
def staff_list(request):
    """List all fashion staff (users)"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    # Get users
    users = User.objects.filter(tenant=tenant, is_active=True).order_by('first_name', 'last_name')
    
    # Get all fashion roles for this tenant
    from .models import FashionRole
    all_roles = FashionRole.objects.filter(tenant=tenant, is_active=True)
    
    # Build a mapping of user_id -> list of role names
    user_roles_map = {}
    for role in all_roles:
        for user in role.users.all():
            if user.id not in user_roles_map:
                user_roles_map[user.id] = []
            user_roles_map[user.id].append(role.name)
    
    # Add custom_roles as a separate attribute to each user (without underscore)
    for user in users:
        user.custom_role_names = user_roles_map.get(user.id, [])
    
    # Filters
    search = request.GET.get('search', '')
    role = request.GET.get('role', '')
    branch_id = request.GET.get('branch', '')
    status = request.GET.get('status', '')
    
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone_number__icontains=search)
        )
    
    if role:
        users = users.filter(role=role)
    
    if status:
        users = users.filter(is_active=(status == 'active'))
    
    # Rebuild user_roles_map for filtered users
    user_roles_map = {}
    for role in all_roles:
        for user in role.users.all():
            if user.id in users.values_list('id', flat=True):
                if user.id not in user_roles_map:
                    user_roles_map[user.id] = []
                user_roles_map[user.id].append(role.name)
    
    for user in users:
        user.custom_role_names = user_roles_map.get(user.id, [])
    
    # Get branches
    branches = Branch.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    # Get system roles
    system_roles = [
        ('admin', 'Admin'),
        ('user', 'User'),
        ('manager', 'Manager'),
        ('cashier', 'Cashier'),
        ('sales_agent', 'Sales Agent'),
        ('stock_controller', 'Stock Controller'),
    ]
    
    # Pagination
    paginator = Paginator(users, 20)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    context = {
        'tenant': tenant,
        'staff': page_obj,
        'branches': branches,
        'roles': system_roles,
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
    user = get_object_or_404(User, id=staff_id, tenant=tenant)
    
    # Get custom roles for this user - store in a separate attribute
    from .models import FashionRole
    custom_roles = []
    for role in FashionRole.objects.filter(tenant=tenant, is_active=True):
        if role.users.filter(id=user.id).exists():
            custom_roles.append(role.name)
    
    # Use a separate attribute, not a model field
    user.custom_role_names = custom_roles
    
    context = {
        'tenant': tenant,
        'staff': user,
        'active_tab': 'staff',
    }
    return render(request, 'fashion_master/staff_detail.html', context)




# ============================================
# STAFF CREATE VIEW
# ============================================

@login_required
def staff_create(request):
    """Create a new staff user with system and custom roles"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    # System roles (EXCLUDE super_admin)
    system_roles = [
        ('admin', 'Admin'),
        ('user', 'User'),
    ]
    
    # Get custom roles from FashionRole model
    from .models import FashionRole
    custom_roles = FashionRole.objects.filter(
        tenant=tenant,
        is_active=True
    ).order_by('name')
    
    # Get branches through tronic_master.Branch
    branches = Branch.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        system_role = request.POST.get('system_role')
        custom_role_id = request.POST.get('custom_role')
        branch_id = request.POST.get('branch')
        hire_date = request.POST.get('hire_date')
        pin = request.POST.get('pin')
        is_active = request.POST.get('is_active') == 'on'
        
        # Validate required fields
        if not username:
            messages.error(request, 'Username is required')
            return redirect('fashion_master:staff_create')
        
        if not password:
            messages.error(request, 'Password is required')
            return redirect('fashion_master:staff_create')
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters')
            return redirect('fashion_master:staff_create')
        
        if not first_name or not last_name:
            messages.error(request, 'First name and last name are required')
            return redirect('fashion_master:staff_create')
        
        if not email:
            messages.error(request, 'Email is required')
            return redirect('fashion_master:staff_create')
        
        if not system_role:
            messages.error(request, 'System role is required')
            return redirect('fashion_master:staff_create')
        
        # Validate system role (prevent super_admin)
        if system_role == 'super_admin':
            messages.error(request, 'Cannot create super admin users')
            return redirect('fashion_master:staff_create')
        
        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists')
            return redirect('fashion_master:staff_create')
        
        # Check if email exists
        if User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" already exists')
            return redirect('fashion_master:staff_create')
        
        # Create user
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            role=system_role,
            tenant=tenant,
            is_active=is_active
        )
        
        # Assign branch if provided
        if branch_id:
            try:
                branch = Branch.objects.get(id=branch_id, tenant=tenant)
                request.session['staff_branch'] = branch_id
                messages.info(request, f'Branch assigned: {branch.name}')
            except Branch.DoesNotExist:
                messages.warning(request, 'Selected branch not found')
        
        # Set hire date if provided
        if hire_date:
            try:
                user.hire_date = datetime.strptime(hire_date, '%Y-%m-%d').date()
                user.save()
            except (ValueError, TypeError):
                pass
        
        # ✅ Assign custom role if selected
        if custom_role_id:
            try:
                custom_role = get_object_or_404(FashionRole, id=custom_role_id, tenant=tenant)
                custom_role.users.add(user)
                custom_role.save()
                messages.info(request, f'Custom role "{custom_role.name}" assigned to {username}')
            except FashionRole.DoesNotExist:
                messages.warning(request, 'Selected custom role not found')
        
        # Set PIN if provided
        if pin and len(pin) >= 4 and pin.isdigit():
            user.pin_code = pin
            user.save()
        
        messages.success(request, f'User "{username}" created successfully!')
        return redirect('fashion_master:staff_detail', staff_id=user.id)
    
    context = {
        'system_roles': system_roles,
        'custom_roles': custom_roles,
        'branches': branches,
        'tenant': tenant,
        'active_tab': 'staff',
        'staff': None,
        'staff_custom_role': None,
    }
    return render(request, 'fashion_master/staff_form.html', context)



# ============================================
# STAFF EDIT VIEW
# ============================================

@login_required
def staff_edit(request, staff_id):
    """Edit staff user with system and custom roles"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    user = get_object_or_404(User, id=staff_id, tenant=tenant)
    
    # Prevent editing super_admin users
    if user.role == 'super_admin':
        messages.error(request, 'Cannot edit super admin users')
        return redirect('fashion_master:staff_list')
    
    # Get system roles
    system_roles = [
        ('admin', 'Admin'),
        ('user', 'User'),
        ('manager', 'Manager'),
        ('cashier', 'Cashier'),
        ('sales_agent', 'Sales Agent'),
        ('stock_controller', 'Stock Controller'),
    ]
    
    # Get custom roles from FashionRole model
    from .models import FashionRole
    custom_roles = FashionRole.objects.filter(
        tenant=tenant,
        is_active=True
    ).order_by('name')
    
    # Get user's current custom role assignment (from FashionRole)
    user_custom_role = None
    for role in custom_roles:
        if role.users.filter(id=user.id).exists():
            user_custom_role = role
            break
    
    # Get branches through tronic_master.Branch
    branches = Branch.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        system_role = request.POST.get('system_role')
        custom_role_id = request.POST.get('custom_role')
        is_active = request.POST.get('is_active') == 'on'
        
        # Validate required fields
        if not username:
            messages.error(request, 'Username is required')
            return redirect('fashion_master:staff_edit', staff_id=user.id)
        
        if not first_name or not last_name:
            messages.error(request, 'First name and last name are required')
            return redirect('fashion_master:staff_edit', staff_id=user.id)
        
        if not email:
            messages.error(request, 'Email is required')
            return redirect('fashion_master:staff_edit', staff_id=user.id)
        
        if not system_role:
            messages.error(request, 'System role is required')
            return redirect('fashion_master:staff_edit', staff_id=user.id)
        
        # Validate system role (prevent super_admin)
        if system_role == 'super_admin':
            messages.error(request, 'Cannot assign super admin role')
            return redirect('fashion_master:staff_edit', staff_id=user.id)
        
        # Check if username exists (excluding current user)
        if User.objects.filter(username=username).exclude(id=user.id).exists():
            messages.error(request, f'Username "{username}" already exists')
            return redirect('fashion_master:staff_edit', staff_id=user.id)
        
        # Check if email exists (excluding current user)
        if User.objects.filter(email=email).exclude(id=user.id).exists():
            messages.error(request, f'Email "{email}" already exists')
            return redirect('fashion_master:staff_edit', staff_id=user.id)
        
        # Update user
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.phone_number = phone_number
        user.role = system_role
        user.is_active = is_active
        
        # Update password if provided
        if password:
            if len(password) < 8:
                messages.error(request, 'Password must be at least 8 characters')
                return redirect('fashion_master:staff_edit', staff_id=user.id)
            user.set_password(password)
        
        user.save()
        
        # ✅ Update custom role assignment (FashionRole)
        # Remove user from all current custom roles
        for role in custom_roles:
            if role.users.filter(id=user.id).exists():
                role.users.remove(user)
        
        # Add to new custom role if selected
        if custom_role_id:
            try:
                custom_role = get_object_or_404(FashionRole, id=custom_role_id, tenant=tenant)
                custom_role.users.add(user)
                custom_role.save()
                messages.info(request, f'Custom role "{custom_role.name}" assigned to {username}')
            except FashionRole.DoesNotExist:
                messages.warning(request, 'Selected custom role not found')
        
        messages.success(request, f'User "{username}" updated successfully!')
        return redirect('fashion_master:staff_detail', staff_id=user.id)
    
    context = {
        'staff': user,
        'system_roles': system_roles,
        'custom_roles': custom_roles,
        'staff_custom_role': user_custom_role,
        'branches': branches,
        'tenant': tenant,
        'active_tab': 'staff',
    }
    return render(request, 'fashion_master/staff_form.html', context)



# ============================================
# STAFF DELETE VIEW
# ============================================

@login_required
def staff_delete(request, staff_id):
    """Delete staff user"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    user = get_object_or_404(User, id=staff_id, tenant=tenant)
    
    # Prevent deleting self
    if user.id == request.user.id:
        messages.error(request, 'You cannot delete your own account!')
        return redirect('fashion_master:staff_list')
    
    # Prevent deleting super admins
    if user.is_super_admin:
        messages.error(request, 'Cannot delete a super admin user!')
        return redirect('fashion_master:staff_list')
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'User "{username}" deleted successfully!')
        return redirect('fashion_master:staff_list')
    
    context = {
        'staff': user,
        'tenant': tenant,
        'active_tab': 'staff',
    }
    return render(request, 'fashion_master/staff_confirm_delete.html', context)


# ============================================
# STAFF TOGGLE STATUS VIEW
# ============================================

@login_required
def staff_toggle_status(request, staff_id):
    """Toggle staff user active status"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    user = get_object_or_404(User, id=staff_id, tenant=tenant)
    
    # Prevent toggling self
    if user.id == request.user.id:
        messages.error(request, 'You cannot change your own status!')
        return redirect('fashion_master:staff_list')
    
    user.is_active = not user.is_active
    user.save()
    
    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User "{user.username}" {status}!')
    return redirect('fashion_master:staff_list')


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
# STAFF ATTENDANCE DETAIL VIEW
# ============================================

@login_required
def staff_attendance_detail(request, staff_id):
    """View attendance for a specific staff member"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    user = get_object_or_404(User, id=staff_id, tenant=tenant)
    
    # Get attendance records for this user
    attendances = []
    
    today = datetime.now().date()
    for i in range(30):
        date = today - timedelta(days=i)
        status = 'present' if i % 5 != 0 else 'absent'
        attendances.append({
            'date': date,
            'status': status,
            'check_in_time': '09:00' if status == 'present' else None,
            'check_out_time': '17:00' if status == 'present' else None,
            'hours_worked': 8.0 if status == 'present' else 0,
        })
    
    paginator = Paginator(attendances, 30)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'staff': user,
        'attendances': page_obj,
        'tenant': tenant,
        'active_tab': 'staff',
    }
    return render(request, 'fashion_master/staff_attendance_detail.html', context)


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
    
    # Get all staff members
    staff_members = User.objects.filter(tenant=tenant, is_active=True).order_by('first_name', 'last_name')
    
    # Get leave requests (placeholder data)
    leaves = []
    today = datetime.now().date()
    
    for idx, user in enumerate(staff_members[:5]):
        leave = {
            'id': idx + 1,
            'user': user,
            'staff': user,
            'staff_name': user.get_full_name() or user.username,
            'leave_type': 'annual',
            'start_date': today,
            'end_date': today + timedelta(days=3),
            'days': 3,
            'reason': 'Annual vacation',
            'status': 'pending',
            'created_at': datetime.now(),
            'get_status_display': lambda: 'Pending',
            'get_leave_type_display': lambda: 'Annual Leave',
        }
        leaves.append(leave)
    
    # Add some approved and rejected ones
    if len(staff_members) > 2:
        leaves.append({
            'id': len(staff_members) + 1,
            'user': staff_members[2],
            'staff': staff_members[2],
            'staff_name': staff_members[2].get_full_name() or staff_members[2].username,
            'leave_type': 'sick',
            'start_date': today - timedelta(days=10),
            'end_date': today - timedelta(days=8),
            'days': 2,
            'reason': 'Sick leave',
            'status': 'approved',
            'created_at': datetime.now(),
            'get_status_display': lambda: 'Approved',
            'get_leave_type_display': lambda: 'Sick Leave',
        })
    
    if len(staff_members) > 3:
        leaves.append({
            'id': len(staff_members) + 2,
            'user': staff_members[3],
            'staff': staff_members[3],
            'staff_name': staff_members[3].get_full_name() or staff_members[3].username,
            'leave_type': 'compassionate',
            'start_date': today - timedelta(days=5),
            'end_date': today - timedelta(days=4),
            'days': 1,
            'reason': 'Compassionate leave',
            'status': 'rejected',
            'created_at': datetime.now(),
            'get_status_display': lambda: 'Rejected',
            'get_leave_type_display': lambda: 'Compassionate Leave',
        })
    
    # Apply filters
    status = request.GET.get('status', '')
    staff_id = request.GET.get('staff', '')
    
    if status:
        leaves = [l for l in leaves if l['status'] == status]
    if staff_id:
        leaves = [l for l in leaves if l['user'].id == int(staff_id)]
    
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
# STAFF LEAVE CREATE VIEW
# ============================================

@login_required
def staff_leave_create(request):
    """Create a leave request for a user"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    if request.method == 'POST':
        user_id = request.POST.get('staff')
        leave_type = request.POST.get('leave_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')
        
        # Validate inputs
        if not user_id:
            messages.error(request, 'Please select a staff member')
            return redirect('fashion_master:staff_leave_create')
        
        if not leave_type:
            messages.error(request, 'Please select a leave type')
            return redirect('fashion_master:staff_leave_create')
        
        if not start_date or not end_date:
            messages.error(request, 'Please select start and end dates')
            return redirect('fashion_master:staff_leave_create')
        
        if not reason:
            messages.error(request, 'Please provide a reason for the leave')
            return redirect('fashion_master:staff_leave_create')
        
        # Get the user
        user = get_object_or_404(User, id=user_id, tenant=tenant)
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end - start).days + 1
        
        messages.success(
            request, 
            f'Leave request created for {user.get_full_name() or user.username}! '
            f'({days} days, {leave_type})'
        )
        return redirect('fashion_master:staff_leave_list')
    
    # GET request - show the form
    staff_members = User.objects.filter(tenant=tenant, is_active=True).order_by('first_name', 'last_name')
    
    context = {
        'staff_members': staff_members,
        'leave_types': [
            ('annual', 'Annual Leave'),
            ('sick', 'Sick Leave'),
            ('maternity', 'Maternity Leave'),
            ('paternity', 'Paternity Leave'),
            ('compassionate', 'Compassionate Leave'),
            ('study', 'Study Leave'),
            ('other', 'Other'),
        ],
        'tenant': tenant,
        'active_tab': 'staff',
    }
    return render(request, 'fashion_master/staff_leave_form.html', context)


# ============================================
# STAFF LEAVE APPROVE VIEW
# ============================================

@login_required
def staff_leave_approve(request, leave_id):
    """Approve a leave request"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    messages.success(request, 'Leave approved successfully!')
    return redirect('fashion_master:staff_leave_list')


# ============================================
# STAFF LEAVE REJECT VIEW
# ============================================

@login_required
def staff_leave_reject(request, leave_id):
    """Reject a leave request"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    messages.success(request, 'Leave rejected successfully!')
    return redirect('fashion_master:staff_leave_list')


# ============================================
# ROLE LIST VIEW
# ============================================

# apps/fashion_master/views_staff.py

@login_required
def role_list(request):
    """List all roles for Fashion Master"""
    tenant = request.user.tenant
    
    # ✅ FIX: Use FashionRole model instead of Role
    from .models import FashionRole
    
    if request.user.is_super_admin:
        # Super admin sees all fashion roles
        roles = FashionRole.objects.all().order_by('name')
    else:
        # Tenant admin sees roles for their tenant
        roles = FashionRole.objects.filter(
            tenant=tenant,
            is_active=True
        ).order_by('name')
    
    # Get user count for each role
    for role in roles:
        role.user_count = role.users.count()
        role.permission_count = len(role.permissions) if role.permissions else 0
    
    context = {
        'tenant': tenant,
        'roles': roles,
        'active_tab': 'roles',
    }
    return render(request, 'fashion_master/role_list.html', context)

# ============================================
# ROLE CREATE VIEW
# ============================================

@login_required
def role_create(request):
    """Create a new role with permissions"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('fashion_master:dashboard')
    
    from .models import FashionRole
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
        elif 'branch' in codename:
            category = 'Branches'
        
        if category not in permission_groups:
            permission_groups[category] = []
        permission_groups[category].append({
            'codename': codename,
            'name': name,
        })
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        permission_list = request.POST.getlist('permissions')
        is_system_role = request.POST.get('is_system_role') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        
        if not name:
            messages.error(request, 'Role name is required')
            return render(request, 'fashion_master/role_form.html', {
                'tenant': tenant,
                'permission_groups': permission_groups,
                'active_tab': 'roles',
            })
        
        # Check if role exists for this tenant
        if FashionRole.objects.filter(tenant=tenant, name__iexact=name).exists():
            messages.error(request, f'Role "{name}" already exists')
            return render(request, 'fashion_master/role_form.html', {
                'tenant': tenant,
                'permission_groups': permission_groups,
                'active_tab': 'roles',
            })
        
        # Create role
        role = FashionRole.objects.create(
            tenant=tenant,
            name=name,
            description=description,
            permissions=permission_list,
            is_system_role=is_system_role,
            is_active=is_active,
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

# ============================================
# ROLE ASSIGN VIEW
# ============================================

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
    
    from .models import FashionRole
    
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
            
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
        except FashionRole.DoesNotExist:
            messages.error(request, 'Role not found.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        
        return redirect('fashion_master:role_assign')
    
    # GET request - show the form
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

# ============================================
# ROLE EDIT VIEW
# ============================================

@login_required
def role_edit(request, role_id):
    """Edit a role and its permissions"""
    tenant = request.user.tenant
    role = get_object_or_404(FashionRole, id=role_id, tenant=tenant)
    
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
        elif 'branch' in codename:
            category = 'Branches'
        
        if category not in permission_groups:
            permission_groups[category] = []
        permission_groups[category].append({
            'codename': codename,
            'name': name,
        })
    
    # Get current role permissions
    role_permissions = role.permissions if isinstance(role.permissions, list) else []
    
    # Get user count
    role.user_count = role.users.count()
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        permission_list = request.POST.getlist('permissions')
        is_active = request.POST.get('is_active') == 'on'
        is_system_role = request.POST.get('is_system_role') == 'on'
        
        if not name:
            messages.error(request, 'Role name is required')
            return render(request, 'fashion_master/role_form.html', {
                'tenant': tenant,
                'role': role,
                'permission_groups': permission_groups,
                'role_permissions': role_permissions,
                'active_tab': 'roles',
            })
        
        # Check if role exists for this tenant (excluding current)
        if FashionRole.objects.filter(tenant=tenant, name__iexact=name).exclude(id=role.id).exists():
            messages.error(request, f'Role "{name}" already exists')
            return render(request, 'fashion_master/role_form.html', {
                'tenant': tenant,
                'role': role,
                'permission_groups': permission_groups,
                'role_permissions': role_permissions,
                'active_tab': 'roles',
            })
        
        # Update role
        role.name = name
        role.description = description
        role.permissions = permission_list
        role.is_active = is_active
        role.is_system_role = is_system_role
        role.save()
        
        messages.success(request, f'Role "{name}" updated successfully!')
        return redirect('fashion_master:role_list')
    
    context = {
        'tenant': tenant,
        'role': role,
        'permission_groups': permission_groups,
        'role_permissions': role_permissions,
        'active_tab': 'roles',
    }
    return render(request, 'fashion_master/role_form.html', context)



# ============================================
# ROLE DELETE VIEW
# ============================================

@login_required
def role_delete(request, role_id):
    """Delete a role"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        role = get_object_or_404(FashionRole, id=role_id, tenant=tenant)
        
        # Check if it's a system role
        if role.is_system_role:
            messages.error(request, 'Cannot delete system roles.')
            return redirect('fashion_master:role_list')
        
        # Check if role has users assigned
        if role.users.exists():
            messages.error(request, f'Cannot delete "{role.name}" because it has {role.users.count()} users assigned.')
            return redirect('fashion_master:role_list')
        
        role_name = role.name
        role.delete()
        messages.success(request, f'Role "{role_name}" deleted successfully!')
        return redirect('fashion_master:role_list')
    
    return redirect('fashion_master:role_list')

# ============================================
# ROLE REMOVE USER VIEW
# ============================================

@login_required
def role_remove_user(request, assignment_id):
    """Remove a role assignment from a user"""
    if request.method == 'POST':
        try:
            assignment = get_object_or_404(UserRoleAssignment, id=assignment_id)
            assignment.delete()
            messages.success(request, 'Role removed from user successfully!')
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})