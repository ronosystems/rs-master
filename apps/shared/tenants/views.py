# apps/shared/tenants/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.utils import timezone
from datetime import timedelta, datetime
from .models import Tenant, ProjectType, SubscriptionPlan, SubscriptionInvoice
from apps.tronic_master.models import Product, Branch 
from django.db.models import Count
from django.core.paginator import Paginator
from apps.shared.users.models import User
import logging



logger = logging.getLogger(__name__)




# ============================================
# HELPER FUNCTIONS
# ============================================

def is_super_admin(user):
    """Check if user is super admin"""
    return user.is_superuser


def is_tenant_admin(user):
    """Check if user is tenant admin"""
    return user.role in ['admin', 'tenant_admin']


def has_tenant_access(user, tenant):
    """Check if user has access to a tenant"""
    if is_super_admin(user):
        return True
    if is_tenant_admin(user) and user.tenant == tenant:
        return True
    return False





# ============================================
# SUPERADMIN DASHBOARD
# ============================================
@login_required
def super_admin_dashboard(request):
    """Super admin dashboard with tenant overview"""
    
    if not request.user.is_super_admin:
        messages.error(request, 'Access denied. Super admin only.')
        return redirect('dashboard')
    
    # Get all tenants
    tenants = Tenant.objects.all().order_by('-created_at')
    
    # Check if in preview mode
    is_preview_mode = request.session.get('tenant_id') is not None
    preview_tenant = None
    
    if is_preview_mode:
        try:
            preview_tenant = Tenant.objects.get(id=request.session['tenant_id'])
        except Tenant.DoesNotExist:
            pass
    
    # Calculate statistics
    total_tenants = tenants.count()
    active_tenants = tenants.filter(status='active').count()
    pending_tenants = tenants.filter(status='pending').count()
    rejected_tenants = tenants.filter(status='rejected').count()
    
    # Get project type breakdown
    project_types = {}
    for tenant in tenants:
        project_type = tenant.project_type.name if tenant.project_type else 'Unknown'
        project_types[project_type] = project_types.get(project_type, 0) + 1
    
    context = {
        'tenants': tenants,
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'pending_tenants': pending_tenants,
        'rejected_tenants': rejected_tenants,
        'project_types': project_types,
        'is_preview_mode': is_preview_mode,
        'preview_tenant': preview_tenant,
        'is_super_admin': True,
    }
    return render(request, 'shared/super_admin_dashboard.html', context)


@login_required
def switch_tenant(request, tenant_id):
    """Switch to a tenant as a super admin to view their dashboard"""
    
    if not request.user.is_super_admin:
        messages.error(request, 'Access denied. Super admin only.')
        return redirect('super_admin_dashboard')
    
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    # Store original tenant to switch back
    if 'original_tenant_id' not in request.session:
        request.session['original_tenant_id'] = request.session.get('tenant_id')
    
    # Switch to selected tenant
    request.session['tenant_id'] = tenant.id
    
    messages.success(request, f'🔍 Previewing: {tenant.company_name}')
    
    # Redirect based on tenant's project type
    if tenant.project_type:
        project_type = tenant.project_type.code.lower()
        redirect_map = {
            'tronic_master': 'tronic_master:dashboard',
            'fashion_master': 'fashion_master:dashboard',
            'food_master': 'food_master:dashboard',
            'hotel_master': 'hotel_master:dashboard',
            'rental_master': 'rental_master:dashboard',
            'health_master': 'health_master:dashboard',
        }
        return redirect(redirect_map.get(project_type, 'portal:dashboard'))
    
    return redirect('portal:dashboard')


@login_required
def exit_preview(request):
    """Exit tenant preview mode and return to super admin view"""
    
    if not request.user.is_super_admin:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Clear tenant from session
    request.session.pop('tenant_id', None)
    request.session.pop('original_tenant_id', None)
    
    # Remove tenant from user if it was set
    if hasattr(request.user, 'tenant'):
        # Don't delete, just set to None
        request.user.tenant = None
        # Save if user model has tenant field
        if hasattr(request.user, 'save'):
            try:
                request.user.save()
            except:
                pass
    
    messages.success(request, '✅ Exited preview mode')
    
    # ✅ Redirect to tenant list (the super admin page)
    return redirect('tenants:tenant_list')








# ============================================
# PROJECT TOGGLE VIEWS
# ============================================
@login_required
def project_type_toggle(request, pk):
    """Toggle project type active status"""
    if not request.user.is_superuser:
        messages.error(request, 'Access denied. Super Admin only.')
        return redirect('dashboard')
    
    project_type = get_object_or_404(ProjectType, pk=pk)
    project_type.is_active = not project_type.is_active
    project_type.save()
    
    status = "activated" if project_type.is_active else "deactivated"
    messages.success(request, f'Project type "{project_type.name}" has been {status}!')
    return redirect('tenants:project_type_list')


# ============================================
# TENANT VIEWS
# ============================================

@login_required
def tenant_list(request):
    """List all tenants - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can view all tenants.')
        return redirect('dashboard')
    
    tenants = Tenant.objects.all().order_by('-created_at')
    
    context = {
        'tenants': tenants,
        'is_super_admin': True,
    }
    return render(request, 'shared/tenant_list.html', context)


@login_required
def tenant_detail(request, tenant_id):
    """View tenant details - Super Admin or Tenant Admin"""
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if not has_tenant_access(request.user, tenant):
        messages.error(request, 'Access denied. You do not have permission to view this tenant.')
        return redirect('dashboard')
    
    tenant = get_object_or_404(
        Tenant.objects.select_related('project_type'), 
        id=tenant_id
    )
    
    admin_users = tenant.users.filter(role__in=['admin', 'tenant_admin'])
    
    # Get subscription info
    subscription_plans = SubscriptionPlan.objects.filter(is_active=True)
    is_subscription_active = False
    days_remaining = 0
    
    if hasattr(tenant, 'subscription_end') and tenant.subscription_end:
        today = timezone.now().date()
        end_date = tenant.subscription_end
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        if end_date > today:
            is_subscription_active = True
            days_remaining = (end_date - today).days
    
    context = {
        'tenant': tenant,
        'admin_users': admin_users,
        'subscription_plans': subscription_plans,
        'is_subscription_active': is_subscription_active,
        'days_remaining': days_remaining,
        'is_super_admin': is_super_admin(request.user),
        'is_tenant_admin': is_tenant_admin(request.user),
    }
    return render(request, 'shared/tenant_detail.html', context)


@login_required
def edit_tenant(request, tenant_id):
    """Edit tenant details - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can edit tenants.')
        return redirect('dashboard')
    
    tenant = get_object_or_404(Tenant, id=tenant_id)
    project_types = ProjectType.objects.filter(is_active=True)
    subscription_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
    
    if request.method == 'POST':
        # ============================================
        # Company Details
        # ============================================
        company_name = request.POST.get('company_name', '').strip()
        company_address = request.POST.get('company_address', '').strip()
        company_phone = request.POST.get('company_phone', '').strip()
        company_email = request.POST.get('company_email', '').strip()
        company_pin = request.POST.get('company_pin', '').strip()
        project_type_id = request.POST.get('project_type')
        status = request.POST.get('status')
        subscription_plan = request.POST.get('subscription_plan', '').strip()
        
        if company_name:
            tenant.company_name = company_name
        tenant.company_address = company_address
        tenant.company_phone = company_phone
        tenant.company_email = company_email
        tenant.company_pin = company_pin
        
        if project_type_id:
            try:
                project_type = ProjectType.objects.get(id=project_type_id)
                tenant.project_type = project_type
            except ProjectType.DoesNotExist:
                pass
        
        if status:
            tenant.status = status
        
        # ============================================
        # Logo Handling
        # ============================================
        if request.FILES.get('logo'):
            tenant.logo = request.FILES.get('logo')
        
        if request.POST.get('remove_logo') == 'on':
            tenant.logo = None
        
        # ============================================
        # ✅ SUBSCRIPTION FIELDS - ADD THESE
        # ============================================
        subscription_plan = request.POST.get('subscription_plan', '').strip()
        subscription_start = request.POST.get('subscription_start', '').strip()
        subscription_end = request.POST.get('subscription_end', '').strip()
        auto_renew = request.POST.get('auto_renew') == 'true'
        
        if subscription_plan:
            tenant.subscription_plan = subscription_plan
        
        if subscription_start:
            try:
                tenant.subscription_start = datetime.strptime(subscription_start, '%Y-%m-%d')
            except ValueError:
                pass
        
        if subscription_end:
            try:
                tenant.subscription_end = datetime.strptime(subscription_end, '%Y-%m-%d')
            except ValueError:
                pass
        
        tenant.auto_renew = auto_renew
        
        # ============================================
        # Save Tenant
        # ============================================
        tenant.save()
        
        messages.success(request, f'Tenant "{tenant.company_name}" updated successfully!')
        return redirect('tenants:tenant_detail', tenant_id=tenant.id)
    
    context = {
        'tenant': tenant,
        'project_types': project_types,
        'status_choices': Tenant.STATUS_CHOICES,
        'subscription_plans': subscription_plans, 
        'is_super_admin': True,
    }
    return render(request, 'shared/edit_tenant.html', context)


@login_required
def register_tenant(request):
    """Register a new tenant - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can register tenants.')
        return redirect('dashboard')
    
    project_types = ProjectType.objects.filter(is_active=True)
    subscription_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
    
    if request.method == 'POST':
        # ============================================
        # Get Tenant Details
        # ============================================
        company_name = request.POST.get('company_name', '').strip()
        project_type_id = request.POST.get('project_type')
        company_address = request.POST.get('company_address', '').strip()
        company_phone = request.POST.get('company_phone', '').strip()
        company_email = request.POST.get('company_email', '').strip()
        company_pin = request.POST.get('company_pin', '').strip()
        
        # ✅ Subscription fields
        subscription_plan = request.POST.get('subscription_plan', 'basic').strip()
        subscription_start = request.POST.get('subscription_start', '').strip()
        subscription_end = request.POST.get('subscription_end', '').strip()
        auto_renew = request.POST.get('auto_renew') == 'true'
        
        # ============================================
        # Get Owner/Admin User Details
        # ============================================
        username = request.POST.get('username', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        pin_code = request.POST.get('pin_code', '').strip()
        
        # ============================================
        # Validate Required Fields
        # ============================================
        if not company_name:
            messages.error(request, 'Company name is required')
            return redirect('tenants:register_tenant')
        
        if not username:
            messages.error(request, 'Username is required')
            return redirect('tenants:register_tenant')
        
        if not full_name:
            messages.error(request, 'Full name is required')
            return redirect('tenants:register_tenant')
        
        if not email:
            messages.error(request, 'Email is required')
            return redirect('tenants:register_tenant')
        
        if not password:
            messages.error(request, 'Password is required')
            return redirect('tenants:register_tenant')
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return redirect('tenants:register_tenant')
        
        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters')
            return redirect('tenants:register_tenant')
        
        # ============================================
        # Check for Duplicates
        # ============================================
        if Tenant.objects.filter(company_name__iexact=company_name).exists():
            messages.error(request, f'Tenant "{company_name}" already exists')
            return redirect('tenants:register_tenant')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists')
            return redirect('tenants:register_tenant')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" already exists')
            return redirect('tenants:register_tenant')
        
        # ============================================
        # Get Project Type
        # ============================================
        project_type = None
        if project_type_id:
            project_type = get_object_or_404(ProjectType, id=project_type_id)
        
        # ============================================
        # Create Tenant
        # ============================================
        tenant = Tenant.objects.create(
            company_name=company_name,
            company_address=company_address,
            company_phone=company_phone,
            company_email=company_email,
            company_pin=company_pin,
            project_type=project_type,
            status='pending',
            # ✅ Subscription fields
            subscription_plan=subscription_plan if subscription_plan else 'basic',
            auto_renew=auto_renew,
        )
        
        # ✅ Set subscription dates
        if subscription_start:
            try:
                tenant.subscription_start = datetime.strptime(subscription_start, '%Y-%m-%d')
            except ValueError:
                pass
        
        if subscription_end:
            try:
                tenant.subscription_end = datetime.strptime(subscription_end, '%Y-%m-%d')
            except ValueError:
                pass
        
        # ============================================
        # Handle Logo Upload
        # ============================================
        if request.FILES.get('logo'):
            tenant.logo = request.FILES.get('logo')
        
        tenant.save()
        
        # ============================================
        # Create Owner/Admin User
        # ============================================
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        owner = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            pin_code=pin_code,
            tenant=tenant,
            role='admin',
            is_active=True
        )
        
        # ============================================
        # Assign Owner to Tenant
        # ============================================
        tenant.owner = owner
        tenant.save()
        
        # ============================================
        # Create Default Settings
        # ============================================
        try:
            from apps.shared.settings.models import ReceiptSetting, ProfileSetting
            
            ReceiptSetting.objects.get_or_create(
                tenant=tenant,
                defaults={
                    'business_name': company_name,
                    'business_address': company_address,
                    'business_phone': company_phone,
                    'business_email': company_email,
                    'show_business_name': True,
                    'show_address': True,
                    'show_phone': True,
                    'show_email': True,
                    'show_tax_pin': False,
                    'footer_text': 'Thank you for your business!',
                }
            )
            
            ProfileSetting.objects.get_or_create(
                user=owner,
                defaults={
                    'theme': 'light',
                    'language': 'en',
                    'currency': 'KES',
                    'notifications_enabled': True,
                    'email_notifications': True,
                }
            )
        except Exception as e:
            logger.warning(f"Could not create default settings: {e}")
        
        messages.success(
            request, 
            f'✅ Tenant "{tenant.company_name}" registered successfully!\n'
            f'👤 Owner: {owner.get_full_name()} ({owner.username})\n'
            f'📧 Email: {owner.email}\n'
            f'🔑 Status: Pending Approval'
        )
        
        return redirect('tenants:tenant_detail', tenant_id=tenant.id)
    
    context = {
        'project_types': project_types,
        'subscription_plans': subscription_plans,
        'today': timezone.now().date(),
        'is_super_admin': True,
    }
    return render(request, 'shared/register_tenant.html', context)


@login_required
def delete_tenant(request, tenant_id):
    """Delete a tenant - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can delete tenants.')
        return redirect('dashboard')
    
    tenant = get_object_or_404(Tenant, id=tenant_id)
    tenant_name = tenant.company_name
    tenant.delete()
    messages.success(request, f'Tenant "{tenant_name}" deleted successfully!')
    return redirect('tenants:tenant_list')


@login_required
def approve_tenant(request, tenant_id):
    """Approve a pending tenant - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can approve tenants.')
        return redirect('dashboard')
    
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if tenant.status != 'pending':
        messages.warning(request, f'Tenant "{tenant.company_name}" is not pending approval')
        return redirect('tenants:tenant_list')
    
    tenant.status = 'active'
    tenant.save()
    
    messages.success(request, f'Tenant "{tenant.company_name}" has been approved!')
    return redirect('tenants:tenant_list')


@login_required
def reject_tenant(request, tenant_id):
    """Reject a pending tenant - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can reject tenants.')
        return redirect('dashboard')
    
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if tenant.status != 'pending':
        messages.warning(request, f'Tenant "{tenant.company_name}" is not pending approval')
        return redirect('tenants:tenant_list')
    
    tenant.status = 'rejected'
    tenant.save()
    
    messages.success(request, f'Tenant "{tenant.company_name}" has been rejected.')
    return redirect('tenants:tenant_list')


@login_required
def assign_owner(request, tenant_id):
    """Assign owner to tenant - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can assign owners.')
        return redirect('dashboard')
    
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                
                if user.tenant and user.tenant != tenant:
                    user.tenant = None
                    user.save()
                
                tenant.owner = user
                tenant.save()
                
                messages.success(request, f'Owner "{user.username}" assigned to "{tenant.company_name}"')
            except User.DoesNotExist:
                messages.error(request, 'User not found')
            return redirect('tenants:tenant_detail', tenant_id=tenant.id)
    
    users = User.objects.filter(
        is_active=True
    ).filter(
        models.Q(tenant=None) | models.Q(tenant=tenant)
    ).order_by('username')
    
    context = {
        'tenant': tenant,
        'users': users,
        'is_super_admin': True,
    }
    return render(request, 'shared/assign_owner.html', context)


@login_required
def edit_tenant_owner(request, tenant_id):
    """Edit tenant owner details - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can edit tenant owners.')
        return redirect('dashboard')
    
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if not tenant.owner:
        messages.warning(request, 'This tenant does not have an owner assigned.')
        return redirect('tenants:assign_owner', tenant_id=tenant.id)
    
    if request.method == 'POST':
        owner = tenant.owner
        owner.first_name = request.POST.get('first_name', owner.first_name)
        owner.last_name = request.POST.get('last_name', owner.last_name)
        owner.email = request.POST.get('email', owner.email)
        owner.phone_number = request.POST.get('phone_number', owner.phone_number)
        owner.pin_code = request.POST.get('pin_code', owner.pin_code)
        
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                messages.error(request, 'Passwords do not match')
                return redirect('tenants:edit_tenant_owner', tenant_id=tenant.id)
            
            if len(password) < 6:
                messages.error(request, 'Password must be at least 6 characters')
                return redirect('tenants:edit_tenant_owner', tenant_id=tenant.id)
            
            owner.set_password(password)
        
        owner.save()
        messages.success(request, f'Owner details for "{owner.username}" updated successfully!')
        return redirect('tenants:tenant_detail', tenant_id=tenant.id)
    
    context = {
        'tenant': tenant,
        'is_super_admin': True,
    }
    return render(request, 'shared/edit_tenant_owner.html', context)


# ============================================
# PROJECT TYPE VIEWS - Super Admin Only
# ============================================

@login_required
def project_type_list(request):
    """List all project types - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can view project types.')
        return redirect('dashboard')
    
    # Get all project types
    project_types = ProjectType.objects.all().order_by('name')
    
    # Calculate statistics
    total_count = project_types.count()
    active_count = project_types.filter(is_active=True).count()
    inactive_count = project_types.filter(is_active=False).count()
    
    # Get total tenants count
    total_tenants = Tenant.objects.count()
    
    # Get last updated time
    last_updated = ProjectType.objects.order_by('-updated_at').first()
    last_updated_time = last_updated.updated_at if last_updated else None
    
    # Annotate each project type with tenant count
    project_types = project_types.annotate(tenant_count=Count('tenants'))
    
    # Pagination
    paginator = Paginator(project_types, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'project_types': page_obj,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'total_tenants': total_tenants,
        'last_updated': last_updated_time,
        'is_super_admin': True,
    }
    return render(request, 'shared/project_type_list.html', context)


@login_required
def project_type_create(request):
    """Create a new project type - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can create project types.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        icon = request.POST.get('icon', 'fa-building')
        color = request.POST.get('color', 'primary')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not code:
            messages.error(request, 'Name and code are required')
            return redirect('tenants:project_type_create')
        
        project_type = ProjectType.objects.create(
            name=name,
            code=code.upper(),
            icon=icon,
            color=color,
            description=description,
            is_active=is_active
        )
        
        messages.success(request, f'Project type "{project_type.name}" created!')
        return redirect('tenants:project_type_list')
    
    context = {
        'icons': [
            ('fa-building', 'Building'),
            ('fa-crown', 'Crown'),
            ('fa-star', 'Star'),
            ('fa-gem', 'Gem'),
            ('fa-rocket', 'Rocket'),
            ('fa-chart-line', 'Chart'),
            ('fa-briefcase', 'Briefcase'),
            ('fa-trophy', 'Trophy'),
        ],
        'colors': [
            ('primary', 'Blue'),
            ('success', 'Green'),
            ('warning', 'Yellow'),
            ('danger', 'Red'),
            ('info', 'Cyan'),
            ('dark', 'Dark'),
        ],
        'is_super_admin': True,
    }
    return render(request, 'shared/project_type_form.html', context)


@login_required
def project_type_edit(request, pk):
    """Edit a project type - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can edit project types.')
        return redirect('dashboard')
    
    project_type = get_object_or_404(ProjectType, pk=pk)
    
    if request.method == 'POST':
        project_type.name = request.POST.get('name')
        project_type.code = request.POST.get('code').upper()
        project_type.icon = request.POST.get('icon', 'fa-building')
        project_type.color = request.POST.get('color', 'primary')
        project_type.description = request.POST.get('description', '')
        project_type.is_active = request.POST.get('is_active') == 'on'
        project_type.save()
        
        messages.success(request, f'Project type "{project_type.name}" updated!')
        return redirect('tenants:project_type_list')
    
    context = {
        'project_type': project_type,
        'icons': [
            ('fa-building', 'Building'),
            ('fa-crown', 'Crown'),
            ('fa-star', 'Star'),
            ('fa-gem', 'Gem'),
            ('fa-rocket', 'Rocket'),
            ('fa-chart-line', 'Chart'),
            ('fa-briefcase', 'Briefcase'),
            ('fa-trophy', 'Trophy'),
        ],
        'colors': [
            ('primary', 'Blue'),
            ('success', 'Green'),
            ('warning', 'Yellow'),
            ('danger', 'Red'),
            ('info', 'Cyan'),
            ('dark', 'Dark'),
        ],
        'is_super_admin': True,
    }
    return render(request, 'shared/project_type_form.html', context)


@login_required
def project_type_delete(request, pk):
    """Delete a project type - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can delete project types.')
        return redirect('dashboard')
    
    project_type = get_object_or_404(ProjectType, pk=pk)
    
    if project_type.tenants.exists():
        messages.error(request, f'Cannot delete "{project_type.name}" because it has tenants assigned.')
        return redirect('tenants:project_type_list')
    
    project_type.delete()
    messages.success(request, f'Project type deleted successfully!')
    return redirect('tenants:project_type_list')


# ============================================
# SUBSCRIPTION PLANS VIEWS - Super Admin Only
# ============================================

@login_required
def subscription_plans_list(request):
    """List all subscription plans - Super Admin only (CRUD operations)"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can manage subscription plans.')
        return redirect('dashboard')
    
    # Get all plans ordered by price
    plans = SubscriptionPlan.objects.all().order_by('price_monthly')
    
    # Calculate statistics
    total_plans = plans.count()
    active_plans_count = plans.filter(is_active=True).count()
    inactive_plans_count = plans.filter(is_active=False).count()
    
    # Get total tenants and active tenants
    total_tenants = Tenant.objects.count()
    active_tenants_count = Tenant.objects.filter(status='active').count()
    
    # ✅ For each plan, calculate directly
    total_monthly_revenue = 0
    for plan in plans:
        # Direct query for tenant count
        plan.tenant_count = Tenant.objects.filter(
            subscription_plan=plan.code,
            status='active'
        ).count()
        
        # Calculate monthly revenue
        plan.monthly_revenue = plan.tenant_count * plan.price_monthly
        
        # Add to total revenue if plan is active
        if plan.is_active:
            total_monthly_revenue += plan.monthly_revenue
    
    # Pagination
    paginator = Paginator(plans, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'plans': page_obj,
        'total_plans': total_plans,
        'active_plans_count': active_plans_count,
        'inactive_plans_count': inactive_plans_count,
        'total_tenants': total_tenants,
        'active_tenants_count': active_tenants_count,
        'total_monthly_revenue': total_monthly_revenue,
        'is_super_admin': True,
    }
    return render(request, 'shared/subscription_plans_list.html', context)


@login_required
def subscription_plan_create(request):
    """Create a new subscription plan - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can create subscription plans.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        price_monthly = request.POST.get('price_monthly', 0)
        price_yearly = request.POST.get('price_yearly', 0)
        max_users = request.POST.get('max_users', 5)
        max_products = request.POST.get('max_products', 100)
        max_branches = request.POST.get('max_branches', 1)
        max_storage_gb = request.POST.get('max_storage_gb', 1)
        icon = request.POST.get('icon', 'fa-building')
        color = request.POST.get('color', 'primary')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        features = {
            'reports': request.POST.get('feature_reports') == 'on',
            'api': request.POST.get('feature_api') == 'on',
            'currencies': request.POST.get('feature_currencies') == 'on',
            'advanced_reports': request.POST.get('feature_advanced_reports') == 'on',
            'support': request.POST.get('feature_support') == 'on',
            'domain': request.POST.get('feature_domain') == 'on',
        }
        
        plan = SubscriptionPlan.objects.create(
            name=name,
            code=code.upper(),
            price_monthly=price_monthly,
            price_yearly=price_yearly,
            max_users=max_users,
            max_products=max_products,
            max_branches=max_branches,
            max_storage_gb=max_storage_gb,
            features=features,
            icon=icon,
            color=color,
            description=description,
            is_active=is_active
        )
        
        messages.success(request, f'Plan "{plan.name}" created successfully!')
        return redirect('tenants:subscription_plans_list')
    
    context = {
        'is_super_admin': True,
    }
    return render(request, 'shared/subscription_plan_create.html', context)


@login_required
def subscription_plan_edit(request, pk):
    """Edit a subscription plan - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can edit subscription plans.')
        return redirect('dashboard')
    
    plan = get_object_or_404(SubscriptionPlan, pk=pk)
    
    if request.method == 'POST':
        plan.name = request.POST.get('name', plan.name)
        plan.code = request.POST.get('code', plan.code).upper()
        plan.price_monthly = request.POST.get('price_monthly', plan.price_monthly)
        plan.price_yearly = request.POST.get('price_yearly', plan.price_yearly)
        plan.max_users = request.POST.get('max_users', plan.max_users)
        plan.max_products = request.POST.get('max_products', plan.max_products)
        plan.max_branches = request.POST.get('max_branches', plan.max_branches)
        plan.max_storage_gb = request.POST.get('max_storage_gb', plan.max_storage_gb)
        plan.icon = request.POST.get('icon', plan.icon)
        plan.color = request.POST.get('color', plan.color)
        plan.description = request.POST.get('description', plan.description)
        plan.is_active = request.POST.get('is_active') == 'on'
        
        plan.features = {
            'reports': request.POST.get('feature_reports') == 'on',
            'api': request.POST.get('feature_api') == 'on',
            'currencies': request.POST.get('feature_currencies') == 'on',
            'advanced_reports': request.POST.get('feature_advanced_reports') == 'on',
            'support': request.POST.get('feature_support') == 'on',
            'domain': request.POST.get('feature_domain') == 'on',
        }
        
        plan.save()
        messages.success(request, f'Plan "{plan.name}" updated successfully!')
        return redirect('tenants:subscription_plans_list')
    
    context = {
        'plan': plan,
        'is_super_admin': True,
    }
    return render(request, 'shared/subscription_plan_edit.html', context)


@login_required
def subscription_plan_delete(request, pk):
    """Delete a subscription plan - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can delete subscription plans.')
        return redirect('dashboard')
    
    plan = get_object_or_404(SubscriptionPlan, pk=pk)
    
    if request.method == 'POST':
        plan_name = plan.name
        plan.delete()
        messages.success(request, f'Plan "{plan_name}" deleted successfully!')
        return redirect('tenants:subscription_plans_list')
    
    context = {
        'plan': plan,
        'is_super_admin': True,
    }
    return render(request, 'shared/subscription_plan_confirm_delete.html', context)





# ============================================
# TENANT SUBSCRIPTION - ALLOWS TENANT ADMIN
# ============================================

@login_required
def tenant_subscription(request, tenant_id):
    """View tenant subscription details - Super Admin or Tenant Admin"""
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if not has_tenant_access(request.user, tenant):
        messages.error(request, 'Access denied. You do not have permission to view this subscription.')
        return redirect('dashboard')
    
    # Get ALL active subscription plans for tenants to see
    all_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
    
    # Get current subscription
    current_subscription = None
    if hasattr(tenant, 'subscription_plan') and tenant.subscription_plan:
        try:
            current_subscription = SubscriptionPlan.objects.get(code=tenant.subscription_plan)
        except SubscriptionPlan.DoesNotExist:
            pass
    
    # Check subscription status
    is_subscription_active = False
    days_remaining = 0
    
    if hasattr(tenant, 'subscription_end') and tenant.subscription_end:
        today = timezone.now().date()
        end_date = tenant.subscription_end
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        if end_date > today:
            is_subscription_active = True
            days_remaining = (end_date - today).days
    
    # ✅ Calculate usage statistics based on current subscription
    tenant_users_count = User.objects.filter(tenant=tenant, is_active=True).count()
    tenant_products_count = Product.objects.filter(tenant=tenant, is_active=True).count()
    tenant_branches_count = Branch.objects.filter(tenant=tenant, is_active=True).count()
    tenant_storage_used = 0  # You can calculate this if you have storage tracking
    
    # Calculate percentages
    tenant_users_percentage = 0
    tenant_products_percentage = 0
    tenant_branches_percentage = 0
    tenant_storage_percentage = 0
    
    if current_subscription:
        if current_subscription.max_users > 0:
            tenant_users_percentage = min(100, (tenant_users_count / current_subscription.max_users) * 100)
        if current_subscription.max_products > 0:
            tenant_products_percentage = min(100, (tenant_products_count / current_subscription.max_products) * 100)
        if current_subscription.max_branches > 0:
            tenant_branches_percentage = min(100, (tenant_branches_count / current_subscription.max_branches) * 100)
        if current_subscription.max_storage_gb > 0:
            tenant_storage_percentage = min(100, (tenant_storage_used / current_subscription.max_storage_gb) * 100)
    
    # Get subscription history
    subscription_history = SubscriptionInvoice.objects.filter(tenant=tenant).order_by('-created_at')
    
    context = {
        'tenant': tenant,
        'all_plans': all_plans,
        'current_subscription': current_subscription,
        'is_subscription_active': is_subscription_active,
        'days_remaining': days_remaining,
        'is_super_admin': is_super_admin(request.user),
        'is_tenant_admin': is_tenant_admin(request.user),
        # Usage statistics
        'tenant_users_count': tenant_users_count,
        'tenant_products_count': tenant_products_count,
        'tenant_branches_count': tenant_branches_count,
        'tenant_storage_used': tenant_storage_used,
        'tenant_users_percentage': tenant_users_percentage,
        'tenant_products_percentage': tenant_products_percentage,
        'tenant_branches_percentage': tenant_branches_percentage,
        'tenant_storage_percentage': tenant_storage_percentage,
        # Subscription history
        'subscription_history': subscription_history,
    }
    return render(request, 'shared/tenant_subscription_detail.html', context)


@login_required
def renew_subscription(request, tenant_id):
    """Renew tenant subscription - Super Admin or Tenant Admin"""
    tenant = get_object_or_404(Tenant, id=tenant_id)
    
    if not has_tenant_access(request.user, tenant):
        messages.error(request, 'Access denied. You do not have permission to renew this subscription.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        plan_code = request.POST.get('plan_code')
        duration = request.POST.get('duration', 'monthly')
        
        plan = get_object_or_404(SubscriptionPlan, code=plan_code)
        
        tenant.subscription_plan = plan.code
        tenant.subscription_start = timezone.now()
        
        if duration == 'monthly':
            tenant.subscription_end = timezone.now() + timedelta(days=30)
        elif duration == 'yearly':
            tenant.subscription_end = timezone.now() + timedelta(days=365)
        else:
            tenant.subscription_end = timezone.now() + timedelta(days=30)
        
        tenant.status = 'active'
        tenant.save()
        
        # Create invoice
        invoice = SubscriptionInvoice.objects.create(
            tenant=tenant,
            plan=plan.name,
            amount=plan.price_monthly if duration == 'monthly' else plan.price_yearly,
            period_start=timezone.now(),
            period_end=tenant.subscription_end,
            status='pending'
        )
        
        messages.success(request, f'Subscription renewed for {tenant.company_name}!')
        return redirect('tenants:tenant_subscription', tenant_id=tenant.id)
    
    # ✅ Get all active plans
    all_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
    
    context = {
        'tenant': tenant,
        'all_plans': all_plans,  # ✅ Passed as all_plans
        'is_super_admin': is_super_admin(request.user),
        'is_tenant_admin': is_tenant_admin(request.user),
    }
    return render(request, 'shared/renew_subscription.html', context)


@login_required
def subscription_users(request):
    """View all subscription users - Super Admin only"""
    if not is_super_admin(request.user):
        messages.error(request, 'Access denied. Only Super Admins can view subscription users.')
        return redirect('dashboard')
    
    tenants = Tenant.objects.all().order_by('-created_at')
    
    # Calculate counts
    active_count = 0
    expired_count = 0
    expiring_soon_count = 0
    total_revenue = 0
    
    for tenant in tenants:
        # Check subscription status
        is_active = False
        days_left = 0
        
        if hasattr(tenant, 'subscription_end') and tenant.subscription_end:
            from django.utils import timezone
            today = timezone.now().date()
            end_date = tenant.subscription_end
            if isinstance(end_date, datetime):
                end_date = end_date.date()
            
            if end_date > today:
                is_active = True
                days_left = (end_date - today).days
        
        if is_active:
            active_count += 1
            if days_left <= 7:
                expiring_soon_count += 1
        elif hasattr(tenant, 'subscription_end') and tenant.subscription_end:
            expired_count += 1
        
        # Calculate revenue
        if hasattr(tenant, 'subscription_plan') and tenant.subscription_plan:
            try:
                plan = SubscriptionPlan.objects.get(code=tenant.subscription_plan)
                total_revenue += float(plan.price_monthly)
            except:
                pass
    
    context = {
        'tenants': tenants,
        'active_count': active_count,
        'expired_count': expired_count,
        'expiring_soon_count': expiring_soon_count,
        'total_revenue': total_revenue,
        'is_super_admin': True,
    }
    return render(request, 'shared/subscription_users.html', context)

# ============================================
# TENANT ADMIN - MY SUBSCRIPTION
# ============================================

@login_required
def my_subscription(request, tenant_id=None):
    """View current user's tenant subscription - Tenant Admin"""
    
    # If tenant_id is provided, use it
    if tenant_id:
        tenant = get_object_or_404(Tenant, id=tenant_id)
    else:
        tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account.')
        return redirect('dashboard')
    
    # Get ALL active subscription plans for tenants to see
    all_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
    
    current_subscription = None
    if hasattr(tenant, 'subscription_plan') and tenant.subscription_plan:
        try:
            current_subscription = SubscriptionPlan.objects.get(code=tenant.subscription_plan)
        except SubscriptionPlan.DoesNotExist:
            pass
    
    # Check subscription status
    is_subscription_active = False
    days_remaining = 0
    
    if hasattr(tenant, 'subscription_end') and tenant.subscription_end:
        today = timezone.now().date()
        end_date = tenant.subscription_end
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        if end_date > today:
            is_subscription_active = True
            days_remaining = (end_date - today).days
    
    context = {
        'tenant': tenant,
        'all_plans': all_plans,
        'current_subscription': current_subscription,
        'is_subscription_active': is_subscription_active,
        'days_remaining': days_remaining,
        'is_tenant_admin': True,
    }
    return render(request, 'shared/my_subscription.html', context)