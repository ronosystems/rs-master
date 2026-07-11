# apps/food_master/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from decimal import Decimal
from datetime import datetime, timedelta, date
from django.core.cache import cache
from datetime import datetime  
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import (
    Branch, Category, MenuItem, Table, Customer, 
    Order, OrderItem, Reservation
)
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


# ============================================
# DASHBOARD VIEW
# ============================================
@login_required
def dashboard(request):
    """Food/Restaurant Master Dashboard"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned.')
        return redirect('portal:dashboard')
    
    # Get branches
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    total_branches = branches.count()
    
    # Menu stats - FIXED: removed is_active filter
    total_menu_items = MenuItem.objects.filter(tenant=tenant).count()
    available_items = MenuItem.objects.filter(tenant=tenant, is_available=True).count()
    
    # Table stats
    total_tables = Table.objects.filter(tenant=tenant, is_active=True).count()
    occupied_tables = Table.objects.filter(tenant=tenant, is_active=True, status='occupied').count()
    available_tables = Table.objects.filter(tenant=tenant, is_active=True, status='available').count()
    
    # Today's orders
    today = date.today()
    today_orders = Order.objects.filter(
        tenant=tenant,
        created_at__date=today
    ).count()
    
    # Today's revenue
    today_revenue = Order.objects.filter(
        tenant=tenant,
        created_at__date=today,
        status='completed',
        payment_status='paid'
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Monthly revenue
    current_month = datetime.now().month
    current_year = datetime.now().year
    monthly_revenue = Order.objects.filter(
        tenant=tenant,
        created_at__date__year=current_year,
        created_at__date__month=current_month,
        status='completed',
        payment_status='paid'
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Recent orders
    recent_orders = Order.objects.filter(
        tenant=tenant
    ).select_related('customer', 'table', 'branch').order_by('-created_at')[:5]
    
    # Popular items
    popular_items = OrderItem.objects.filter(
        order__tenant=tenant,
        order__status='completed'
    ).values(
        'menu_item__name'
    ).annotate(
        total_orders=Count('id'),
        total_quantity=Sum('quantity')
    ).order_by('-total_quantity')[:5]
    
    # Today's reservations
    today_reservations = Reservation.objects.filter(
        tenant=tenant,
        reservation_date=today,
        status__in=['pending', 'confirmed']
    ).select_related('customer', 'table', 'branch').order_by('reservation_time')[:5]
    
    context = {
        'tenant': tenant,
        'active_tab': 'dashboard',
        'project_type': 'FOOD_MASTER',
        
        # Stats
        'total_branches': total_branches,
        'total_menu_items': total_menu_items,
        'available_items': available_items,
        'total_tables': total_tables,
        'occupied_tables': occupied_tables,
        'available_tables': available_tables,
        'today_orders': today_orders,
        'today_revenue': today_revenue,
        'monthly_revenue': monthly_revenue,
        
        # Lists
        'recent_orders': recent_orders,
        'popular_items': popular_items,
        'today_reservations': today_reservations,
    }
    return render(request, 'food_master/dashboard.html', context)

@login_required
def edit_branch(request, branch_id):
    """Edit branch details"""
    tenant = request.user.tenant
    branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        city = request.POST.get('city')
        county = request.POST.get('county')
        contact_person = request.POST.get('contact_person')
        contact_phone = request.POST.get('contact_phone')
        email = request.POST.get('email')
        is_active = request.POST.get('is_active') == 'on'
        
        if name and location:
            branch.name = name
            branch.location = location
            branch.city = city
            branch.county = county
            branch.contact_person = contact_person
            branch.contact_phone = contact_phone
            branch.email = email
            branch.is_active = is_active
            branch.save()
            
            messages.success(request, f'Branch "{branch.name}" updated successfully!')
            return redirect('food_master:branch_detail', branch_id=branch.id)
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'branch': branch,
        'active_tab': 'branches',
    }
    return render(request, 'food_master/edit_branch.html', context)

@login_required
def branch_detail(request, branch_id):
    """View branch details"""
    tenant = request.user.tenant
    branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
    
    # Get branch statistics
    tables = Table.objects.filter(branch=branch, is_active=True)
    menu_items = MenuItem.objects.filter(branch=branch)
    orders = Order.objects.filter(branch=branch)
    reservations = Reservation.objects.filter(branch=branch)
    
    # Get today's orders for this branch
    today = date.today()
    today_orders = orders.filter(created_at__date=today)
    
    # Get revenue for this branch
    total_revenue = orders.filter(
        status='completed',
        payment_status='paid'
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    context = {
        'tenant': tenant,
        'branch': branch,
        'tables': tables,
        'menu_items': menu_items,
        'orders': orders[:20],
        'reservations': reservations[:20],
        'today_orders': today_orders.count(),
        'total_revenue': total_revenue,
        'active_tab': 'branches',
    }
    return render(request, 'food_master/branch_detail.html', context)

@login_required
@csrf_exempt
def toggle_branch(request, branch_id):
    """Toggle branch active status"""
    tenant = request.user.tenant
    branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
    
    if request.method == 'POST':
        branch.is_active = not branch.is_active
        branch.save()
        return JsonResponse({
            'success': True,
            'is_active': branch.is_active,
            'message': f'Branch "{branch.name}" { "activated" if branch.is_active else "deactivated" } successfully.'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


# ============================================
# BRANCH VIEWS
# ============================================
@login_required
def branches(request):
    """List restaurant branches"""
    tenant = request.user.tenant
    branches_list = Branch.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'branches': branches_list,
        'active_tab': 'branches',
    }
    return render(request, 'food_master/branches.html', context)

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
        email = request.POST.get('email')
        
        if name and location:
            branch = Branch.objects.create(
                tenant=tenant,
                name=name,
                location=location,
                city=city,
                contact_person=contact_person,
                contact_phone=contact_phone,
                email=email,
                is_active=True
            )
            messages.success(request, f'Branch "{branch.name}" created successfully!')
            return redirect('food_master:branches')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'active_tab': 'branches',
    }
    return render(request, 'food_master/add_branch.html', context)





# ============================================
# CATEGORY VIEWS
# ============================================
@login_required
def categories(request):
    """List categories"""
    tenant = request.user.tenant
    categories_list = Category.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'categories': categories_list,
        'active_tab': 'menu',
    }
    return render(request, 'food_master/categories.html', context)

@login_required
def add_category(request):
    """Add a new category"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        icon = request.POST.get('icon')
        display_order = request.POST.get('display_order', 0)
        
        if name:
            category = Category.objects.create(
                tenant=tenant,
                name=name,
                description=description,
                icon=icon,
                display_order=display_order,
                is_active=True
            )
            messages.success(request, f'Category "{category.name}" created successfully!')
            return redirect('food_master:categories')
        else:
            messages.error(request, 'Please enter a category name.')
    
    context = {
        'tenant': tenant,
        'active_tab': 'menu',
    }
    return render(request, 'food_master/add_category.html', context)

@login_required
def edit_category(request, category_id):
    """Edit a category"""
    tenant = request.user.tenant
    category = get_object_or_404(Category, id=category_id, tenant=tenant)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        icon = request.POST.get('icon')
        display_order = request.POST.get('display_order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if name:
            category.name = name
            category.description = description
            category.icon = icon
            category.display_order = display_order
            category.is_active = is_active
            category.save()
            
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect('food_master:categories')
        else:
            messages.error(request, 'Please enter a category name.')
    
    context = {
        'tenant': tenant,
        'category': category,
        'active_tab': 'menu',
    }
    return render(request, 'food_master/edit_category.html', context)

@login_required
def delete_category(request, category_id):
    """Delete a category"""
    tenant = request.user.tenant
    category = get_object_or_404(Category, id=category_id, tenant=tenant)
    
    if request.method == 'POST':
        category_name = category.name
        category.delete()
        messages.success(request, f'Category "{category_name}" deleted successfully!')
        return JsonResponse({'success': True, 'message': 'Category deleted successfully.'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


@login_required
@csrf_exempt
def toggle_menu_item(request, item_id):
    """Toggle menu item availability"""
    tenant = request.user.tenant
    item = get_object_or_404(MenuItem, id=item_id, tenant=tenant)
    
    if request.method == 'POST':
        item.is_available = not item.is_available
        item.save()
        return JsonResponse({
            'success': True,
            'is_available': item.is_available,
            'message': f'Item "{item.name}" {"available" if item.is_available else "unavailable"} now.'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})






# ============================================
# MENU MANAGEMENT VIEWS
# ============================================
@login_required
def menu_list(request):
    """List menu items"""
    tenant = request.user.tenant
    category_id = request.GET.get('category')
    
    items = MenuItem.objects.filter(tenant=tenant).select_related('category', 'branch')
    if category_id:
        items = items.filter(category_id=category_id)
    
    # Filter by availability
    availability = request.GET.get('availability')
    if availability == 'available':
        items = items.filter(is_available=True)
    elif availability == 'unavailable':
        items = items.filter(is_available=False)
    
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'items': items,
        'categories': categories,
        'branches': branches,
        'active_tab': 'menu',
    }
    return render(request, 'food_master/menu_list.html', context)


@login_required
def menu_order(request):
    """Menu order page with cart - PIN required to access"""
    tenant = request.user.tenant
    user = request.user
    
    # Check if user has PIN set
    if not user.has_pin():
        messages.warning(request, 'Please set your PIN first before accessing POS.')
        return redirect('settings:change_pin')
    
    # Check if user is verified (PIN verified in session)
    if not request.session.get('pin_verified', False):
        # Redirect to PIN verification page
        return redirect('food_master:verify_pin_access')
    
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    menu_items = MenuItem.objects.filter(tenant=tenant, is_available=True).select_related('category')
    
    # Get receipt settings
    receipt_settings = {
        'show_logo_on_receipts': getattr(tenant, 'show_logo_on_receipts', False),
        'logo_url': getattr(tenant, 'logo_url', None),
        'show_business_name': getattr(tenant, 'show_business_name', True),
        'business_name': getattr(tenant, 'company_name', tenant.company_name),
        'show_address': getattr(tenant, 'show_address', True),
        'business_address': getattr(tenant, 'physical_address', ''),
        'show_phone': getattr(tenant, 'show_phone', True),
        'business_phone': getattr(tenant, 'phone', ''),
        'show_email': getattr(tenant, 'show_email', True),
        'business_email': getattr(tenant, 'email', ''),
        'show_tax_pin': getattr(tenant, 'show_tax_pin', True),
        'business_tax_pin': getattr(tenant, 'tax_pin', ''),
        'show_sale_date': getattr(tenant, 'show_sale_date', True),
        'show_sale_time': getattr(tenant, 'show_sale_time', True),
        'show_agent_user': getattr(tenant, 'show_agent_user', True),
        'show_gross_total': getattr(tenant, 'show_gross_total', True),
        'show_vat_on_receipt': getattr(tenant, 'show_vat_on_receipt', True),
        'vat_rate': getattr(tenant, 'vat_rate', 16),
        'vat_label': getattr(tenant, 'vat_label', 'VAT'),
        'show_footer_message': getattr(tenant, 'show_footer_message', True),
        'footer_text': getattr(tenant, 'footer_text', 'Thank you for dining with us!'),
        'show_till_number': getattr(tenant, 'show_till_number', True),
        'till_number': getattr(tenant, 'till_number', 'N/A'),
        'show_paybill': getattr(tenant, 'show_paybill', True),
        'paybill': getattr(tenant, 'paybill', 'N/A'),
        'show_account_number': getattr(tenant, 'show_account_number', True),
        'account_number': getattr(tenant, 'account_number', 'N/A'),
    }
    
    context = {
        'tenant': tenant,
        'categories': categories,
        'menu_items': menu_items,
        'active_tab': 'menu_order',
        'today': datetime.now(),
        'waiter_name': user.full_name or user.username,
        'user_has_pin': user.has_pin(),
        'receipt_settings': receipt_settings,
    }
    return render(request, 'food_master/menu_order.html', context)


@login_required
def verify_pin_access(request):
    """Verify PIN before accessing menu order page"""
    user = request.user
    
    # Check if user has PIN set
    if not user.has_pin():
        messages.warning(request, 'Please set your PIN first before accessing POS.')
        return redirect('settings:change_pin')
    
    if request.method == 'POST':
        pin = request.POST.get('pin', '').strip()
        
        if not pin or len(pin) < 4 or len(pin) > 6 or not pin.isdigit():
            messages.error(request, 'PIN must be 4-6 digits.')
            return render(request, 'food_master/verify_pin.html', {'error': 'Invalid PIN format'})
        
        # Verify PIN
        if user.check_pin(pin):
            # Set session variable to allow access
            request.session['pin_verified'] = True
            request.session['pin_verified_at'] = datetime.now().isoformat()
            request.session['pin_verified_user'] = user.id
            
            # Log successful verification
            from apps.shared.users.models import UserActivityLog
            UserActivityLog.log_activity(
                user=user,
                action='pin_verification',
                details={'success': True, 'ip': request.META.get('REMOTE_ADDR')},
                request=request
            )
            
            messages.success(request, f'Welcome {user.full_name}! PIN verified successfully.')
            return redirect('food_master:menu_order')
        else:
            # Log failed attempt
            from apps.shared.users.models import UserActivityLog
            UserActivityLog.log_activity(
                user=user,
                action='pin_verification',
                details={'success': False, 'ip': request.META.get('REMOTE_ADDR')},
                request=request
            )
            
            messages.error(request, 'Invalid PIN. Please try again.')
            return render(request, 'food_master/verify_pin.html', {'error': 'Invalid PIN'})
    
    context = {
        'user': user,
        'waiter_name': user.full_name or user.username,
    }
    return render(request, 'food_master/verify_pin.html', context)


@login_required
def logout_pin_session(request):
    """Clear PIN verification session"""
    if request.method == 'POST':
        request.session.pop('pin_verified', None)
        request.session.pop('pin_verified_at', None)
        request.session.pop('pin_verified_user', None)
        messages.info(request, 'You have been logged out of POS.')
    return redirect('food_master:dashboard')




@login_required
def add_menu_item(request):
    """Add a new menu item"""
    tenant = request.user.tenant
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        cost = request.POST.get('cost')
        description = request.POST.get('description')
        unit = request.POST.get('unit')
        preparation_time = request.POST.get('preparation_time')
        is_available = request.POST.get('is_available') == 'on'
        is_vegetarian = request.POST.get('is_vegetarian') == 'on'
        is_vegan = request.POST.get('is_vegan') == 'on'
        is_gluten_free = request.POST.get('is_gluten_free') == 'on'
        is_spicy = request.POST.get('is_spicy') == 'on'
        has_allergens = request.POST.get('has_allergens') == 'on'
        branch_id = request.POST.get('branch')
        
        if name and category_id and price:
            category = get_object_or_404(Category, id=category_id, tenant=tenant)
            
            menu_item = MenuItem.objects.create(
                tenant=tenant,
                category=category,
                name=name,
                price=price,
                cost=cost or 0,
                description=description,
                unit=unit or 'serving',
                preparation_time=preparation_time or 0,
                is_available=is_available,
                is_vegetarian=is_vegetarian,
                is_vegan=is_vegan,
                is_gluten_free=is_gluten_free,
                is_spicy=is_spicy,
                has_allergens=has_allergens,
            )
            
            if branch_id:
                menu_item.branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
                menu_item.save()
            
            messages.success(request, f'Menu item "{menu_item.name}" added successfully!')
            return redirect('food_master:menu_list')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'categories': categories,
        'branches': branches,
        'active_tab': 'menu',
    }
    return render(request, 'food_master/add_menu_item.html', context)

@login_required
def edit_menu_item(request, item_id):
    """Edit a menu item"""
    tenant = request.user.tenant
    item = get_object_or_404(MenuItem, id=item_id, tenant=tenant)
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        cost = request.POST.get('cost')
        description = request.POST.get('description')
        unit = request.POST.get('unit')
        preparation_time = request.POST.get('preparation_time')
        is_available = request.POST.get('is_available') == 'on'
        is_vegetarian = request.POST.get('is_vegetarian') == 'on'
        is_vegan = request.POST.get('is_vegan') == 'on'
        is_gluten_free = request.POST.get('is_gluten_free') == 'on'
        is_spicy = request.POST.get('is_spicy') == 'on'
        has_allergens = request.POST.get('has_allergens') == 'on'
        branch_id = request.POST.get('branch')
        
        if name and category_id and price:
            category = get_object_or_404(Category, id=category_id, tenant=tenant)
            
            item.name = name
            item.category = category
            item.price = price
            item.cost = cost or 0
            item.description = description
            item.unit = unit or 'serving'
            item.preparation_time = preparation_time or 0
            item.is_available = is_available
            item.is_vegetarian = is_vegetarian
            item.is_vegan = is_vegan
            item.is_gluten_free = is_gluten_free
            item.is_spicy = is_spicy
            item.has_allergens = has_allergens
            
            if branch_id:
                item.branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
            else:
                item.branch = None
            
            item.save()
            
            messages.success(request, f'Menu item "{item.name}" updated successfully!')
            return redirect('food_master:menu_list')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'item': item,
        'categories': categories,
        'branches': branches,
        'active_tab': 'menu',
    }
    return render(request, 'food_master/edit_menu_item.html', context)

@login_required
def delete_menu_item(request, item_id):
    """Delete a menu item"""
    tenant = request.user.tenant
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        return JsonResponse({'success': False, 'message': 'Permission denied'})
    
    if request.method == 'POST':
        item = get_object_or_404(MenuItem, id=item_id, tenant=tenant)
        item_name = item.name
        item.delete()
        messages.success(request, f'Menu item "{item_name}" deleted successfully!')
        return JsonResponse({'success': True, 'message': 'Item deleted successfully'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


# ============================================
# ORDER MANAGEMENT VIEWS
# ============================================
@login_required
def orders(request):
    """List orders"""
    tenant = request.user.tenant
    status = request.GET.get('status')
    
    orders_list = Order.objects.filter(tenant=tenant).select_related('customer', 'table', 'branch').order_by('-created_at')
    if status:
        orders_list = orders_list.filter(status=status)
    
    context = {
        'tenant': tenant,
        'orders': orders_list,
        'active_tab': 'orders',
    }
    return render(request, 'food_master/orders.html', context)

@login_required
def create_order(request):
    """Create a new order"""
    tenant = request.user.tenant
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    tables = Table.objects.filter(tenant=tenant, is_active=True, status='available')
    customers = Customer.objects.filter(tenant=tenant, is_active=True)
    menu_items = MenuItem.objects.filter(tenant=tenant, is_available=True)
    
    if request.method == 'POST':
        branch_id = request.POST.get('branch')
        table_id = request.POST.get('table')
        customer_id = request.POST.get('customer')
        order_type = request.POST.get('order_type')
        notes = request.POST.get('notes')
        
        if branch_id and order_type:
            branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
            
            # Create order
            order = Order.objects.create(
                tenant=tenant,
                branch=branch,
                order_type=order_type,
                status='pending',
                payment_status='pending',
                notes=notes
            )
            
            if table_id:
                order.table = get_object_or_404(Table, id=table_id, tenant=tenant)
                order.table.status = 'occupied'
                order.table.save()
            
            if customer_id:
                order.customer = get_object_or_404(Customer, id=customer_id, tenant=tenant)
            
            order.save()
            
            messages.success(request, f'Order #{order.order_number} created successfully!')
            return redirect('food_master:order_detail', order_id=order.id)
        else:
            messages.error(request, 'Please select a branch and order type.')
    
    context = {
        'tenant': tenant,
        'branches': branches,
        'tables': tables,
        'customers': customers,
        'menu_items': menu_items,
        'active_tab': 'orders',
    }
    return render(request, 'food_master/create_order.html', context)


@login_required
def order_detail(request, order_id):
    """View order details"""
    tenant = request.user.tenant
    order = get_object_or_404(Order, id=order_id, tenant=tenant)
    menu_items = MenuItem.objects.filter(tenant=tenant, is_available=True)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_item':
            item_id = request.POST.get('item_id')
            quantity = int(request.POST.get('quantity', 1))
            
            if item_id and quantity:
                menu_item = get_object_or_404(MenuItem, id=item_id, tenant=tenant)
                order_item = OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=quantity,
                    unit_price=menu_item.price
                )
                order.subtotal += order_item.subtotal
                order.total_amount = order.subtotal + order.tax - order.discount
                order.save()
                messages.success(request, f'Added {quantity}x {menu_item.name} to order.')
                return redirect('food_master:order_detail', order_id=order.id)
        
        elif action == 'remove_item':
            item_id = request.POST.get('item_id')
            if item_id:
                order_item = get_object_or_404(OrderItem, id=item_id, order=order)
                order.subtotal -= order_item.subtotal
                order.total_amount = order.subtotal + order.tax - order.discount
                order.save()
                order_item.delete()
                messages.success(request, 'Item removed from order.')
                return redirect('food_master:order_detail', order_id=order.id)
        
        elif action == 'update_status':
            new_status = request.POST.get('status')
            if new_status in ['pending', 'confirmed', 'preparing', 'ready', 'served', 'completed', 'cancelled']:
                order.status = new_status
                if new_status == 'completed':
                    if order.table:
                        order.table.status = 'available'
                        order.table.save()
                order.save()
                messages.success(request, f'Order status updated to {new_status.title()}')
                return redirect('food_master:order_detail', order_id=order.id)
        
        elif action == 'mark_paid':
            payment_method = request.POST.get('payment_method')
            amount_paid = Decimal(request.POST.get('amount_paid', 0))
            transaction_ref = request.POST.get('transaction_ref', '')
            payment_notes = request.POST.get('payment_notes', '')
            
            if amount_paid < order.total_amount:
                messages.error(request, f'Amount paid (KES {amount_paid}) is less than total (KES {order.total_amount})')
                return redirect('food_master:order_detail', order_id=order.id)
            
            # Update payment status
            order.payment_status = 'paid'
            order.payment_method = payment_method
            
            # AUTO-COMPLETE THE ORDER
            order.status = 'completed'
            
            # Add notes
            notes_parts = []
            if order.notes:
                notes_parts.append(order.notes)
            if transaction_ref:
                notes_parts.append(f"Transaction: {transaction_ref}")
            if payment_notes:
                notes_parts.append(payment_notes)
            if notes_parts:
                order.notes = " | ".join(notes_parts)
            
            order.save()
            
            # Free up the table if occupied
            if order.table and order.table.status == 'occupied':
                order.table.status = 'available'
                order.table.save()
            
            messages.success(request, f'Order #{order.order_number} marked as paid and completed successfully!')
            return redirect('food_master:order_detail', order_id=order.id)
    
    context = {
        'tenant': tenant,
        'order': order,
        'menu_items': menu_items,
        'active_tab': 'orders',
        'receipt_settings': {
            'business_name': getattr(tenant, 'company_name', tenant.company_name),
            'business_address': getattr(tenant, 'physical_address', ''),
            'business_phone': getattr(tenant, 'phone', ''),
        }
    }
    return render(request, 'food_master/order_detail.html', context)


# apps/food_master/views.py - Update order_receipt with correct VAT calculation

from decimal import Decimal

@login_required
def order_receipt(request, order_id):
    """Display order receipt as a page"""
    tenant = request.user.tenant
    order = get_object_or_404(Order, id=order_id, tenant=tenant)
    
    # Get waiter name
    waiter_session = cache.get(f'waiter_session_{request.user.id}')
    waiter_name = waiter_session.get('name', 'N/A') if waiter_session else (request.user.full_name or request.user.username or 'N/A')
    
    # Get payment settings
    from apps.shared.settings.models import PaymentSetting
    try:
        payment_settings = PaymentSetting.objects.get(tenant=tenant)
        till_number = payment_settings.till_number or 'N/A'
        paybill_number = payment_settings.paybill_number or 'N/A'
        account_number = payment_settings.account_number or 'N/A'
        show_till_number = payment_settings.show_till_number
        show_paybill = payment_settings.show_paybill
        show_account_number = payment_settings.show_account_number
    except PaymentSetting.DoesNotExist:
        payment_settings = PaymentSetting.objects.create(tenant=tenant)
        till_number = 'N/A'
        paybill_number = 'N/A'
        account_number = 'N/A'
        show_till_number = True
        show_paybill = True
        show_account_number = True
    
    # Get receipt settings
    from apps.shared.settings.models import ReceiptSetting
    try:
        receipt_settings_obj = ReceiptSetting.objects.get(tenant=tenant)
    except ReceiptSetting.DoesNotExist:
        receipt_settings_obj = ReceiptSetting.objects.create(tenant=tenant)
    
    # VAT settings
    tax_type = receipt_settings_obj.tax_type if receipt_settings_obj.tax_type else 'exclusive'
    vat_rate = Decimal(str(receipt_settings_obj.vat_rate)) if receipt_settings_obj.vat_rate else Decimal('16.00')
    vat_label = receipt_settings_obj.vat_label if receipt_settings_obj.vat_label else 'VAT'
    show_vat = receipt_settings_obj.show_vat_on_receipt
    
    # Get order amounts
    subtotal = order.subtotal  # This is the total including VAT when items are entered with VAT
    total_amount = order.total_amount
    
    # Calculate VAT correctly
    if tax_type == 'inclusive' and show_vat:
        # Items include VAT, so subtotal is the total including VAT
        # VAT-exclusive amount = Total / (1 + VAT%)
        vat_rate_decimal = vat_rate / Decimal('100.00')
        divisor = Decimal('1.00') + vat_rate_decimal
        
        # VAT-exclusive total
        vat_exclusive = subtotal / divisor
        
        # VAT amount
        vat_amount = subtotal - vat_exclusive
        
        # Round to 2 decimal places
        vat_exclusive = vat_exclusive.quantize(Decimal('0.01'))
        vat_amount = vat_amount.quantize(Decimal('0.01'))
        
        subtotal_display = vat_exclusive      # 155.17 (excluding VAT)
        tax_display = vat_amount               # 24.83 (VAT amount)
        total_display = subtotal               # 180.00 (including VAT)
    else:
        # Exclusive tax: VAT is added to subtotal
        subtotal_display = subtotal
        tax_display = order.tax or Decimal('0.00')
        total_display = total_amount
    
    # Build receipt settings
    receipt_settings = {
        # Logo
        'show_logo_on_receipts': getattr(tenant, 'show_logo_on_receipts', False),
        'logo_url': getattr(tenant, 'logo_url', None),
        
        # Business Details
        'show_business_name': True,
        'business_name': getattr(tenant, 'company_name', 'Restaurant'),
        'show_address': True,
        'business_address': getattr(tenant, 'company_address', ''),
        'show_phone': True,
        'business_phone': getattr(tenant, 'company_phone', ''),
        'show_email': True,
        'business_email': getattr(tenant, 'company_email', ''),
        'show_tax_pin': True,
        'business_tax_pin': getattr(tenant, 'company_pin', ''),
        
        # Payment Details
        'show_till_number': show_till_number,
        'till_number': till_number,
        'show_paybill': show_paybill,
        'paybill': paybill_number,
        'show_account_number': show_account_number,
        'account_number': account_number,
        
        # VAT Settings
        'show_vat_on_receipt': show_vat,
        'vat_rate': float(vat_rate),
        'vat_label': vat_label,
        'tax_type': tax_type,
        
        # Calculated values
        'subtotal_display': float(subtotal_display),
        'tax_display': float(tax_display),
        'total_display': float(total_display),
        
        # Footer
        'show_footer_message': getattr(tenant, 'show_footer_message', True),
        'footer_text': getattr(tenant, 'footer_text', 'Thank you for dining with us!'),
    }
    
    context = {
        'tenant': tenant,
        'order': order,
        'receipt_settings': receipt_settings,
        'waiter_name': waiter_name,
        'active_tab': 'orders',
    }
    return render(request, 'food_master/order_receipt.html', context)

# ============================================
# TABLE MANAGEMENT VIEWS
# ============================================
@login_required
def tables(request):
    """List tables"""
    tenant = request.user.tenant
    tables_list = Table.objects.filter(tenant=tenant, is_active=True).select_related('branch')
    status = request.GET.get('status')
    if status:
        tables_list = tables_list.filter(status=status)
    
    context = {
        'tenant': tenant,
        'tables': tables_list,
        'active_tab': 'tables',
    }
    return render(request, 'food_master/tables.html', context)

@login_required
def add_table(request):
    """Add a new table"""
    tenant = request.user.tenant
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        branch_id = request.POST.get('branch')
        table_number = request.POST.get('table_number')
        capacity = request.POST.get('capacity')
        location = request.POST.get('location')
        
        if branch_id and table_number and capacity:
            branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
            table = Table.objects.create(
                tenant=tenant,
                branch=branch,
                table_number=table_number,
                capacity=capacity,
                location=location,
                status='available',
                is_active=True
            )
            messages.success(request, f'Table {table.table_number} added successfully!')
            return redirect('food_master:tables')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'branches': branches,
        'active_tab': 'tables',
    }
    return render(request, 'food_master/add_table.html', context)







# ============================================
# RESERVATION VIEWS
# ============================================
@login_required
def reservations(request):
    """List reservations"""
    tenant = request.user.tenant
    date_filter = request.GET.get('date')
    
    reservations_list = Reservation.objects.filter(tenant=tenant).select_related('customer', 'table', 'branch')
    if date_filter:
        reservations_list = reservations_list.filter(reservation_date=date_filter)
    
    status = request.GET.get('status')
    if status:
        reservations_list = reservations_list.filter(status=status)
    
    context = {
        'tenant': tenant,
        'reservations': reservations_list,
        'active_tab': 'reservations',
    }
    return render(request, 'food_master/reservations.html', context)

@login_required
def create_reservation(request):
    """Create a new reservation"""
    tenant = request.user.tenant
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    tables = Table.objects.filter(tenant=tenant, is_active=True, status__in=['available', 'reserved'])
    customers = Customer.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        branch_id = request.POST.get('branch')
        customer_id = request.POST.get('customer')
        reservation_date = request.POST.get('reservation_date')
        reservation_time = request.POST.get('reservation_time')
        number_of_guests = request.POST.get('number_of_guests')
        table_id = request.POST.get('table')
        special_requests = request.POST.get('special_requests')
        
        if branch_id and customer_id and reservation_date and reservation_time and number_of_guests:
            branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
            customer = get_object_or_404(Customer, id=customer_id, tenant=tenant)
            
            reservation = Reservation.objects.create(
                tenant=tenant,
                branch=branch,
                customer=customer,
                reservation_date=reservation_date,
                reservation_time=reservation_time,
                number_of_guests=number_of_guests,
                special_requests=special_requests,
                status='pending'
            )
            
            if table_id:
                reservation.table = get_object_or_404(Table, id=table_id, tenant=tenant)
                reservation.table.status = 'reserved'
                reservation.table.save()
                reservation.save()
            
            messages.success(request, f'Reservation for {customer.name} created successfully!')
            return redirect('food_master:reservations')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'branches': branches,
        'tables': tables,
        'customers': customers,
        'active_tab': 'reservations',
    }
    return render(request, 'food_master/create_reservation.html', context)






# ============================================
# CUSTOMER MANAGEMENT VIEWS
# ============================================
@login_required
def customers(request):
    """List customers"""
    tenant = request.user.tenant
    customers_list = Customer.objects.filter(tenant=tenant, is_active=True).order_by('-created_at')
    
    context = {
        'tenant': tenant,
        'customers': customers_list,
        'active_tab': 'customers',
    }
    return render(request, 'food_master/customers.html', context)

@login_required
def add_customer(request):
    """Add a new customer"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        name = request.POST.get('name')
        phone_number = request.POST.get('phone_number')
        email = request.POST.get('email')
        address = request.POST.get('address')
        
        if name and phone_number:
            customer = Customer.objects.create(
                tenant=tenant,
                name=name,
                phone_number=phone_number,
                email=email,
                address=address,
                is_active=True
            )
            messages.success(request, f'Customer "{customer.name}" added successfully!')
            return redirect('food_master:customers')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'tenant': tenant,
        'active_tab': 'customers',
    }
    return render(request, 'food_master/add_customer.html', context)




# ============================================
# POS VIEWS (Point of Sale)
# ============================================

@login_required
def pos_dashboard(request):
    """POS Dashboard with waiter login"""
    tenant = request.user.tenant
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    tables = Table.objects.filter(tenant=tenant, is_active=True, status='available')
    customers = Customer.objects.filter(tenant=tenant, is_active=True)
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    menu_items = MenuItem.objects.filter(tenant=tenant, is_available=True).select_related('category')
    
    # Get waiter session from cache
    waiter_session = cache.get(f'waiter_session_{request.user.id}')
    is_waiter_logged_in = waiter_session is not None
    
    context = {
        'tenant': tenant,
        'branches': branches,
        'tables': tables,
        'customers': customers,
        'categories': categories,
        'menu_items': menu_items,
        'is_waiter_logged_in': is_waiter_logged_in,
        'waiter_name': waiter_session.get('name') if waiter_session else None,
        'active_tab': 'pos',
    }
    return render(request, 'food_master/pos_dashboard.html', context)


@csrf_exempt
def waiter_login(request):
    """Waiter login with name and PIN"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Invalid request method.'
        })
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        pin = data.get('pin', '').strip()
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'message': 'Please login first.'
            })
        
        tenant = request.user.tenant
        if not tenant:
            return JsonResponse({
                'success': False,
                'message': 'No tenant found.'
            })
        
        if not name or not pin:
            return JsonResponse({
                'success': False,
                'message': 'Please enter both name and PIN.'
            })
        
        if len(pin) != 4 or not pin.isdigit():
            return JsonResponse({
                'success': False,
                'message': 'PIN must be 4 digits.'
            })
        
        # Check if waiter exists with this name
        from .models import Staff
        try:
            waiter = Staff.objects.get(
                tenant=tenant,
                name__iexact=name,
                is_active=True
            )
            
            # Check if role is waiter or cashier or manager
            if waiter.role not in ['waiter', 'cashier', 'manager']:
                return JsonResponse({
                    'success': False,
                    'message': f'User role "{waiter.get_role_display()}" not authorized for POS.'
                })
            
            # Verify PIN using the check_pin method
            if waiter.check_pin(pin):
                # Store waiter session in cache
                session_data = {
                    'id': waiter.id,
                    'name': waiter.name,
                    'role': waiter.role,
                    'branch_id': waiter.branch_id if waiter.branch_id else None
                }
                cache_key = f'waiter_session_{request.user.id}'
                cache.set(cache_key, session_data, 3600)  # 1 hour expiry
                
                return JsonResponse({
                    'success': True,
                    'message': f'Welcome {waiter.name}!',
                    'waiter': session_data
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid PIN. Please try again.'
                })
                
        except Staff.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Waiter not found. Please check your name.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request format.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@login_required
def waiter_logout(request):
    """Logout waiter"""
    if request.method == 'POST':
        cache.delete(f'waiter_session_{request.user.id}')
        return JsonResponse({
            'success': True,
            'message': 'Logged out successfully.'
        })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method.'
    })


@csrf_exempt
@login_required
def verify_waiter_pin(request):
    """Verify user PIN and set session"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        data = json.loads(request.body)
        pin = data.get('pin', '').strip()
        
        if not pin or len(pin) < 4 or len(pin) > 6 or not pin.isdigit():
            return JsonResponse({'success': False, 'message': 'PIN must be 4-6 digits'})
        
        user = request.user
        
        if not user:
            return JsonResponse({'success': False, 'message': 'User not found'})
        
        if not user.has_pin():
            return JsonResponse({
                'success': False, 
                'message': 'No PIN set for this user. Please contact admin.'
            })
        
        if user.check_pin(pin):
            # Set session variable for PIN verification
            request.session['pin_verified'] = True
            request.session['pin_verified_at'] = datetime.now().isoformat()
            request.session['pin_verified_user'] = user.id
            
            # Log successful verification
            from apps.shared.users.models import UserActivityLog
            UserActivityLog.log_activity(
                user=user,
                action='pin_verification',
                details={'success': True, 'ip': request.META.get('REMOTE_ADDR')},
                request=request
            )
            
            return JsonResponse({
                'success': True, 
                'message': 'PIN verified',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'full_name': user.full_name,
                }
            })
        else:
            # Log failed attempt
            from apps.shared.users.models import UserActivityLog
            UserActivityLog.log_activity(
                user=user,
                action='pin_verification',
                details={'success': False, 'ip': request.META.get('REMOTE_ADDR')},
                request=request
            )
            
            return JsonResponse({'success': False, 'message': 'Invalid PIN'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})




# ============================================
# POS API ENDPOINTS
# ============================================

@csrf_exempt
@login_required
def pos_place_order(request):
    """Place order from menu"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        table_number = data.get('table_number', 'N/A')
        guest_count = data.get('guest_count', 1)
        
        tenant = request.user.tenant
        user = request.user  # Get the logged-in user
        
        if not items:
            return JsonResponse({'success': False, 'message': 'Cart is empty'})
        
        # Get branch
        branch = Branch.objects.filter(tenant=tenant, is_active=True).first()
        if not branch:
            return JsonResponse({'success': False, 'message': 'No branch found'})
        
        # Get or create table
        table = None
        if table_number and table_number != 'N/A':
            table, _ = Table.objects.get_or_create(
                tenant=tenant,
                branch=branch,
                table_number=table_number,
                defaults={'capacity': guest_count, 'is_active': True}
            )
        
        # Calculate subtotal
        subtotal = Decimal('0.00')
        order_items = []
        for item in items:
            menu_item = get_object_or_404(MenuItem, id=item['id'], tenant=tenant)
            quantity = item['quantity']
            price = Decimal(str(item['price']))
            subtotal += price * quantity
            order_items.append({
                'menu_item': menu_item,
                'quantity': quantity,
                'price': price
            })
        
        # Calculate tax (16%)
        tax = subtotal * Decimal('0.16')
        total = subtotal + tax
        
        # Create order with created_by information
        order = Order.objects.create(
            tenant=tenant,
            branch=branch,
            table=table,
            order_type='dine_in',
            status='pending',
            payment_status='pending',
            subtotal=subtotal,
            tax=tax,
            total_amount=total,
            notes=f"Table: {table_number} | Guests: {guest_count}",
            created_by_id=user.id,  # Store user ID
            created_by_username=user.username,  # Store username
            created_by_full_name=user.full_name or user.username  # Store full name
        )
        
        # Create order items
        for item in order_items:
            OrderItem.objects.create(
                order=order,
                menu_item=item['menu_item'],
                quantity=item['quantity'],
                unit_price=item['price']
            )
        
        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'order_number': order.order_number,
            'items': [{'name': i['menu_item'].name, 'quantity': i['quantity'], 'price': float(i['price'])} for i in order_items],
            'subtotal': float(subtotal),
            'tax': float(tax),
            'total': float(total),
            'table_number': table_number,
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
    


@login_required
def pos_get_products(request):
    """Get products for POS"""
    tenant = request.user.tenant
    
    # Check waiter session
    waiter_session = cache.get(f'waiter_session_{request.user.id}')
    if not waiter_session:
        return JsonResponse({
            'success': False,
            'message': 'Please login as waiter first.'
        })
    
    category = request.GET.get('category')
    search = request.GET.get('search', '')
    
    products = MenuItem.objects.filter(
        tenant=tenant,
        is_available=True
    ).select_related('category')
    
    if category and category != 'all':
        products = products.filter(category_id=category)
    
    if search:
        products = products.filter(name__icontains=search)
    
    product_list = []
    for p in products:
        product_list.append({
            'id': p.id,
            'name': p.name,
            'price': float(p.price),
            'category': p.category.name,
            'category_id': p.category_id,
            'is_vegetarian': p.is_vegetarian,
            'is_spicy': p.is_spicy,
            'is_vegan': p.is_vegan,
            'is_gluten_free': p.is_gluten_free,
        })
    
    return JsonResponse({
        'success': True,
        'products': product_list
    })


@login_required
def pos_get_cart(request):
    """Get current cart from session"""
    cart = cache.get(f'pos_cart_{request.user.id}', [])
    
    subtotal = 0
    for item in cart:
        subtotal += item['price'] * item['quantity']
    
    return JsonResponse({
        'success': True,
        'cart': cart,
        'subtotal': subtotal,
        'total': subtotal
    })


@csrf_exempt
@login_required
def pos_add_to_cart(request):
    """Add item to cart"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantity = int(data.get('quantity', 1))
        
        tenant = request.user.tenant
        menu_item = get_object_or_404(MenuItem, id=item_id, tenant=tenant)
        
        cart_key = f'pos_cart_{request.user.id}'
        cart = cache.get(cart_key, [])
        
        # Check if item already in cart
        found = False
        for item in cart:
            if item['id'] == item_id:
                item['quantity'] += quantity
                found = True
                break
        
        if not found:
            cart.append({
                'id': item_id,
                'name': menu_item.name,
                'price': float(menu_item.price),
                'quantity': quantity,
                'unit': menu_item.unit,
            })
        
        cache.set(cart_key, cart, 3600)  # 1 hour expiry
        
        # Calculate subtotal
        subtotal = sum(item['price'] * item['quantity'] for item in cart)
        
        return JsonResponse({
            'success': True,
            'cart': cart,
            'subtotal': subtotal,
            'total': subtotal
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@csrf_exempt
@login_required
def pos_update_cart(request):
    """Update item quantity in cart"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantity = int(data.get('quantity', 1))
        
        if quantity < 1:
            return pos_remove_from_cart(request)
        
        cart_key = f'pos_cart_{request.user.id}'
        cart = cache.get(cart_key, [])
        
        for item in cart:
            if item['id'] == item_id:
                item['quantity'] = quantity
                break
        
        cache.set(cart_key, cart, 3600)
        
        subtotal = sum(item['price'] * item['quantity'] for item in cart)
        
        return JsonResponse({
            'success': True,
            'cart': cart,
            'subtotal': subtotal,
            'total': subtotal
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@csrf_exempt
@login_required
def pos_remove_from_cart(request):
    """Remove item from cart"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        
        cart_key = f'pos_cart_{request.user.id}'
        cart = cache.get(cart_key, [])
        
        cart = [item for item in cart if item['id'] != item_id]
        
        cache.set(cart_key, cart, 3600)
        
        subtotal = sum(item['price'] * item['quantity'] for item in cart)
        
        return JsonResponse({
            'success': True,
            'cart': cart,
            'subtotal': subtotal,
            'total': subtotal
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@csrf_exempt
@login_required
def pos_clear_cart(request):
    """Clear cart"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    cache.delete(f'pos_cart_{request.user.id}')
    
    return JsonResponse({
        'success': True,
        'cart': [],
        'subtotal': 0,
        'total': 0
    })


@csrf_exempt
@login_required
def pos_process_order(request):
    """Process order from POS"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        data = json.loads(request.body)
        customer_id = data.get('customer_id')
        payment_method = data.get('payment_method', 'cash')
        amount_paid = Decimal(str(data.get('amount_paid', 0)))
        table_id = data.get('table_id')
        order_type = data.get('order_type', 'dine_in')
        
        tenant = request.user.tenant
        
        # Check waiter session
        waiter_session = cache.get(f'waiter_session_{request.user.id}')
        if not waiter_session:
            return JsonResponse({
                'success': False,
                'message': 'Please login as waiter first.'
            })
        
        # Get cart
        cart_key = f'pos_cart_{request.user.id}'
        cart = cache.get(cart_key, [])
        
        if not cart:
            return JsonResponse({
                'success': False,
                'message': 'Cart is empty.'
            })
        
        # Get branch from waiter session
        branch_id = waiter_session.get('branch_id')
        if not branch_id:
            return JsonResponse({
                'success': False,
                'message': 'Waiter has no branch assigned.'
            })
        
        branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
        
        # Calculate subtotal
        subtotal = sum(Decimal(str(item['price'])) * item['quantity'] for item in cart)
        
        # Create order
        order = Order.objects.create(
            tenant=tenant,
            branch=branch,
            order_type=order_type,
            status='pending',
            payment_status='pending',
            subtotal=subtotal,
            total_amount=subtotal
        )
        
        # Assign table if dine-in
        if table_id and order_type == 'dine_in':
            table = get_object_or_404(Table, id=table_id, tenant=tenant)
            order.table = table
            table.status = 'occupied'
            table.save()
        
        # Assign customer
        if customer_id:
            customer = get_object_or_404(Customer, id=customer_id, tenant=tenant)
            order.customer = customer
        
        order.save()
        
        # Create order items
        for item in cart:
            menu_item = get_object_or_404(MenuItem, id=item['id'], tenant=tenant)
            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                quantity=item['quantity'],
                unit_price=item['price']
            )
        
        # Update payment status if paid
        change = Decimal('0.00')
        if amount_paid >= subtotal:
            order.payment_status = 'paid'
            order.payment_method = payment_method
            change = amount_paid - subtotal
            order.save()
        
        # Clear cart
        cache.delete(cart_key)
        
        return JsonResponse({
            'success': True,
            'message': f'Order #{order.order_number} created successfully!',
            'order_id': order.id,
            'order_number': order.order_number,
            'total': float(subtotal),
            'change': float(change) if change >= 0 else 0
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
def pos_search_customer(request):
    """Search customer by phone"""
    tenant = request.user.tenant
    phone = request.GET.get('phone', '').strip()
    
    if not phone:
        return JsonResponse({
            'success': False,
            'message': 'Phone number required'
        })
    
    try:
        customer = Customer.objects.get(
            tenant=tenant,
            phone_number__iexact=phone,
            is_active=True
        )
        
        return JsonResponse({
            'success': True,
            'found': True,
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone_number,
                'email': customer.email,
                'address': customer.address
            }
        })
        
    except Customer.DoesNotExist:
        return JsonResponse({
            'success': True,
            'found': False,
            'message': 'Customer not found'
        })
    except Customer.MultipleObjectsReturned:
        customers = Customer.objects.filter(
            tenant=tenant,
            phone_number__icontains=phone,
            is_active=True
        )[:5]
        
        return JsonResponse({
            'success': True,
            'found': True,
            'multiple': True,
            'customers': [
                {
                    'id': c.id,
                    'name': c.name,
                    'phone': c.phone_number,
                    'email': c.email
                } for c in customers
            ]
        })


@csrf_exempt
@login_required
def pos_add_customer(request):
    """Add customer from POS"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        email = data.get('email', '').strip()
        
        if not name or not phone:
            return JsonResponse({
                'success': False,
                'message': 'Name and phone are required'
            })
        
        tenant = request.user.tenant
        
        customer = Customer.objects.create(
            tenant=tenant,
            name=name,
            phone_number=phone,
            email=email or '',
            is_active=True
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Customer added successfully!',
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone_number,
                'email': customer.email
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })



# ===========================================
# PAYMENTS WITHIN POS
# ===========================================

@login_required
def payment_dashboard(request):
    """Payment confirmation dashboard for cashiers"""
    tenant = request.user.tenant
    
    # Get company settings
    company_settings = {
        'company_name': tenant.company_name,
        'address': getattr(tenant, 'physical_address', 'Restaurant'),
        'phone': getattr(tenant, 'phone', 'N/A'),
        'till_number': getattr(tenant, 'till_number', 'N/A'),
        'paybill': getattr(tenant, 'paybill', 'N/A'),
        'account_number': getattr(tenant, 'account_number', 'N/A'),
    }
    
    context = {
        'tenant': tenant,
        'active_tab': 'payment',
        'today': datetime.now(),
        'company_settings': company_settings,
    }
    return render(request, 'food_master/payment_confirmation.html', context)


@login_required
def payment_search_order(request):
    """Search order for payment"""
    tenant = request.user.tenant
    order_number = request.GET.get('order_number')
    phone = request.GET.get('phone')
    
    if order_number:
        try:
            order = Order.objects.get(tenant=tenant, order_number=order_number)
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Order not found'})
    elif phone:
        orders = Order.objects.filter(
            tenant=tenant,
            customer__phone_number__icontains=phone,
            payment_status='pending'
        ).order_by('-created_at')
        if orders.exists():
            order = orders.first()
        else:
            return JsonResponse({'success': False, 'message': 'No pending orders found for this phone'})
    else:
        return JsonResponse({'success': False, 'message': 'Please provide order number or phone'})
    
    # Check if order is already paid
    if order.payment_status == 'paid':
        return JsonResponse({
            'success': False, 
            'message': 'This order is already paid!',
            'order': {
                'id': order.id,
                'order_number': order.order_number,
                'payment_status': order.payment_status,
            }
        })
    
    # Get order items
    items = []
    for item in order.items.all():
        items.append({
            'id': item.id,
            'name': item.menu_item.name,
            'quantity': item.quantity,
            'price': float(item.unit_price)
        })
    
    status_colors = {
        'pending': 'warning',
        'paid': 'success',
        'partial': 'info',
        'refunded': 'danger',
    }
    
    return JsonResponse({
        'success': True,
        'order': {
            'id': order.id,
            'order_number': order.order_number,
            'status': order.status,
            'status_display': order.get_status_display(),
            'status_color': status_colors.get(order.status, 'secondary'),
            'payment_status': order.payment_status,
            'table_number': order.table.table_number if order.table else 'N/A',
            'guest_count': 1,
            'subtotal': float(order.subtotal),
            'tax': float(order.tax),
            'total': float(order.total_amount),
            'items': items,
            'created_at': order.created_at.isoformat(),
        }
    })


@login_required
def payment_search_suggestions(request):
    """Get search suggestions for orders"""
    tenant = request.user.tenant
    query = request.GET.get('q', '').strip()
    search_type = request.GET.get('type', 'order')
    
    if len(query) < 2:
        return JsonResponse({'success': True, 'suggestions': []})
    
    if search_type == 'order':
        # Search by order number
        orders = Order.objects.filter(
            tenant=tenant,
            order_number__icontains=query,
            payment_status__in=['pending', 'partial']
        ).order_by('-created_at')[:10]
    else:
        # Search by phone
        orders = Order.objects.filter(
            tenant=tenant,
            customer__phone_number__icontains=query,
            payment_status__in=['pending', 'partial']
        ).select_related('customer').order_by('-created_at')[:10]
    
    suggestions = []
    for order in orders:
        suggestions.append({
            'order_number': order.order_number,
            'total_amount': float(order.total_amount),
            'payment_status': order.payment_status,
            'customer_name': order.customer.name if order.customer else 'Walk-in',
        })
    
    return JsonResponse({
        'success': True,
        'suggestions': suggestions
    })


@csrf_exempt
@login_required
def payment_confirm(request):
    """Confirm payment for order"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        payment_method = data.get('payment_method', 'cash')
        amount_paid = Decimal(str(data.get('amount_paid', 0)))
        transaction_ref = data.get('transaction_reference', '')
        
        if not order_id:
            return JsonResponse({'success': False, 'message': 'Order ID required'})
        
        tenant = request.user.tenant
        order = get_object_or_404(Order, id=order_id, tenant=tenant)
        
        if order.payment_status == 'paid':
            return JsonResponse({'success': False, 'message': 'Order already paid'})
        
        if amount_paid < order.total_amount:
            return JsonResponse({
                'success': False, 
                'message': f'Insufficient payment amount. Total: KES {order.total_amount}'
            })
        
        # Update order
        order.payment_status = 'paid'
        order.payment_method = payment_method
        
        # Auto-complete order
        order.status = 'completed'
        
        if transaction_ref:
            notes = order.notes or ''
            order.notes = f"{notes} | Transaction: {transaction_ref}".strip()
        
        order.save()
        
        # Free up the table if occupied
        if order.table and order.table.status == 'occupied':
            order.table.status = 'available'
            order.table.save()
        
        # Generate receipt number
        receipt_number = f"RCP-{datetime.now().strftime('%Y%m%d')}-{order.id:04d}"
        
        return JsonResponse({
            'success': True,
            'message': 'Payment confirmed successfully!',
            'receipt_number': receipt_number,
            'amount_paid': float(amount_paid),
            'change': float(amount_paid - order.total_amount),
            'transaction_ref': transaction_ref
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})






from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

# Import from shared permissions with correct model names
from apps.shared.permissions.models import Role, UserRoleAssignment

User = get_user_model()


def generate_unique_codename(base_name, exclude_id=None):
    """Generate a unique codename based on the role name"""
    base_codename = base_name.lower().replace(' ', '_')
    codename = base_codename
    counter = 1
    
    # Check if codename exists (excluding the current role if editing)
    while Role.objects.filter(codename=codename).exclude(id=exclude_id).exists():
        codename = f"{base_codename}_{counter}"
        counter += 1
    
    return codename

# ============================================
# ROLE & PERMISSION MANAGEMENT VIEWS
# ============================================

@login_required
def role_list(request):
    """List all roles"""
    tenant = request.user.tenant
    
    if request.user.is_super_admin:
        roles = Role.objects.all()
    else:
        roles = Role.objects.filter(project_types=tenant.project_type)
    
    context = {
        'tenant': tenant,
        'roles': roles,
        'active_tab': 'roles',
    }
    return render(request, 'food_master/role_list.html', context)


@login_required
def create_role(request):
    """Create a new role with permissions"""
    tenant = request.user.tenant
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'You do not have permission to create roles.')
        return redirect('food_master:role_list')
    
    # Get all food permissions
    content_type = ContentType.objects.get_for_model(Order)
    all_permissions = Permission.objects.filter(content_type=content_type)
    
    if request.method == 'POST':
        role_name = request.POST.get('role_name')
        permission_ids = request.POST.getlist('permissions')
        description = request.POST.get('description', '')
        codename = request.POST.get('codename', '')
        
        if not role_name:
            messages.error(request, 'Please enter a role name.')
        else:
            # Generate codename if not provided
            if not codename:
                codename = role_name.lower().replace(' ', '_')
            
            # Check if codename already exists
            if Role.objects.filter(codename=codename).exists():
                messages.error(request, f'A role with the codename "{codename}" already exists. Please use a different name.')
                return render(request, 'food_master/roles/create_role.html', {
                    'tenant': tenant,
                    'permissions': all_permissions,
                    'active_tab': 'roles',
                })
            
            # Create role
            role = Role.objects.create(
                name=role_name,
                codename=codename,
                role_type='custom',
                description=description,
                is_active=True,
                is_system_role=False
            )
            
            # Add project type if tenant has one
            if tenant and tenant.project_type:
                role.project_types.add(tenant.project_type)
            
            # Assign permissions
            for perm_id in permission_ids:
                try:
                    perm = Permission.objects.get(id=int(perm_id))
                    role.permissions.add(perm)
                except (Permission.DoesNotExist, ValueError):
                    pass
            
            messages.success(request, f'Role "{role_name}" created successfully!')
            return redirect('food_master:role_list')
    
    context = {
        'tenant': tenant,
        'permissions': all_permissions,
        'active_tab': 'roles',
    }
    return render(request, 'food_master/create_role.html', context)


@login_required
def edit_role(request, role_id):
    """Edit a role and its permissions"""
    tenant = request.user.tenant
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'You do not have permission to edit roles.')
        return redirect('food_master:role_list')
    
    role = get_object_or_404(Role, id=role_id)
    
    # Get all food permissions
    content_type = ContentType.objects.get_for_model(Order)
    all_permissions = Permission.objects.filter(content_type=content_type)
    
    # Get current role permissions (as list of IDs)
    role_permissions = list(role.permissions.all().values_list('id', flat=True))
    
    if request.method == 'POST':
        role_name = request.POST.get('role_name')
        permission_ids = request.POST.getlist('permissions')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        codename = request.POST.get('codename', '')
        
        if not role_name:
            messages.error(request, 'Please enter a role name.')
        else:
            # Generate codename if not provided or keep the existing one
            if not codename:
                codename = role_name.lower().replace(' ', '_')
            
            # Check if the codename already exists for another role
            if Role.objects.filter(codename=codename).exclude(id=role.id).exists():
                messages.error(request, f'A role with the codename "{codename}" already exists. Please use a different name.')
                return render(request, 'food_master/edit_role.html', {
                    'tenant': tenant,
                    'role': role,
                    'permissions': all_permissions,
                    'role_permissions': role_permissions,
                    'active_tab': 'roles',
                })
            
            # Update role fields
            role.name = role_name
            role.codename = codename
            role.description = description
            role.is_active = is_active
            role.save()
            
            # Clear existing permissions
            role.permissions.clear()
            
            # Assign new permissions
            for perm_id in permission_ids:
                try:
                    perm = Permission.objects.get(id=int(perm_id))
                    role.permissions.add(perm)
                except (Permission.DoesNotExist, ValueError):
                    pass
            
            messages.success(request, f'Role "{role_name}" updated successfully!')
            return redirect('food_master:role_list')
    
    context = {
        'tenant': tenant,
        'role': role,
        'permissions': all_permissions,
        'role_permissions': role_permissions,
        'active_tab': 'roles',
    }
    return render(request, 'food_master/edit_role.html', context)


@login_required
def delete_role(request, role_id):
    """Delete a role"""
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        return JsonResponse({'success': False, 'message': 'Permission denied'})
    
    if request.method == 'POST':
        role = get_object_or_404(Role, id=role_id)
        
        # Check if it's a system role
        if role.is_system_role:
            return JsonResponse({'success': False, 'message': 'Cannot delete system roles.'})
        
        role_name = role.name
        role.delete()
        messages.success(request, f'Role "{role_name}" deleted successfully!')
        return JsonResponse({'success': True, 'message': 'Role deleted successfully'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def assign_role_to_user(request):
    """Assign a role to a user"""
    tenant = request.user.tenant
    
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'You do not have permission to assign roles.')
        return redirect('food_master:role_list')
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role_id = request.POST.get('role_id')
        
        if not user_id or not role_id:
            messages.error(request, 'Please select both user and role.')
            return redirect('food_master:role_list')
        
        try:
            user = User.objects.get(id=user_id)
            role = Role.objects.get(id=role_id)
            
            # Check if assignment already exists
            assignment, created = UserRoleAssignment.objects.get_or_create(
                user=user,
                role=role,
                defaults={
                    'assigned_by': request.user,
                    'is_active': True,
                    'notes': f'Assigned via Food Master admin by {request.user.username}'
                }
            )
            
            if not created:
                assignment.is_active = True
                assignment.assigned_by = request.user
                assignment.save()
                messages.info(request, f'Role "{role.name}" already assigned to {user.username}. Activated it.')
            else:
                messages.success(request, f'Role "{role.name}" assigned to {user.username} successfully!')
                
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
        except Role.DoesNotExist:
            messages.error(request, 'Role not found.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        
        return redirect('food_master:role_list')
    
    # Get users and roles for the form
    users = User.objects.filter(tenant=tenant, is_active=True)
    
    # Get roles for this project type
    if tenant and tenant.project_type:
        roles = Role.objects.filter(project_types=tenant.project_type, is_active=True)
    else:
        roles = Role.objects.filter(is_active=True)
    
    context = {
        'tenant': tenant,
        'users': users,
        'roles': roles,
        'active_tab': 'roles',
    }
    return render(request, 'food_master/assign_role.html', context)


@login_required
def remove_user_role(request, assignment_id):
    """Remove a role assignment from a user"""
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        return JsonResponse({'success': False, 'message': 'Permission denied'})
    
    if request.method == 'POST':
        try:
            assignment = get_object_or_404(UserRoleAssignment, id=assignment_id)
            assignment.delete()
            messages.success(request, 'Role removed from user successfully!')
            return JsonResponse({'success': True, 'message': 'Role removed successfully'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def user_roles(request, user_id):
    """Get roles assigned to a user (AJAX)"""
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        return JsonResponse({'success': False, 'message': 'Permission denied'})
    
    try:
        user = User.objects.get(id=user_id)
        assignments = UserRoleAssignment.objects.filter(user=user, is_active=True).select_related('role')
        roles = [{'id': a.role.id, 'name': a.role.name} for a in assignments]
        return JsonResponse({'success': True, 'roles': roles})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'})







from decimal import Decimal
from django.db.models import Sum, Count, Q
from .models import Purchase

@login_required
def purchases(request):
    """List all purchases"""
    tenant = request.user.tenant
    
    # Date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    category = request.GET.get('category')
    search = request.GET.get('search', '')
    
    if not date_from:
        date_from = date.today() - timedelta(days=30)
    if not date_to:
        date_to = date.today()
    
    # Convert to date objects
    if isinstance(date_from, str):
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
    if isinstance(date_to, str):
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
    
    # Get purchases
    purchases_qs = Purchase.objects.filter(
        tenant=tenant,
        purchase_date__gte=date_from,
        purchase_date__lte=date_to
    ).select_related('recorded_by')
    
    # Apply filters
    if category:
        purchases_qs = purchases_qs.filter(category=category)
    
    if search:
        purchases_qs = purchases_qs.filter(
            Q(item_name__icontains=search) |
            Q(supplier__icontains=search)
        )
    
    # Group by date
    purchases_by_date = {}
    total_cost = Decimal('0.00')
    total_items = 0
    
    for purchase in purchases_qs:
        date_key = purchase.purchase_date
        
        if date_key not in purchases_by_date:
            purchases_by_date[date_key] = {
                'items': [],
                'total_cost': Decimal('0.00'),
                'total_items': 0
            }
        
        purchase_data = {
            'id': purchase.id,
            'item_name': purchase.item_name,
            'category': purchase.get_category_display(),
            'category_code': purchase.category,
            'quantity': float(purchase.quantity),
            'unit': purchase.unit,
            'unit_price': float(purchase.unit_price),
            'total_cost': float(purchase.total_cost),
            'supplier': purchase.supplier,
            'payment_status': purchase.payment_status,
            'payment_method': purchase.payment_method,
            'notes': purchase.notes,
            'created_at': purchase.created_at,
            'recorded_by': purchase.recorded_by.full_name if purchase.recorded_by else 'N/A',
        }
        
        purchases_by_date[date_key]['items'].append(purchase_data)
        purchases_by_date[date_key]['total_cost'] += purchase.total_cost
        purchases_by_date[date_key]['total_items'] += 1
        
        total_cost += purchase.total_cost
        total_items += 1
    
    # Sort dates descending
    sorted_purchases = dict(sorted(purchases_by_date.items(), reverse=True))
    
    # Get categories for filter
    categories = Purchase.PURCHASE_TYPE_CHOICES
    
    context = {
        'tenant': tenant,
        'purchases_by_date': sorted_purchases,
        'total_cost': total_cost,
        'total_items': total_items,
        'date_from': date_from,
        'date_to': date_to,
        'categories': categories,
        'active_tab': 'purchases',
    }
    return render(request, 'food_master/purchases.html', context)


@login_required
def add_purchase(request):
    """Add a new purchase record"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        item_name = request.POST.get('item_name')
        category = request.POST.get('category')
        quantity = request.POST.get('quantity')
        unit = request.POST.get('unit')
        unit_price = request.POST.get('unit_price')
        supplier = request.POST.get('supplier')
        supplier_contact = request.POST.get('supplier_contact')
        payment_status = request.POST.get('payment_status')
        payment_method = request.POST.get('payment_method')
        purchase_date = request.POST.get('purchase_date')
        notes = request.POST.get('notes')
        
        if not all([item_name, category, quantity, unit, unit_price]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('food_master:add_purchase')
        
        try:
            purchase = Purchase.objects.create(
                tenant=tenant,
                item_name=item_name,
                category=category,
                quantity=Decimal(quantity),
                unit=unit,
                unit_price=Decimal(unit_price),
                supplier=supplier,
                supplier_contact=supplier_contact,
                payment_status=payment_status or 'paid',
                payment_method=payment_method,
                purchase_date=purchase_date or date.today(),
                notes=notes,
                recorded_by=request.user
            )
            
            messages.success(request, f'Purchase of "{item_name}" recorded successfully!')
            return redirect('food_master:purchases')
            
        except Exception as e:
            messages.error(request, f'Error recording purchase: {str(e)}')
    
    context = {
        'tenant': tenant,
        'categories': Purchase.PURCHASE_TYPE_CHOICES,
        'units': Purchase._meta.get_field('unit').choices,
        'payment_statuses': Purchase.PAYMENT_STATUS_CHOICES,
        'payment_methods': [
            ('cash', 'Cash'),
            ('mpesa', 'M-Pesa'),
            ('bank_transfer', 'Bank Transfer'),
            ('card', 'Card'),
            ('credit', 'Credit'),
        ],
        'today': date.today(),
        'active_tab': 'purchases',
    }
    return render(request, 'food_master/add_purchase.html', context)


@login_required
def purchase_detail(request, purchase_id):
    """View purchase details"""
    tenant = request.user.tenant
    purchase = get_object_or_404(Purchase, id=purchase_id, tenant=tenant)
    
    context = {
        'tenant': tenant,
        'purchase': purchase,
        'active_tab': 'purchases',
    }
    return render(request, 'food_master/purchase_detail.html', context)


@login_required
def edit_purchase(request, purchase_id):
    """Edit a purchase record"""
    tenant = request.user.tenant
    purchase = get_object_or_404(Purchase, id=purchase_id, tenant=tenant)
    
    if request.method == 'POST':
        item_name = request.POST.get('item_name')
        category = request.POST.get('category')
        quantity = request.POST.get('quantity')
        unit = request.POST.get('unit')
        unit_price = request.POST.get('unit_price')
        supplier = request.POST.get('supplier')
        supplier_contact = request.POST.get('supplier_contact')
        payment_status = request.POST.get('payment_status')
        payment_method = request.POST.get('payment_method')
        purchase_date = request.POST.get('purchase_date')
        notes = request.POST.get('notes')
        
        if not all([item_name, category, quantity, unit, unit_price]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'food_master/edit_purchase.html', {'purchase': purchase})
        
        try:
            purchase.item_name = item_name
            purchase.category = category
            purchase.quantity = Decimal(quantity)
            purchase.unit = unit
            purchase.unit_price = Decimal(unit_price)
            purchase.supplier = supplier
            purchase.supplier_contact = supplier_contact
            purchase.payment_status = payment_status
            purchase.payment_method = payment_method
            purchase.purchase_date = purchase_date or date.today()
            purchase.notes = notes
            purchase.save()
            
            messages.success(request, f'Purchase updated successfully!')
            return redirect('food_master:purchase_detail', purchase_id=purchase.id)
            
        except Exception as e:
            messages.error(request, f'Error updating purchase: {str(e)}')
    
    context = {
        'tenant': tenant,
        'purchase': purchase,
        'categories': Purchase.PURCHASE_TYPE_CHOICES,
        'units': Purchase._meta.get_field('unit').choices,
        'payment_statuses': Purchase.PAYMENT_STATUS_CHOICES,
        'payment_methods': [
            ('cash', 'Cash'),
            ('mpesa', 'M-Pesa'),
            ('bank_transfer', 'Bank Transfer'),
            ('card', 'Card'),
            ('credit', 'Credit'),
        ],
        'active_tab': 'purchases',
    }
    return render(request, 'food_master/edit_purchase.html', context)


@login_required
def delete_purchase(request, purchase_id):
    """Delete a purchase record"""
    tenant = request.user.tenant
    purchase = get_object_or_404(Purchase, id=purchase_id, tenant=tenant)
    
    if request.method == 'POST':
        item_name = purchase.item_name
        purchase.delete()
        messages.success(request, f'Purchase "{item_name}" deleted successfully!')
        return JsonResponse({'success': True, 'message': 'Purchase deleted'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})



@login_required
def reports(request):
    """View reports"""
    tenant = request.user.tenant
    
    # Get report type and date range
    report_type = request.GET.get('type', 'weekly')  # Default to weekly to show more data
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Calculate date range based on report type
    if not date_from:
        if report_type == 'daily':
            date_from = date.today()
        elif report_type == 'weekly':
            date_from = date.today() - timedelta(days=7)
        elif report_type == 'monthly':
            date_from = date.today() - timedelta(days=30)
        elif report_type == 'yearly':
            date_from = date.today() - timedelta(days=365)
        else:  # custom or default
            date_from = date.today() - timedelta(days=7)  # Default to 7 days
    
    if not date_to:
        date_to = date.today()
    
    # Convert to date objects if they're strings
    if isinstance(date_from, str):
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
    if isinstance(date_to, str):
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
    
    # Get ALL orders for the period (including pending)
    all_orders = Order.objects.filter(
        tenant=tenant,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to
    ).select_related('customer', 'table', 'branch')
    
    # Order counts
    total_orders = all_orders.count()
    pending_orders = all_orders.filter(
        status__in=['pending', 'confirmed', 'preparing', 'ready']
    ).count()
    
    # Revenue from completed orders only
    completed_orders = all_orders.filter(status='completed')
    total_revenue = completed_orders.filter(
        payment_status='paid'
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Pending revenue
    pending_revenue = all_orders.filter(
        payment_status='pending'
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Total payments
    total_payments = all_orders.filter(
        payment_status='paid'
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Pending payments
    pending_payments = all_orders.filter(
        payment_status='pending'
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Purchase cost (from completed orders)
    purchase_cost = OrderItem.objects.filter(
        order__tenant=tenant,
        order__created_at__date__gte=date_from,
        order__created_at__date__lte=date_to,
        order__status='completed'
    ).aggregate(
        total_cost=Sum('menu_item__cost') * Sum('quantity')
    )['total_cost'] or Decimal('0.00')
    
    # Profit
    total_profit = total_revenue - purchase_cost
    
    # Sales by day (only completed/paid orders)
    sales_by_day = all_orders.filter(
        status='completed',
        payment_status='paid'
    ).annotate(
        day=TruncDate('created_at')
    ).values('day').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('day')
    
    # Popular items (from completed orders)
    popular_items = OrderItem.objects.filter(
        order__tenant=tenant,
        order__created_at__date__gte=date_from,
        order__created_at__date__lte=date_to,
        order__status='completed'
    ).values(
        'menu_item__name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('subtotal')
    ).order_by('-total_quantity')[:10]
    
    # Get recent orders for display (max 20)
    recent_orders = all_orders.order_by('-created_at')[:20]
    
    context = {
        'tenant': tenant,
        'active_tab': 'reports',
        'report_type': report_type,
        'date_from': date_from,
        'date_to': date_to,
        
        # Stats
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_revenue': total_revenue,
        'pending_revenue': pending_revenue,
        'total_payments': total_payments,
        'pending_payments': pending_payments,
        'total_purchase_cost': purchase_cost,
        'total_profit': total_profit,
        
        # Lists
        'sales_by_day': sales_by_day,
        'popular_items': popular_items,
        'recent_orders': recent_orders,  # Added for the orders table
    }
    return render(request, 'food_master/reports.html', context)


