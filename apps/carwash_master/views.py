from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from .models import (
    ServiceCategory, Service, Vehicle, Booking,
    BookingService, Employee, Inventory
)


@login_required
def dashboard(request):
    """Carwash Master Dashboard"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get statistics
    total_services = Service.objects.filter(tenant=tenant, is_active=True).count()
    total_vehicles = Vehicle.objects.filter(tenant=tenant, is_active=True).count()
    total_employees = Employee.objects.filter(tenant=tenant, is_active=True).count()
    
    # Today's bookings
    today = timezone.now().date()
    today_bookings = Booking.objects.filter(
        tenant=tenant,
        booking_date__date=today
    ).count()
    
    today_revenue = Booking.objects.filter(
        tenant=tenant,
        booking_date__date=today,
        status='completed'
    ).aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')
    
    # Pending bookings
    pending_bookings = Booking.objects.filter(
        tenant=tenant,
        status='pending'
    ).count()
    
    # Recent bookings
    recent_bookings = Booking.objects.filter(
        tenant=tenant
    ).select_related('vehicle').order_by('-created_at')[:10]
    
    context = {
        'tenant': tenant,
        'total_services': total_services,
        'total_vehicles': total_vehicles,
        'total_employees': total_employees,
        'today_bookings': today_bookings,
        'today_revenue': today_revenue,
        'pending_bookings': pending_bookings,
        'recent_bookings': recent_bookings,
        'active_tab': 'dashboard',
        'project_type': 'CARWASH_MASTER',
    }
    return render(request, 'carwash_master/dashboard.html', context)


@login_required
def service_list(request):
    """List car wash services"""
    tenant = request.user.tenant
    
    services = Service.objects.filter(
        tenant=tenant
    ).select_related('category').order_by('name')
    
    # Filter by category
    category_id = request.GET.get('category')
    if category_id:
        services = services.filter(category_id=category_id)
    
    categories = ServiceCategory.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'services': services,
        'categories': categories,
        'active_tab': 'services',
    }
    return render(request, 'carwash_master/services.html', context)


@login_required
def service_create(request):
    """Create a new service"""
    tenant = request.user.tenant
    categories = ServiceCategory.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        description = request.POST.get('description', '')
        price = request.POST.get('price', 0)
        duration = request.POST.get('duration', 30)
        
        if not all([name, category_id, price]):
            messages.error(request, 'Please fill in all required fields')
            return redirect('carwash_master:service_create')
        
        if Service.objects.filter(tenant=tenant, name=name).exists():
            messages.error(request, f'Service "{name}" already exists')
            return redirect('carwash_master:service_create')
        
        category = get_object_or_404(ServiceCategory, id=category_id, tenant=tenant)
        
        service = Service.objects.create(
            tenant=tenant,
            name=name,
            category=category,
            description=description,
            price=price,
            duration=duration,
            is_active=True
        )
        
        messages.success(request, f'Service "{name}" created successfully!')
        return redirect('carwash_master:services')
    
    context = {
        'tenant': tenant,
        'categories': categories,
        'active_tab': 'services',
    }
    return render(request, 'carwash_master/service_form.html', context)


@login_required
def vehicle_list(request):
    """List customer vehicles"""
    tenant = request.user.tenant
    
    vehicles = Vehicle.objects.filter(tenant=tenant).order_by('-created_at')
    
    search = request.GET.get('search')
    if search:
        vehicles = vehicles.filter(
            Q(license_plate__icontains=search) |
            Q(customer_name__icontains=search) |
            Q(customer_phone__icontains=search)
        )
    
    context = {
        'tenant': tenant,
        'vehicles': vehicles,
        'active_tab': 'vehicles',
    }
    return render(request, 'carwash_master/vehicles.html', context)


@login_required
def vehicle_create(request):
    """Create a new vehicle"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        customer_name = request.POST.get('customer_name')
        customer_phone = request.POST.get('customer_phone')
        customer_email = request.POST.get('customer_email', '')
        vehicle_type = request.POST.get('vehicle_type')
        license_plate = request.POST.get('license_plate').upper()
        color = request.POST.get('color', '')
        make = request.POST.get('make', '')
        model = request.POST.get('model', '')
        
        if not all([customer_name, customer_phone, license_plate]):
            messages.error(request, 'Please fill in all required fields')
            return redirect('carwash_master:vehicle_create')
        
        if Vehicle.objects.filter(tenant=tenant, license_plate=license_plate).exists():
            messages.error(request, f'Vehicle with plate "{license_plate}" already exists')
            return redirect('carwash_master:vehicle_create')
        
        vehicle = Vehicle.objects.create(
            tenant=tenant,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            vehicle_type=vehicle_type,
            license_plate=license_plate,
            color=color,
            make=make,
            model=model,
            is_active=True
        )
        
        messages.success(request, f'Vehicle "{license_plate}" registered successfully!')
        return redirect('carwash_master:vehicles')
    
    context = {
        'tenant': tenant,
        'vehicle_types': Vehicle.VEHICLE_TYPES,
        'active_tab': 'vehicles',
    }
    return render(request, 'carwash_master/vehicle_form.html', context)


@login_required
def booking_list(request):
    """List all bookings"""
    tenant = request.user.tenant
    
    bookings = Booking.objects.filter(
        tenant=tenant
    ).select_related('vehicle', 'created_by').order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    if status:
        bookings = bookings.filter(status=status)
    
    date_from = request.GET.get('date_from')
    if date_from:
        bookings = bookings.filter(booking_date__date__gte=date_from)
    
    date_to = request.GET.get('date_to')
    if date_to:
        bookings = bookings.filter(booking_date__date__lte=date_to)
    
    context = {
        'tenant': tenant,
        'bookings': bookings,
        'status_choices': Booking.STATUS_CHOICES,
        'active_tab': 'bookings',
    }
    return render(request, 'carwash_master/bookings.html', context)


@login_required
def booking_create(request):
    """Create a new booking"""
    tenant = request.user.tenant
    vehicles = Vehicle.objects.filter(tenant=tenant, is_active=True)
    services = Service.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle')
        service_ids = request.POST.getlist('services')
        booking_date = request.POST.get('booking_date')
        notes = request.POST.get('notes', '')
        
        if not all([vehicle_id, service_ids, booking_date]):
            messages.error(request, 'Please fill in all required fields')
            return redirect('carwash_master:booking_create')
        
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, tenant=tenant)
        
        # Calculate total and duration
        total_amount = Decimal('0.00')
        total_duration = 0
        selected_services = []
        
        for service_id in service_ids:
            service = get_object_or_404(Service, id=service_id, tenant=tenant)
            selected_services.append(service)
            total_amount += service.price
            total_duration += service.duration
        
        booking = Booking.objects.create(
            tenant=tenant,
            vehicle=vehicle,
            booking_date=booking_date,
            estimated_duration=total_duration,
            total_amount=total_amount,
            status='pending',
            notes=notes,
            created_by=request.user
        )
        
        # Add services to booking
        for service in selected_services:
            BookingService.objects.create(
                booking=booking,
                service=service,
                quantity=1,
                price=service.price
            )
        
        booking.save()
        
        messages.success(request, f'Booking created successfully for {vehicle.license_plate}!')
        return redirect('carwash_master:booking_detail', booking_id=booking.id)
    
    context = {
        'tenant': tenant,
        'vehicles': vehicles,
        'services': services,
        'active_tab': 'bookings',
    }
    return render(request, 'carwash_master/booking_form.html', context)


@login_required
def booking_detail(request, booking_id):
    """View booking details"""
    tenant = request.user.tenant
    booking = get_object_or_404(Booking, id=booking_id, tenant=tenant)
    booking_services = booking.booking_services.all().select_related('service')
    payments = booking.payments.all()
    
    context = {
        'tenant': tenant,
        'booking': booking,
        'booking_services': booking_services,
        'payments': payments,
        'active_tab': 'bookings',
    }
    return render(request, 'carwash_master/booking_detail.html', context)


@login_required
def booking_update_status(request, booking_id):
    """Update booking status"""
    tenant = request.user.tenant
    booking = get_object_or_404(Booking, id=booking_id, tenant=tenant)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in dict(Booking.STATUS_CHOICES):
            booking.status = status
            booking.save()
            messages.success(request, f'Booking status updated to {status.title()}')
        else:
            messages.error(request, 'Invalid status')
    
    return redirect('carwash_master:booking_detail', booking_id=booking.id)


@login_required
def employee_list(request):
    """List employees"""
    tenant = request.user.tenant
    employees = Employee.objects.filter(tenant=tenant).order_by('name')
    
    context = {
        'tenant': tenant,
        'employees': employees,
        'active_tab': 'employees',
    }
    return render(request, 'carwash_master/employees.html', context)


@login_required
def employee_create(request):
    """Create a new employee"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email', '')
        role = request.POST.get('role')
        hire_date = request.POST.get('hire_date')
        hourly_rate = request.POST.get('hourly_rate', 0)
        
        if not all([name, phone, role, hire_date]):
            messages.error(request, 'Please fill in all required fields')
            return redirect('carwash_master:employee_create')
        
        employee = Employee.objects.create(
            tenant=tenant,
            name=name,
            phone=phone,
            email=email,
            role=role,
            hire_date=hire_date,
            hourly_rate=hourly_rate,
            is_active=True
        )
        
        messages.success(request, f'Employee "{name}" created successfully!')
        return redirect('carwash_master:employees')
    
    context = {
        'tenant': tenant,
        'role_choices': Employee.ROLE_CHOICES,
        'active_tab': 'employees',
    }
    return render(request, 'carwash_master/employee_form.html', context)


@login_required
def inventory_list(request):
    """List inventory items"""
    tenant = request.user.tenant
    inventory = Inventory.objects.filter(tenant=tenant).order_by('name')
    
    # Filter low stock
    low_stock_only = request.GET.get('low_stock')
    if low_stock_only:
        inventory = inventory.filter(quantity__lte=models.F('reorder_level')) # pyright: ignore[reportUndefinedVariable]
    
    context = {
        'tenant': tenant,
        'inventory': inventory,
        'active_tab': 'inventory',
    }
    return render(request, 'carwash_master/inventory.html', context)


@login_required
def inventory_create(request):
    """Create new inventory item"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        name = request.POST.get('name')
        sku = request.POST.get('sku').upper()
        description = request.POST.get('description', '')
        unit = request.POST.get('unit')
        quantity = request.POST.get('quantity', 0)
        reorder_level = request.POST.get('reorder_level', 10)
        unit_price = request.POST.get('unit_price', 0)
        supplier = request.POST.get('supplier', '')
        
        if not all([name, sku, unit, unit_price]):
            messages.error(request, 'Please fill in all required fields')
            return redirect('carwash_master:inventory_create')
        
        if Inventory.objects.filter(tenant=tenant, sku=sku).exists():
            messages.error(request, f'Item with SKU "{sku}" already exists')
            return redirect('carwash_master:inventory_create')
        
        inventory = Inventory.objects.create(
            tenant=tenant,
            name=name,
            sku=sku,
            description=description,
            unit=unit,
            quantity=quantity,
            reorder_level=reorder_level,
            unit_price=unit_price,
            supplier=supplier,
            is_active=True
        )
        
        messages.success(request, f'Inventory item "{name}" created successfully!')
        return redirect('carwash_master:inventory')
    
    context = {
        'tenant': tenant,
        'unit_choices': Inventory.UNIT_CHOICES,
        'active_tab': 'inventory',
    }
    return render(request, 'carwash_master/inventory_form.html', context)