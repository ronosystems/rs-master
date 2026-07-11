# apps/rental_master/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from datetime import datetime, timedelta, date
from .models import (
    Branch,  RoomSize, PropertyType, Property, 
    RentalUnit, Lease, TenantProfile, RentPayment, 
    Deposit
)


# ============================================
# DASHBOARD VIEW
# ============================================
@login_required
def dashboard(request):
    """Rental Master Dashboard"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned.')
        return redirect('portal:dashboard')
    
    # Get all data
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    total_branches = branches.count()
    
    properties = Property.objects.filter(tenant=tenant, is_active=True)
    total_properties = properties.count()
    
    rental_units = RentalUnit.objects.filter(tenant=tenant, is_active=True)
    total_units = rental_units.count()
    
    occupied_units = rental_units.filter(status='occupied').count()
    available_units = rental_units.filter(status='available').count()
    reserved_units = rental_units.filter(status='reserved').count()
    maintenance_units = rental_units.filter(status='maintenance').count()
    
    # Occupancy rate
    occupancy_rate = 0
    if total_units > 0:
        occupancy_rate = round((occupied_units / total_units) * 100, 1)
    
    # Calculate monthly revenue
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    monthly_revenue = RentPayment.objects.filter(
        tenant=tenant,
        payment_date__year=current_year,
        payment_date__month=current_month,
        payment_status='paid'
    ).aggregate(
        total=Sum('amount_paid')
    )['total'] or Decimal('0.00')
    
    # Recent payments
    recent_payments = RentPayment.objects.filter(
        tenant=tenant
    ).select_related('rental_unit', 'tenant_profile').order_by('-payment_date')[:5]
    
    # Active leases
    active_leases = Lease.objects.filter(
        tenant=tenant,
        is_active=True,
        status='active'
    ).select_related('rental_unit', 'rental_unit__property', 'client_tenant').order_by('end_date')[:5]
    
    # Expiring leases (next 30 days)
    thirty_days_from_now = date.today() + timedelta(days=30)
    expiring_leases = Lease.objects.filter(
        tenant=tenant,
        is_active=True,
        status='active',
        end_date__lte=thirty_days_from_now,
        end_date__gte=date.today()
    ).select_related('rental_unit', 'rental_unit__property', 'client_tenant').order_by('end_date')[:5]
    
    # Recent tenants
    recent_tenants = TenantProfile.objects.filter(
        tenant=tenant,
        is_active=True
    ).order_by('-created_at')[:5]
    
    # Recent deposits
    recent_deposits = Deposit.objects.filter(
        tenant=tenant
    ).select_related('tenant_profile', 'rental_unit').order_by('-payment_date')[:5]
    
    # Income by unit type
    income_by_type = RentPayment.objects.filter(
        tenant=tenant,
        payment_status='paid'
    ).values(
        'rental_unit__unit_type'
    ).annotate(
        total=Sum('amount_paid')
    ).order_by('-total')
    
    # Branch statistics
    branch_stats = []
    for branch in branches:
        branch_units = RentalUnit.objects.filter(property__branch=branch, is_active=True)
        branch_stats.append({
            'branch': branch,
            'total_units': branch_units.count(),
            'occupied_units': branch_units.filter(status='occupied').count(),
            'available_units': branch_units.filter(status='available').count(),
        })
    
    context = {
        'tenant': tenant,
        'active_tab': 'dashboard',
        'project_type': 'RENTAL_MASTER',
        
        # Stats
        'total_branches': total_branches,
        'total_properties': total_properties,
        'total_units': total_units,
        'occupied_units': occupied_units,
        'available_units': available_units,
        'reserved_units': reserved_units,
        'maintenance_units': maintenance_units,
        'occupancy_rate': occupancy_rate,
        'monthly_revenue': monthly_revenue,
        
        # Lists
        'recent_payments': recent_payments,
        'active_leases': active_leases,
        'expiring_leases': expiring_leases,
        'recent_tenants': recent_tenants,
        'recent_deposits': recent_deposits,
        'branch_stats': branch_stats,
        'income_by_type': income_by_type,
    }
    return render(request, 'rental_master/dashboard.html', context)


# ============================================
# BRANCH VIEWS
# ============================================
@login_required
def branches(request):
    """List branches"""
    tenant = request.user.tenant
    branches_list = Branch.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'branches': branches_list,
        'active_tab': 'branches',
    }
    return render(request, 'rental_master/branches.html', context)


@login_required
def add_branch(request):
    """Add a new branch"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        city = request.POST.get('city')
        contact_person = request.POST.get('contact_person')
        contact_phone = request.POST.get('contact_phone')
        
        if name and location:
            branch = Branch.objects.create(
                tenant=tenant,
                name=name,
                location=location,
                city=city,
                contact_person=contact_person,
                contact_phone=contact_phone,
                is_active=True
            )
            messages.success(request, f'Branch "{branch.name}" created successfully!')
            return redirect('rental_master:branches')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'active_tab': 'branches',
    }
    return render(request, 'rental_master/add_branch.html', context)


@login_required
def branch_detail(request, branch_id):
    """Branch detail view"""
    tenant = request.user.tenant
    branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
    blocks = branch.blocks.filter(is_active=True)
    properties = branch.properties.filter(is_active=True)
    
    context = {
        'tenant': tenant,
        'branch': branch,
        'blocks': blocks,
        'properties': properties,
        'active_tab': 'branches',
    }
    return render(request, 'rental_master/branch_detail.html', context)


# ============================================
# PROPERTY VIEWS
# ============================================
@login_required
def properties(request):
    """List properties"""
    tenant = request.user.tenant
    branch_id = request.GET.get('branch')
    
    properties_list = Property.objects.filter(tenant=tenant, is_active=True)
    if branch_id:
        properties_list = properties_list.filter(branch_id=branch_id)
    
    # Get all branches for filter
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'properties': properties_list,
        'branches': branches,
        'active_tab': 'properties',
    }
    return render(request, 'rental_master/properties.html', context)


@login_required
def add_property(request):
    """Add a new property"""
    tenant = request.user.tenant
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        branch_id = request.POST.get('branch')
        property_type_name = request.POST.get('property_type_name')  # Now text input
        location = request.POST.get('location')
        description = request.POST.get('description')
        
        if name and branch_id and property_type_name:
            branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
            
            # Get or create property type
            property_type, created = PropertyType.objects.get_or_create(
                tenant=tenant,
                name=property_type_name.strip(),
                defaults={'description': f'{property_type_name} property'}
            )
            
            property_obj = Property.objects.create(
                tenant=tenant,
                branch=branch,
                property_type=property_type,
                name=name,
                location=location,
                description=description,
                is_active=True
            )
            
            if created:
                messages.success(request, f'Property type "{property_type_name}" created automatically!')
            messages.success(request, f'Property "{property_obj.name}" created successfully!')
            return redirect('rental_master:properties')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'branches': branches,
        'active_tab': 'properties',
    }
    return render(request, 'rental_master/add_property.html', context)


@login_required
def property_detail(request, property_id):
    """Property detail view"""
    tenant = request.user.tenant
    property_obj = get_object_or_404(Property, id=property_id, tenant=tenant)
    units = property_obj.rental_units.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'property': property_obj,
        'units': units,
        'active_tab': 'properties',
    }
    return render(request, 'rental_master/property_detail.html', context)



@login_required
def property_types(request):
    """Manage property types"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        
        # Check if action is delete
        if request.POST.get('action') == 'delete':
            type_id = request.POST.get('type_id')
            if type_id:
                try:
                    property_type = PropertyType.objects.get(id=type_id, tenant=tenant)
                    property_type.is_active = False
                    property_type.save()
                    messages.success(request, f'Property type "{property_type.name}" deactivated.')
                except PropertyType.DoesNotExist:
                    messages.error(request, 'Property type not found.')
            return redirect('rental_master:property_types')
        
        if name:
            property_type, created = PropertyType.objects.get_or_create(
                tenant=tenant,
                name=name.strip(),
                defaults={'description': description or ''}
            )
            if created:
                messages.success(request, f'Property type "{property_type.name}" created successfully!')
            else:
                messages.info(request, f'Property type "{property_type.name}" already exists.')
            return redirect('rental_master:property_types')
        else:
            messages.error(request, 'Please enter a property type name.')
    
    property_types_list = PropertyType.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    context = {
        'tenant': tenant,
        'property_types': property_types_list,
        'active_tab': 'settings',
    }
    return render(request, 'rental_master/settings/property_types.html', context)


# ============================================
# UNIT VIEWS
# ============================================
@login_required
def units(request):
    """List rental units with filters"""
    tenant = request.user.tenant
    
    units_list = RentalUnit.objects.filter(tenant=tenant, is_active=True).select_related(
        'property', 'block', 'room_size'
    ).order_by('property__name', 'unit_number')
    
    # Filters
    property_id = request.GET.get('property')
    if property_id:
        units_list = units_list.filter(property_id=property_id)
    
    branch_id = request.GET.get('branch')
    if branch_id:
        units_list = units_list.filter(property__branch_id=branch_id)
    
    status = request.GET.get('status')
    if status:
        units_list = units_list.filter(status=status)
    
    unit_type = request.GET.get('unit_type')
    if unit_type:
        units_list = units_list.filter(unit_type=unit_type)
    
    # Get filter options
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    properties = Property.objects.filter(tenant=tenant, is_active=True)
    room_sizes = RoomSize.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'units': units_list,
        'branches': branches,
        'properties': properties,
        'room_sizes': room_sizes,
        'active_tab': 'units',
    }
    return render(request, 'rental_master/units.html', context)

@login_required
def add_unit(request):
    """Add a new rental unit"""
    tenant = request.user.tenant
    properties = Property.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        property_id = request.POST.get('property')
        unit_number = request.POST.get('unit_number')
        unit_type = request.POST.get('unit_type')  # Now text input
        monthly_rent = request.POST.get('monthly_rent')
        deposit_amount = request.POST.get('deposit_amount')
        status = request.POST.get('status', 'available')
        
        if property_id and unit_number and monthly_rent:
            property_obj = get_object_or_404(Property, id=property_id, tenant=tenant)
            
            unit = RentalUnit.objects.create(
                tenant=tenant,
                property=property_obj,
                unit_number=unit_number,
                unit_type=unit_type or 'room',  # Default to room if not specified
                monthly_rent=monthly_rent,
                deposit_amount=deposit_amount or 0,
                status=status,
                is_active=True
            )
            messages.success(request, f'Unit "{unit.unit_number}" created successfully!')
            return redirect('rental_master:units')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'properties': properties,
        'active_tab': 'units',
    }
    return render(request, 'rental_master/add_unit.html', context)

@login_required
def unit_detail(request, unit_id):
    """Unit detail view"""
    tenant = request.user.tenant
    unit = get_object_or_404(RentalUnit, id=unit_id, tenant=tenant)
    
    # Get lease history
    leases = unit.leases.filter(tenant=tenant).order_by('-start_date')
    current_lease = leases.filter(is_active=True, status='active').first()
    
    # Get payment history
    payments = unit.payments.filter(tenant=tenant).order_by('-payment_date')
    
    # Get deposits
    deposits = unit.deposits.filter(tenant=tenant).order_by('-payment_date')
    
    context = {
        'tenant': tenant,
        'unit': unit,
        'leases': leases,
        'current_lease': current_lease,
        'payments': payments[:10],
        'deposits': deposits,
        'active_tab': 'units',
    }
    return render(request, 'rental_master/unit_detail.html', context)

@login_required
def get_units_data(request):
    """API endpoint to get branches, properties, and units data"""
    tenant = request.user.tenant
    
    # Get all branches with their properties
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    properties_data = {}
    units_data = {}
    
    for branch in branches:
        properties = Property.objects.filter(tenant=tenant, branch=branch, is_active=True)
        properties_data[branch.id] = [
            {'id': prop.id, 'name': prop.name}
            for prop in properties
        ]
        
        for prop in properties:
            units = RentalUnit.objects.filter(
                tenant=tenant, 
                property=prop, 
                is_active=True,
                status='available'  # Only show available units
            )
            units_data[prop.id] = [
                {
                    'id': unit.id,
                    'unit_number': unit.unit_number,
                    'unit_type': unit.get_unit_type_display(),
                    'monthly_rent': str(unit.monthly_rent),
                    'deposit_amount': str(unit.deposit_amount),
                    'property_name': prop.name
                }
                for unit in units
            ]
    
    return JsonResponse({
        'properties': properties_data,
        'units': units_data
    })


# ============================================
# TENANT VIEWS
# ============================================
@login_required
def tenants_list(request):
    """List client tenants"""
    tenant = request.user.tenant
    tenants = TenantProfile.objects.filter(tenant=tenant, is_active=True).order_by('-created_at')
    
    # Filter by active lease
    has_active_lease = request.GET.get('has_active_lease')
    if has_active_lease:
        if has_active_lease == 'yes':
            tenants = tenants.filter(leases__is_active=True, leases__status='active').distinct()
        elif has_active_lease == 'no':
            tenants = tenants.exclude(leases__is_active=True, leases__status='active')
    
    context = {
        'tenant': tenant,
        'tenants': tenants,
        'active_tab': 'tenants',
    }
    return render(request, 'rental_master/tenants.html', context)

@login_required
def add_tenant(request):
    """Add a new tenant with branch → property → unit selection"""
    tenant = request.user.tenant
    
    # Get all branches for selection
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        # Get tenant details
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        id_number = request.POST.get('id_number')
        tenant_type = request.POST.get('tenant_type', 'individual')
        company_name = request.POST.get('company_name')
        alternative_phone = request.POST.get('alternative_phone')
        physical_address = request.POST.get('physical_address')
        start_date = request.POST.get('start_date')
        
        # Get unit selection
        unit_id = request.POST.get('unit')
        
        # Get checkboxes
        rent_paid = request.POST.get('rent_paid') == 'on'
        deposit_paid = request.POST.get('deposit_paid') == 'on'
        agreement_signed = request.POST.get('agreement_signed') == 'on'
        terms_accepted = request.POST.get('terms_accepted') == 'on'
        
        # Validate required fields
        if not all([full_name, email, phone_number, id_number, unit_id, start_date]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'rental_master/add_tenant.html', {
                'tenant': tenant,
                'branches': branches,
                'active_tab': 'tenants',
            })
        
        if not agreement_signed:
            messages.error(request, 'Please confirm that the agreement has been signed.')
            return render(request, 'rental_master/add_tenant.html', {
                'tenant': tenant,
                'branches': branches,
                'active_tab': 'tenants',
            })
        
        if not terms_accepted:
            messages.error(request, 'Please accept the terms and conditions.')
            return render(request, 'rental_master/add_tenant.html', {
                'tenant': tenant,
                'branches': branches,
                'active_tab': 'tenants',
            })
        
        try:
            unit = RentalUnit.objects.get(id=unit_id, tenant=tenant)
        except RentalUnit.DoesNotExist:
            messages.error(request, 'Selected unit not found.')
            return render(request, 'rental_master/add_tenant.html', {
                'tenant': tenant,
                'branches': branches,
                'active_tab': 'tenants',
            })
        
        # Create tenant profile
        tenant_profile = TenantProfile.objects.create(
            tenant=tenant,
            full_name=full_name,
            email=email,
            phone_number=phone_number,
            id_number=id_number,
            tenant_type=tenant_type,
            company_name=company_name,
            alternative_phone=alternative_phone,
            physical_address=physical_address,
            is_active=True
        )
        
        # Create lease
        lease = Lease.objects.create(
            tenant=tenant,
            rental_unit=unit,
            client_tenant=tenant_profile,
            start_date=start_date,
            end_date=date.today() + timedelta(days=365),  # 1 year lease
            monthly_rent=unit.monthly_rent,
            deposit_due=unit.deposit_amount,
            deposit_paid=unit.deposit_amount if deposit_paid else 0,
            status='active',
            is_active=True
        )
        
        # Record rent payment if checked
        if rent_paid:
            RentPayment.objects.create(
                tenant=tenant,
                rental_unit=unit,
                tenant_profile=tenant_profile,
                lease=lease,
                amount_due=unit.monthly_rent,
                amount_paid=unit.monthly_rent,
                payment_date=start_date,
                due_date=start_date,
                payment_method='cash',
                payment_status='paid',
                is_recurring=True,
                recurring_month=date.today().month,
                recurring_year=date.today().year
            )
            messages.success(request, f'First month rent of KES {unit.monthly_rent} recorded.')
        
        # Record deposit if checked
        if deposit_paid and unit.deposit_amount > 0:
            Deposit.objects.create(
                tenant=tenant,
                tenant_profile=tenant_profile,
                rental_unit=unit,
                lease=lease,
                amount=unit.deposit_amount,
                payment_date=start_date,
                payment_method='cash',
                status='paid'
            )
            messages.success(request, f'Deposit of KES {unit.deposit_amount} recorded.')
        
        # Update unit status
        unit.status = 'occupied'
        unit.save()
        
        messages.success(request, f'Tenant "{full_name}" registered successfully for unit {unit.unit_number}!')
        return redirect('rental_master:tenants')
    
    context = {
        'tenant': tenant,
        'branches': branches,
        'active_tab': 'tenants',
        'today': date.today(),
    }
    return render(request, 'rental_master/add_tenant.html', context)

@login_required
def tenant_detail(request, tenant_id):
    """Client tenant detail view"""
    tenant = request.user.tenant
    client_tenant = get_object_or_404(TenantProfile, id=tenant_id, tenant=tenant)
    
    # Get leases
    leases = client_tenant.leases.filter(tenant=tenant).order_by('-start_date')
    
    # Get payments
    payments = client_tenant.payments.filter(tenant=tenant).order_by('-payment_date')
    
    # Get deposits
    deposits = client_tenant.deposits.filter(tenant=tenant).order_by('-payment_date')
    
    context = {
        'tenant': tenant,
        'client_tenant': client_tenant,
        'leases': leases,
        'payments': payments[:10],
        'deposits': deposits,
        'active_tab': 'tenants',
    }
    return render(request, 'rental_master/tenant_detail.html', context)


@login_required
def vacate_tenant(request, tenant_id):
    """Vacate/Move out a tenant"""
    tenant = request.user.tenant
    
    try:
        client_tenant = TenantProfile.objects.get(id=tenant_id, tenant=tenant)
    except TenantProfile.DoesNotExist:
        messages.error(request, 'Tenant not found.')
        return redirect('rental_master:tenants')
    
    if request.method == 'POST':
        vacate_reason = request.POST.get('vacate_reason')
        vacate_date = request.POST.get('vacate_date')
        
        # Helper function to safely convert to Decimal
        def parse_decimal(value):
            if not value:
                return Decimal('0.00')
            try:
                # Remove any commas and convert to float then Decimal
                cleaned = str(value).replace(',', '').strip()
                if not cleaned:
                    return Decimal('0.00')
                return Decimal(cleaned)
            except (ValueError, TypeError, InvalidOperation):
                return Decimal('0.00')
        
        pending_bills = parse_decimal(request.POST.get('pending_bills'))
        refund_deposit = request.POST.get('refund_deposit') == 'on'
        has_damages = request.POST.get('has_damages') == 'on'
        damages_description = request.POST.get('damages_description', '').strip()
        damages_cost = parse_decimal(request.POST.get('damages_cost'))
        vacate_notes = request.POST.get('vacate_notes', '').strip()
        
        # Get active lease
        active_lease = client_tenant.active_leases.first()
        if not active_lease:
            messages.error(request, 'No active lease found for this tenant.')
            return redirect('rental_master:tenant_detail', tenant_id=tenant_id)
        
        # Calculate refund
        deposit_paid = active_lease.deposit_paid or Decimal('0.00')
        refund_amount = Decimal('0.00')
        
        if refund_deposit:
            refund_amount = deposit_paid - pending_bills - damages_cost
            if refund_amount < 0:
                refund_amount = Decimal('0.00')
        
        # Update lease
        active_lease.status = 'terminated'
        active_lease.is_active = False
        active_lease.end_date = vacate_date
        
        # Add notes
        notes_parts = [f"Vacated on {vacate_date}. Reason: {vacate_reason}."]
        if vacate_notes:
            notes_parts.append(vacate_notes)
        if has_damages and damages_description:
            notes_parts.append(f"Damages: {damages_description} (Cost: KES {damages_cost:.2f})")
        if pending_bills > 0:
            notes_parts.append(f"Pending bills: KES {pending_bills:.2f}")
        if refund_amount > 0:
            notes_parts.append(f"Deposit refund: KES {refund_amount:.2f}")
        
        active_lease.notes = " ".join(notes_parts)
        active_lease.save()
        
        # Update unit
        unit = active_lease.rental_unit
        unit.status = 'available'
        unit.save()
        
        # Update tenant
        client_tenant.is_active = False
        client_tenant.save()
        
        # Create deposit refund record if applicable
        if refund_amount > 0:
            Deposit.objects.create(
                tenant=tenant,
                tenant_profile=client_tenant,
                rental_unit=unit,
                lease=active_lease,
                amount=refund_amount,
                payment_date=vacate_date,
                status='refunded',
                notes=f"Refund on vacate. Reason: {vacate_reason}",
                refund_date=vacate_date,
                refund_amount=refund_amount,
                refund_reason=f"Tenant vacated. {vacate_reason}"
            )
            messages.success(request, f'Deposit refund of KES {refund_amount:,.2f} processed.')
        
        # Record pending bills if any
        if pending_bills > 0:
            messages.info(request, f'Pending bills of KES {pending_bills:,.2f} recorded.')
        
        # Record damages if any
        if has_damages and damages_description:
            messages.warning(request, f'Damages recorded: {damages_description}. Repair cost: KES {damages_cost:,.2f}')
        
        messages.success(request, f'Tenant {client_tenant.full_name} has been moved out successfully. Unit {unit.unit_number} is now available.')
        return redirect('rental_master:tenants')
    
    return redirect('rental_master:tenant_detail', tenant_id=tenant_id)


# ============================================
# LEASE VIEWS
# ============================================
@login_required
def leases(request):
    """List all leases"""
    tenant = request.user.tenant
    leases_list = Lease.objects.filter(tenant=tenant).select_related(
        'rental_unit', 'rental_unit__property', 'client_tenant'
    ).order_by('-start_date')
    
    # Filters
    status = request.GET.get('status')
    if status:
        leases_list = leases_list.filter(status=status)
    
    is_active = request.GET.get('is_active')
    if is_active:
        leases_list = leases_list.filter(is_active=is_active == 'yes')
    
    context = {
        'tenant': tenant,
        'leases': leases_list,
        'active_tab': 'leases',
    }
    return render(request, 'rental_master/leases.html', context)

@login_required
def create_lease(request):
    """Create a new lease"""
    tenant = request.user.tenant
    units = RentalUnit.objects.filter(tenant=tenant, is_active=True, status='available')
    tenants = TenantProfile.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        unit_id = request.POST.get('unit')
        tenant_id = request.POST.get('tenant')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        monthly_rent = request.POST.get('monthly_rent')
        deposit_amount = request.POST.get('deposit_amount', 0)
        
        if unit_id and tenant_id and start_date and end_date and monthly_rent:
            unit = get_object_or_404(RentalUnit, id=unit_id, tenant=tenant)
            client_tenant = get_object_or_404(TenantProfile, id=tenant_id, tenant=tenant)
            
            lease = Lease.objects.create(
                tenant=tenant,
                rental_unit=unit,
                client_tenant=client_tenant,
                start_date=start_date,
                end_date=end_date,
                monthly_rent=monthly_rent,
                deposit_due=deposit_amount,
                status='active',
                is_active=True
            )
            messages.success(request, f'Lease created successfully for {client_tenant.full_name}!')
            return redirect('rental_master:leases')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'units': units,
        'tenants': tenants,
        'active_tab': 'leases',
    }
    return render(request, 'rental_master/create_lease.html', context)


# ============================================
# PAYMENT VIEWS
# ============================================
@login_required
def payments(request):
    """List all payments with filters"""
    tenant = request.user.tenant
    payments_list = RentPayment.objects.filter(tenant=tenant).select_related(
        'rental_unit', 'tenant_profile', 'lease'
    ).order_by('-payment_date')
    
    # Filters
    status = request.GET.get('status')
    if status:
        payments_list = payments_list.filter(payment_status=status)
    
    property_id = request.GET.get('property')
    if property_id:
        payments_list = payments_list.filter(rental_unit__property_id=property_id)
    
    unit_id = request.GET.get('unit')
    if unit_id:
        payments_list = payments_list.filter(rental_unit_id=unit_id)
    
    date_from = request.GET.get('date_from')
    if date_from:
        payments_list = payments_list.filter(payment_date__gte=date_from)
    
    date_to = request.GET.get('date_to')
    if date_to:
        payments_list = payments_list.filter(payment_date__lte=date_to)
    
    context = {
        'tenant': tenant,
        'payments': payments_list,
        'active_tab': 'payments',
    }
    return render(request, 'rental_master/payments.html', context)

@login_required
def record_payment(request):
    """Record a new payment"""
    tenant = request.user.tenant
    units = RentalUnit.objects.filter(tenant=tenant, is_active=True)
    tenants = TenantProfile.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        unit_id = request.POST.get('unit')
        tenant_id = request.POST.get('tenant')
        amount_paid = request.POST.get('amount_paid')
        payment_date = request.POST.get('payment_date')
        payment_method = request.POST.get('payment_method', 'cash')
        
        if unit_id and tenant_id and amount_paid and payment_date:
            unit = get_object_or_404(RentalUnit, id=unit_id, tenant=tenant)
            client_tenant = get_object_or_404(TenantProfile, id=tenant_id, tenant=tenant)
            
            payment = RentPayment.objects.create(
                tenant=tenant,
                rental_unit=unit,
                tenant_profile=client_tenant,
                amount_due=amount_paid,
                amount_paid=amount_paid,
                payment_date=payment_date,
                due_date=payment_date,
                payment_method=payment_method,
                payment_status='paid'
            )
            messages.success(request, f'Payment of KES {amount_paid} recorded successfully!')
            return redirect('rental_master:payments')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'units': units,
        'tenants': tenants,
        'active_tab': 'payments',
    }
    return render(request, 'rental_master/record_payment.html', context)


# ============================================
# DEPOSIT VIEWS
# ============================================
@login_required
def deposits(request):
    """List all deposits"""
    tenant = request.user.tenant
    deposits_list = Deposit.objects.filter(tenant=tenant).select_related(
        'tenant_profile', 'rental_unit', 'lease'
    ).order_by('-payment_date')
    
    # Filters
    status = request.GET.get('status')
    if status:
        deposits_list = deposits_list.filter(status=status)
    
    context = {
        'tenant': tenant,
        'deposits': deposits_list,
        'active_tab': 'deposits',
    }
    return render(request, 'rental_master/deposits.html', context)


# ============================================
# REPORT VIEWS
# ============================================
@login_required
def occupancy_report(request):
    """Occupancy report"""
    tenant = request.user.tenant
    
    # Get occupancy data
    total_units = RentalUnit.objects.filter(tenant=tenant, is_active=True).count()
    occupied_units = RentalUnit.objects.filter(tenant=tenant, is_active=True, status='occupied').count()
    available_units = RentalUnit.objects.filter(tenant=tenant, is_active=True, status='available').count()
    
    # Get occupancy by property
    property_occupancy = Property.objects.filter(tenant=tenant, is_active=True).annotate(
        total_units=Count('rental_units'),
        occupied_units=Count('rental_units', filter=Q(rental_units__status='occupied'))
    ).values('name', 'total_units', 'occupied_units')
    
    # Get occupancy by unit type
    type_occupancy = RentalUnit.objects.filter(tenant=tenant, is_active=True).values('unit_type').annotate(
        total=Count('id'),
        occupied=Count('id', filter=Q(status='occupied'))
    )
    
    context = {
        'tenant': tenant,
        'total_units': total_units,
        'occupied_units': occupied_units,
        'available_units': available_units,
        'property_occupancy': property_occupancy,
        'type_occupancy': type_occupancy,
        'active_tab': 'reports',
    }
    return render(request, 'rental_master/reports/occupancy.html', context)


@login_required
def revenue_report(request):
    """Revenue report"""
    tenant = request.user.tenant
    
    # Monthly revenue for the last 12 months
    twelve_months_ago = date.today() - timedelta(days=365)
    monthly_revenue = RentPayment.objects.filter(
        tenant=tenant,
        payment_status='paid',
        payment_date__gte=twelve_months_ago
    ).annotate(
        month=TruncMonth('payment_date')
    ).values('month').annotate(
        total=Sum('amount_paid')
    ).order_by('month')
    
    # Revenue by property
    property_revenue = RentPayment.objects.filter(
        tenant=tenant,
        payment_status='paid'
    ).values('rental_unit__property__name').annotate(
        total=Sum('amount_paid')
    ).order_by('-total')
    
    # Revenue by unit type
    type_revenue = RentPayment.objects.filter(
        tenant=tenant,
        payment_status='paid'
    ).values('rental_unit__unit_type').annotate(
        total=Sum('amount_paid')
    ).order_by('-total')
    
    # Total revenue
    total_revenue = RentPayment.objects.filter(
        tenant=tenant,
        payment_status='paid'
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    context = {
        'tenant': tenant,
        'monthly_revenue': monthly_revenue,
        'property_revenue': property_revenue,
        'type_revenue': type_revenue,
        'total_revenue': total_revenue,
        'active_tab': 'reports',
    }
    return render(request, 'rental_master/reports/revenue.html', context)


@login_required
def rent_collection(request):
    """Rent collection report"""
    tenant = request.user.tenant
    
    # Get all units with their payment status
    units = RentalUnit.objects.filter(tenant=tenant, is_active=True).select_related('property')
    
    # Get current month payments
    current_month = date.today().month
    current_year = date.today().year
    
    unit_payment_status = []
    for unit in units:
        # Check if payment exists for this month
        payment = RentPayment.objects.filter(
            tenant=tenant,
            rental_unit=unit,
            payment_date__month=current_month,
            payment_date__year=current_year
        ).first()
        
        status = 'pending'
        if payment:
            if payment.payment_status == 'paid':
                status = 'paid'
            elif payment.payment_status == 'partial':
                status = 'partial'
            elif payment.payment_status == 'overdue':
                status = 'overdue'
        
        unit_payment_status.append({
            'unit': unit,
            'status': status,
            'amount_due': unit.monthly_rent,
            'amount_paid': payment.amount_paid if payment else 0,
            'payment_date': payment.payment_date if payment else None
        })
    
    context = {
        'tenant': tenant,
        'unit_payment_status': unit_payment_status,
        'current_month': date.today().strftime('%B %Y'),
        'active_tab': 'reports',
    }
    return render(request, 'rental_master/reports/rent_collection.html', context)


@login_required
def export_reports(request):
    """Export reports"""
    tenant = request.user.tenant
    context = {
        'tenant': tenant,
        'active_tab': 'reports',
    }
    return render(request, 'rental_master/reports/export.html', context)


# ============================================
# SETTINGS VIEWS
# ============================================
@login_required
def room_sizes(request):
    """Manage room sizes"""
    tenant = request.user.tenant
    room_sizes_list = RoomSize.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        standard_price = request.POST.get('standard_price')
        description = request.POST.get('description')
        
        if name:
            room_size = RoomSize.objects.create(
                tenant=tenant,
                name=name,
                standard_price=standard_price or 0,
                description=description,
                is_active=True
            )
            messages.success(request, f'Room size "{room_size.name}" created successfully!')
            return redirect('rental_master:room_sizes')
        else:
            messages.error(request, 'Please enter a room size name.')
    
    context = {
        'tenant': tenant,
        'room_sizes': room_sizes_list,
        'active_tab': 'settings',
    }
    return render(request, 'rental_master/settings/room_sizes.html', context)


# ============================================
# MAINTENANCE VIEWS (CARETAKER)
# ============================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta, date
from .models import (
    Branch, RoomSize, PropertyType, Property, 
    RentalUnit, Lease, TenantProfile, RentPayment, 
    Deposit,  MaintenanceRequest
)

@login_required
def maintenance_requests(request):
    """List maintenance requests with filters"""
    tenant = request.user.tenant
    
    # Get all maintenance requests for this tenant
    requests_list = MaintenanceRequest.objects.filter(
        tenant=tenant
    ).select_related('rental_unit', 'rental_unit__property')
    
    # Apply filters
    status = request.GET.get('status')
    if status:
        requests_list = requests_list.filter(status=status)
    
    priority = request.GET.get('priority')
    if priority:
        requests_list = requests_list.filter(priority=priority)
    
    category = request.GET.get('category')
    if category:
        requests_list = requests_list.filter(category=category)
    
    # Order by priority and date
    requests_list = requests_list.order_by(
        '-priority', '-created_at'
    )
    
    # Statistics
    total_requests = requests_list.count()
    pending_count = requests_list.filter(status='pending').count()
    in_progress_count = requests_list.filter(status='in_progress').count()
    completed_count = requests_list.filter(status='completed').count()
    cancelled_count = requests_list.filter(status='cancelled').count()
    
    # Get urgent requests
    urgent_requests = requests_list.filter(priority='urgent', status__in=['pending', 'in_progress'])
    
    # Get overdue requests
    overdue_requests = requests_list.filter(
        scheduled_date__lt=timezone.now(),
        status__in=['pending', 'in_progress']
    )
    
    context = {
        'tenant': tenant,
        'requests': requests_list,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
        'cancelled_count': cancelled_count,
        'urgent_requests': urgent_requests,
        'overdue_requests': overdue_requests,
        'active_tab': 'maintenance',
    }
    return render(request, 'rental_master/maintenance_list.html', context)


@login_required
def new_request(request):
    """Create a new maintenance request"""
    tenant = request.user.tenant
    
    # Get all branches and properties for the form
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    properties = Property.objects.filter(tenant=tenant, is_active=True)
    units = RentalUnit.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        branch_id = request.POST.get('branch')
        property_id = request.POST.get('property')
        unit_id = request.POST.get('unit')
        title = request.POST.get('title')
        priority = request.POST.get('priority')
        category = request.POST.get('category')
        reported_by = request.POST.get('reported_by')
        description = request.POST.get('description')
        scheduled_date = request.POST.get('scheduled_date')
        
        # Validate required fields
        if not all([unit_id, title, priority, category, description]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'rental_master/maintenance_request.html', {
                'tenant': tenant,
                'branches': branches,
                'properties': properties,
                'units': units,
                'active_tab': 'maintenance',
            })
        
        try:
            unit = RentalUnit.objects.get(id=unit_id, tenant=tenant)
        except RentalUnit.DoesNotExist:
            messages.error(request, 'Selected unit not found.')
            return redirect('rental_master:maintenance_requests')
        
        # Create maintenance request
        maintenance_request = MaintenanceRequest.objects.create(
            tenant=tenant,
            rental_unit=unit,
            title=title,
            description=description,
            priority=priority,
            category=category,
            reported_by=reported_by or request.user.get_full_name() or request.user.username,
            status='pending',
            scheduled_date=scheduled_date if scheduled_date else None,
        )
        
        messages.success(request, f'Maintenance request "{title}" created successfully!')
        return redirect('rental_master:maintenance_requests')
    
    context = {
        'tenant': tenant,
        'branches': branches,
        'properties': properties,
        'units': units,
        'active_tab': 'maintenance',
    }
    return render(request, 'rental_master/maintenance_request.html', context)


@login_required
def task_list(request):
    """List maintenance tasks"""
    tenant = request.user.tenant
    
    # Get all tasks for this tenant
    tasks = MaintenanceRequest.objects.filter(
        tenant=tenant
    ).select_related('rental_unit', 'rental_unit__property')
    
    # Apply filters
    status = request.GET.get('status')
    if status:
        tasks = tasks.filter(status=status)
    
    # Order by priority and due date
    tasks = tasks.order_by('-priority', 'scheduled_date')
    
    # Statistics
    total_tasks = tasks.count()
    pending_tasks = tasks.filter(status='pending').count()
    in_progress_tasks = tasks.filter(status='in_progress').count()
    completed_tasks = tasks.filter(status='completed').count()
    overdue_tasks = tasks.filter(
        scheduled_date__lt=timezone.now(),
        status__in=['pending', 'in_progress']
    ).count()
    
    context = {
        'tenant': tenant,
        'tasks': tasks,
        'total_tasks': total_tasks,
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_tasks': completed_tasks,
        'overdue_tasks': overdue_tasks,
        'active_tab': 'maintenance',
    }
    return render(request, 'rental_master/maintenance_tasks.html', context)


@login_required
def maintenance_detail(request, request_id):
    """View maintenance request details"""
    tenant = request.user.tenant
    maintenance_request = get_object_or_404(
        MaintenanceRequest, 
        id=request_id, 
        tenant=tenant
    )
    
    context = {
        'tenant': tenant,
        'request': maintenance_request,
        'active_tab': 'maintenance',
    }
    return render(request, 'rental_master/maintenance_detail.html', context)


@login_required
def update_maintenance_status(request, request_id):
    """Update maintenance request status"""
    tenant = request.user.tenant
    maintenance_request = get_object_or_404(
        MaintenanceRequest, 
        id=request_id, 
        tenant=tenant
    )
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        if new_status in ['pending', 'in_progress', 'completed', 'cancelled']:
            maintenance_request.status = new_status
            if notes:
                maintenance_request.notes = notes
            if new_status == 'completed':
                maintenance_request.completed_date = timezone.now()
            maintenance_request.save()
            messages.success(request, f'Request status updated to {new_status.title()}')
        else:
            messages.error(request, 'Invalid status')
    
    return redirect('rental_master:maintenance_detail', request_id=request_id)