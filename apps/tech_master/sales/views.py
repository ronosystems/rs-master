# apps/tech_master/sales/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from django.core.paginator import Paginator
from decimal import Decimal
from django.http import JsonResponse
from django.conf import settings
import logging

# ✅ Clean imports - no duplicates
from apps.tech_master.sales.models import Sale, SaleItem, Return
from apps.tech_master.inventory.models import Product, ProductUnit
from apps.shared.customers.models import Customer
from apps.shared.tenants.models import SyncQueue

logger = logging.getLogger(__name__)


# ============================================
# SALES AGENT - SALE CREATION
# ============================================

@login_required
def agent_sale(request):
    """Sales Agent - Create a new sale from assigned stock"""
    tenant = request.user.tenant
    user = request.user
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    # ✅ Get all available units assigned to this sales agent
    products = ProductUnit.objects.filter(
        tenant=tenant,
        current_owner=user,
        status='available'
    ).select_related('product', 'branch')
    
    if request.method == 'POST':
        # Get customer details
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        customer_id_number = request.POST.get('customer_id_number', '').strip()
        
        next_of_kin_name = request.POST.get('next_of_kin_name', '').strip()
        next_of_kin_phone = request.POST.get('next_of_kin_phone', '').strip()
        next_of_kin_relationship = request.POST.get('next_of_kin_relationship', '').strip()
        
        # Get IMEI/Serial
        imei = request.POST.get('imei', '').strip()
        
        # Get selling price (editable)
        selling_price = request.POST.get('selling_price', '').strip()
        payment_method = request.POST.get('payment_method', 'credit').strip()
        
        # Validate
        if not customer_name:
            messages.error(request, 'Customer name is required')
            return redirect('tech_master:agent_sale')
        
        if not customer_phone:
            messages.error(request, 'Customer phone number is required')
            return redirect('tech_master:agent_sale')
        
        if not imei:
            messages.error(request, 'Please select a product by IMEI/Serial number')
            return redirect('tech_master:agent_sale')
        
        if not selling_price:
            messages.error(request, 'Selling price is required')
            return redirect('tech_master:agent_sale')
        
        try:
            selling_price = Decimal(str(selling_price))
            if selling_price <= 0:
                messages.error(request, 'Selling price must be greater than 0')
                return redirect('tech_master:agent_sale')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid selling price')
            return redirect('tech_master:agent_sale')
        
        # ✅ Find the unit by IMEI or Serial
        unit = ProductUnit.objects.filter(
            tenant=tenant,
            current_owner=user,
            status='available'
        ).filter(
            Q(imei_number=imei) | Q(serial_number=imei)
        ).first()
        
        if not unit:
            messages.error(request, 'Product not found in your assigned stock')
            return redirect('tech_master:agent_sale')
        
        # ✅ Check if unit is still available
        if unit.status != 'available':
            messages.error(request, f'Unit {imei} is no longer available (Status: {unit.status})')
            return redirect('tech_master:agent_sale')
        
        # ✅ Create or get customer
        customer, created = Customer.objects.get_or_create(
            tenant=tenant,
            phone=customer_phone,
            defaults={
                'name': customer_name,
                'id_number': customer_id_number,
                'next_of_kin_name': next_of_kin_name,
                'next_of_kin_phone': next_of_kin_phone,
                'next_of_kin_relationship': next_of_kin_relationship,
                'created_by': user
            }
        )
        
        # ✅ Generate invoice number
        today = timezone.now()
        invoice_prefix = f"SALE-{today.strftime('%Y%m%d')}"
        last_sale = Sale.objects.filter(
            tenant=tenant,
            invoice_no__startswith=invoice_prefix
        ).order_by('-invoice_no').first()
        
        if last_sale:
            try:
                last_number = int(last_sale.invoice_no.split('-')[-1])
                new_number = last_number + 1
            except (ValueError, IndexError):
                new_number = 1
        else:
            new_number = 1
        
        invoice_no = f"{invoice_prefix}-{new_number:04d}"
        
        # ✅ Create sale
        sale = Sale.objects.create(
            tenant=tenant,
            customer=customer,
            customer_name=customer_name,
            customer_phone=customer_phone,
            cashier=user,
            invoice_no=invoice_no,
            subtotal=selling_price,
            total=selling_price,
            payment_method=payment_method,
            status='completed',
            tax_inclusive=True,
            branch=unit.branch
        )
        
        # ✅ Create sale item
        sale_item = SaleItem.objects.create(
            sale=sale,
            product=unit.product,
            product_unit=unit,
            quantity=1,
            price=selling_price,
            subtotal=selling_price
        )
        
        # ✅ Mark unit as sold
        unit.status = 'sold'
        unit.sold_at_price = selling_price
        unit.sold_date = timezone.now()
        unit.sold_by = user
        unit.save()
        
        # ✅ Update product quantities
        unit.product.update_quantities()
        
        # ✅ Update customer total spent
        customer.total_spent = (customer.total_spent or 0) + selling_price
        customer.save()
        
        # ✅ Queue sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='Sale',
                    object_id=str(sale.id),
                    operation='CREATE',
                    data={
                        'id': sale.id,
                        'invoice_no': sale.invoice_no,
                        'customer_id': customer.id if customer else None,
                        'customer_name': customer_name,
                        'customer_phone': customer_phone,
                        'branch_id': unit.branch_id if unit.branch else None,
                        'subtotal': str(sale.subtotal),
                        'total': str(sale.total),
                        'payment_method': payment_method,
                        'status': 'completed',
                        'cashier_id': user.id,
                        'tenant_id': tenant.id,
                        'created_at': sale.created_at.isoformat(),
                    },
                    priority=8  # High priority for sales
                )
                
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='SaleItem',
                    object_id=str(sale_item.id),
                    operation='CREATE',
                    data={
                        'id': sale_item.id,
                        'sale_id': sale.id,
                        'product_id': unit.product_id,
                        'product_unit_id': unit.id,
                        'quantity': 1,
                        'price': str(selling_price),
                        'subtotal': str(selling_price),
                        'tenant_id': tenant.id,
                    },
                    priority=8
                )
                
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='ProductUnit',
                    object_id=str(unit.id),
                    operation='UPDATE',
                    data={
                        'id': unit.id,
                        'status': 'sold',
                        'sold_at_price': str(selling_price),
                        'sold_date': unit.sold_date.isoformat(),
                        'sold_by_id': user.id,
                        'tenant_id': tenant.id,
                    },
                    priority=8
                )
                logger.debug(f"✅ Queued Sale sync: {sale.invoice_no}")
            except Exception as e:
                logger.error(f"Failed to queue Sale sync: {e}")
        
        messages.success(request, f'Sale completed successfully! {unit.product.name} sold for KES {selling_price:.2f}')
        return redirect('tech_master:my_sales')
    
    # ✅ GET request - show the form
    product_list = []
    for unit in products:
        product_list.append({
            'id': unit.id,
            'name': unit.product.name,
            'model': unit.product.model,
            'imei': unit.imei_number or '',
            'serial': unit.serial_number or '',
            'selling_price': float(unit.unit_selling_price or unit.product.selling_price),
            'buying_price': float(unit.unit_buying_price or unit.product.buying_price),
            'branch': unit.branch.name if unit.branch else 'Main Shop'
        })
    
    context = {
        'tenant': tenant,
        'products': product_list,
        'total_available': products.count(),
        'active_tab': 'sales',
    }
    return render(request, 'tech_master/sales/agent_sale.html', context)


# ============================================
# SALES AGENT - MY STOCK
# ============================================

@login_required
def my_stock(request):
    """Sales Agent - View their assigned stock (product units)"""
    tenant = request.user.tenant
    user = request.user
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    # ✅ Get all product units assigned to this sales agent
    my_units = ProductUnit.objects.filter(
        tenant=tenant,
        current_owner=user,
        status__in=['available', 'reserved']
    ).select_related(
        'product',
        'product__category',
        'branch'
    ).order_by('-assigned_date', 'product__name')
    
    # Count statistics
    total_units = my_units.count()
    available_units = my_units.filter(status='available').count()
    reserved_units = my_units.filter(status='reserved').count()
    sold_units = ProductUnit.objects.filter(
        tenant=tenant,
        current_owner=user,
        status='sold'
    ).count()
    
    # Get unique products
    products = my_units.values('product').distinct()
    total_products = products.count()
    
    # Calculate total value of assigned stock
    total_value = 0
    for unit in my_units:
        price = unit.unit_selling_price or unit.product.selling_price
        total_value += float(price)
    
    # Group by product for better display
    grouped_stock = {}
    for unit in my_units:
        product_name = unit.product.name
        if product_name not in grouped_stock:
            grouped_stock[product_name] = {
                'product': unit.product,
                'units': [],
                'total_available': 0,
                'total_reserved': 0,
                'total_value': 0
            }
        grouped_stock[product_name]['units'].append(unit)
        if unit.status == 'available':
            grouped_stock[product_name]['total_available'] += 1
        elif unit.status == 'reserved':
            grouped_stock[product_name]['total_reserved'] += 1
        price = unit.unit_selling_price or unit.product.selling_price
        grouped_stock[product_name]['total_value'] += float(price)
    
    # Filter by product or search
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    
    if search_query:
        my_units = my_units.filter(
            Q(product__name__icontains=search_query) |
            Q(product__sku_code__icontains=search_query) |
            Q(imei_number__icontains=search_query) |
            Q(serial_number__icontains=search_query)
        )
    
    if status_filter:
        my_units = my_units.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(my_units, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'user': user,
        'my_units': page_obj,
        'total_units': total_units,
        'available_units': available_units,
        'reserved_units': reserved_units,
        'sold_units': sold_units,
        'total_products': total_products,
        'total_value': total_value,
        'grouped_stock': grouped_stock,
        'search_query': search_query,
        'status_filter': status_filter,
        'active_tab': 'my_stock',
    }
    return render(request, 'tech_master/sales/my_stock.html', context)


@login_required
def my_stock_detail(request, unit_id):
    """Sales Agent - View details of a specific stock unit"""
    tenant = request.user.tenant
    user = request.user
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    unit = get_object_or_404(
        ProductUnit,
        id=unit_id,
        tenant=tenant,
        current_owner=user
    )
    
    context = {
        'tenant': tenant,
        'unit': unit,
        'active_tab': 'my_stock',
    }
    return render(request, 'tech_master/sales/my_stock_detail.html', context)


@login_required
def my_stock_sell(request, unit_id):
    """Sales Agent - Sell a unit from their stock"""
    tenant = request.user.tenant
    user = request.user
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    unit = get_object_or_404(
        ProductUnit,
        id=unit_id,
        tenant=tenant,
        current_owner=user,
        status='available'
    )
    
    if request.method == 'POST':
        # ✅ Get all fields from the form
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        customer_id_number = request.POST.get('customer_id_number', '').strip()
        
        next_of_kin_name = request.POST.get('next_of_kin_name', '').strip()
        next_of_kin_phone = request.POST.get('next_of_kin_phone', '').strip()
        next_of_kin_relationship = request.POST.get('next_of_kin_relationship', '').strip()
        
        selling_price = request.POST.get('selling_price', '').strip()
        payment_method = request.POST.get('payment_method', 'credit').strip()
        
        # ✅ Validate required fields
        if not customer_name:
            messages.error(request, 'Customer name is required')
            return redirect('tech_master:my_stock_sell', unit_id=unit.id)
        
        if not customer_phone:
            messages.error(request, 'Customer phone number is required')
            return redirect('tech_master:my_stock_sell', unit_id=unit.id)
        
        if not selling_price:
            messages.error(request, 'Selling price is required')
            return redirect('tech_master:my_stock_sell', unit_id=unit.id)
        
        try:
            selling_price = Decimal(str(selling_price))
            if selling_price <= 0:
                messages.error(request, 'Selling price must be greater than 0')
                return redirect('tech_master:my_stock_sell', unit_id=unit.id)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid selling price')
            return redirect('tech_master:my_stock_sell', unit_id=unit.id)
        
        # ✅ Check if unit is still available
        if unit.status != 'available':
            messages.error(request, f'Unit is no longer available (Status: {unit.status})')
            return redirect('tech_master:my_stock')
        
        # ✅ Create or get customer
        customer, created = Customer.objects.get_or_create(
            tenant=tenant,
            phone=customer_phone,
            defaults={
                'name': customer_name,
                'id_number': customer_id_number,
                'next_of_kin_name': next_of_kin_name,
                'next_of_kin_phone': next_of_kin_phone,
                'next_of_kin_relationship': next_of_kin_relationship,
                'created_by': user
            }
        )
        
        # ✅ Update customer if exists and fields are provided
        if not created:
            if customer_name and not customer.name:
                customer.name = customer_name
            if customer_id_number and not customer.id_number:
                customer.id_number = customer_id_number
            if next_of_kin_name and not customer.next_of_kin_name:
                customer.next_of_kin_name = next_of_kin_name
            if next_of_kin_phone and not customer.next_of_kin_phone:
                customer.next_of_kin_phone = next_of_kin_phone
            if next_of_kin_relationship and not customer.next_of_kin_relationship:
                customer.next_of_kin_relationship = next_of_kin_relationship
            customer.save()
        
        # ✅ Generate invoice number
        today = timezone.now()
        invoice_prefix = f"SALE-{today.strftime('%Y%m%d')}"
        last_sale = Sale.objects.filter(
            tenant=tenant,
            invoice_no__startswith=invoice_prefix
        ).order_by('-invoice_no').first()
        
        if last_sale:
            try:
                last_number = int(last_sale.invoice_no.split('-')[-1])
                new_number = last_number + 1
            except (ValueError, IndexError):
                new_number = 1
        else:
            new_number = 1
        
        invoice_no = f"{invoice_prefix}-{new_number:04d}"
        
        # ✅ Create sale
        sale = Sale.objects.create(
            tenant=tenant,
            customer=customer,
            cashier=user,
            customer_name=customer_name,
            customer_phone=customer_phone,
            invoice_no=invoice_no,
            subtotal=selling_price,
            total=selling_price,
            payment_method=payment_method,
            status='completed',
            tax_inclusive=True,
            branch=unit.branch
        )
        
        # ✅ Create sale item
        sale_item = SaleItem.objects.create(
            sale=sale,
            product=unit.product,
            product_unit=unit,
            quantity=1,
            price=selling_price,
            subtotal=selling_price
        )
        
        # ✅ Mark unit as sold
        unit.status = 'sold'
        unit.sold_at_price = selling_price
        unit.sold_date = timezone.now()
        unit.sold_by = user
        unit.save()
        
        # ✅ Update product quantities
        unit.product.update_quantities()
        
        # ✅ Update customer total spent
        customer.total_spent = (customer.total_spent or 0) + selling_price
        customer.save()
        
        # ✅ Queue sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='Sale',
                    object_id=str(sale.id),
                    operation='CREATE',
                    data={
                        'id': sale.id,
                        'invoice_no': sale.invoice_no,
                        'customer_id': customer.id if customer else None,
                        'customer_name': customer_name,
                        'customer_phone': customer_phone,
                        'branch_id': unit.branch_id if unit.branch else None,
                        'subtotal': str(sale.subtotal),
                        'total': str(sale.total),
                        'payment_method': payment_method,
                        'status': 'completed',
                        'cashier_id': user.id,
                        'tenant_id': tenant.id,
                        'created_at': sale.created_at.isoformat(),
                    },
                    priority=8
                )
                
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='SaleItem',
                    object_id=str(sale_item.id),
                    operation='CREATE',
                    data={
                        'id': sale_item.id,
                        'sale_id': sale.id,
                        'product_id': unit.product_id,
                        'product_unit_id': unit.id,
                        'quantity': 1,
                        'price': str(selling_price),
                        'subtotal': str(selling_price),
                        'tenant_id': tenant.id,
                    },
                    priority=8
                )
                
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='ProductUnit',
                    object_id=str(unit.id),
                    operation='UPDATE',
                    data={
                        'id': unit.id,
                        'status': 'sold',
                        'sold_at_price': str(selling_price),
                        'sold_date': unit.sold_date.isoformat(),
                        'sold_by_id': user.id,
                        'tenant_id': tenant.id,
                    },
                    priority=8
                )
                logger.debug(f"✅ Queued Sale sync: {sale.invoice_no}")
            except Exception as e:
                logger.error(f"Failed to queue Sale sync: {e}")
        
        messages.success(request, f'Sale completed successfully! {unit.product.name} sold for KES {selling_price:.2f}')
        return redirect('tech_master:my_sales')
    
    context = {
        'tenant': tenant,
        'unit': unit,
        'active_tab': 'my_stock',
    }
    return render(request, 'tech_master/sales/my_stock_sell.html', context)


# ============================================
# SALES AGENT - MY SALES
# ============================================

@login_required
def my_sales(request):
    """Sales Agent - View their own sales only"""
    tenant = request.user.tenant
    user = request.user
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    # ✅ Only show sales made by this sales agent
    sales = Sale.objects.filter(
        tenant=tenant,
        cashier=user
    ).order_by('-created_at')
    
    # Statistics
    total_sales = sales.aggregate(total=Sum('total'))['total'] or Decimal('0')
    total_count = sales.count()
    
    # Today's sales
    today = timezone.now().date()
    today_sales = sales.filter(created_at__date=today)
    today_count = today_sales.count()
    today_total = today_sales.aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    # Pagination
    paginator = Paginator(sales, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'sales': page_obj,
        'total_sales': total_sales,
        'total_count': total_count,
        'today': today,
        'today_count': today_count,
        'today_total': today_total,
        'active_tab': 'my_sales',
    }
    return render(request, 'tech_master/sales/my_sales.html', context)


# ============================================
# SALES SEARCH
# ============================================

@login_required
def sales_search(request):
    """Search for sales by IMEI/Serial or Invoice number"""
    tenant = request.user.tenant
    user = request.user
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    search_query = request.GET.get('q', '').strip()
    search_type = request.GET.get('type', 'all')
    
    sale_result = None
    error_message = None
    
    if search_query:
        try:
            # Search by Invoice Number
            if search_type == 'invoice' or search_type == 'all':
                sale_result = Sale.objects.filter(
                    tenant=tenant,
                    invoice_no__icontains=search_query
                ).first()
                
                if sale_result:
                    return redirect('tech_master:sale_detail', sale_id=sale_result.id)
            
            # Search by IMEI/Serial
            if search_type == 'imei' or search_type == 'all':
                # Find the product unit by IMEI/Serial
                unit = ProductUnit.objects.filter(
                    Q(imei_number=search_query) | Q(serial_number=search_query),
                    tenant=tenant
                ).first()
                
                if unit:
                    # Find the sale item that contains this unit
                    sale_item = SaleItem.objects.filter(
                        product_unit=unit
                    ).select_related('sale').first()
                    
                    if sale_item:
                        sale_result = sale_item.sale
                        return redirect('tech_master:sale_detail', sale_id=sale_result.id)
                    else:
                        error_message = f"IMEI/Serial '{search_query}' found but not linked to any sale"
                else:
                    error_message = f"No product found with IMEI/Serial '{search_query}'"
        
        except Exception as e:
            error_message = f"Search error: {str(e)}"
    
    # Show search results if no redirect happened
    search_results = []
    if search_query and not sale_result and not error_message:
        # Try to find sales by customer name or phone
        search_results = Sale.objects.filter(
            tenant=tenant
        ).filter(
            Q(customer_name__icontains=search_query) |
            Q(customer_phone__icontains=search_query) |
            Q(invoice_no__icontains=search_query)
        ).order_by('-created_at')[:20]
    
    context = {
        'tenant': tenant,
        'search_query': search_query,
        'search_type': search_type,
        'search_results': search_results,
        'error_message': error_message,
        'sale_result': sale_result,
        'active_tab': 'sales_search',
    }
    return render(request, 'tech_master/sales/sales_search.html', context)


@login_required
def sales_search_ajax(request):
    """AJAX endpoint for live search suggestions"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'results': []})
    
    results = []
    
    # Search by Invoice Number
    sales = Sale.objects.filter(
        tenant=tenant,
        invoice_no__icontains=query
    ).values('id', 'invoice_no', 'customer_name', 'total')[:10]
    
    for sale in sales:
        results.append({
            'type': 'invoice',
            'id': sale['id'],
            'invoice_no': sale['invoice_no'],
            'customer_name': sale['customer_name'] or 'Walk-in',
            'total': float(sale['total']) if sale['total'] else 0,
            'url': f"/tech/sales/{sale['id']}/"
        })
    
    # Search by IMEI/Serial
    units = ProductUnit.objects.filter(
        Q(imei_number__icontains=query) | Q(serial_number__icontains=query),
        tenant=tenant
    ).select_related('product')[:10]
    
    for unit in units:
        sale_item = SaleItem.objects.filter(product_unit=unit).select_related('sale').first()
        if sale_item:
            sale = sale_item.sale
            results.append({
                'type': 'imei',
                'id': sale.id,
                'identifier': unit.imei_number or unit.serial_number,
                'product_name': unit.product.name,
                'invoice_no': sale.invoice_no,
                'customer_name': sale.customer_name or 'Walk-in',
                'total': float(sale.total) if sale.total else 0,
                'url': f"/tech/sales/{sale.id}/"
            })
    
    return JsonResponse({'results': results})


# ============================================
# SALES HISTORY
# ============================================

@login_required
def sales_history(request):
    """View sales history"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    sales = Sale.objects.filter(tenant=tenant).order_by('-created_at')
    
    # Filters
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if search:
        sales = sales.filter(
            Q(invoice_no__icontains=search) |
            Q(customer_name__icontains=search)
        )
    if status:
        sales = sales.filter(status=status)
    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)
    
    # Statistics
    total_sales = sales.aggregate(total=Sum('total'))['total'] or Decimal('0')
    total_count = sales.count()
    
    # Pagination
    paginator = Paginator(sales, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'sales': page_obj,
        'total_sales': total_sales,
        'total_count': total_count,
        'search': search,
        'status_filter': status,
        'date_from': date_from,
        'date_to': date_to,
        'active_tab': 'sales',
    }
    return render(request, 'tech_master/sales/sales_history.html', context)


# ============================================
# SALE DETAIL
# ============================================

@login_required
def sale_detail(request, sale_id):
    """View sale details"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    # Get the sale with all related data
    sale = get_object_or_404(
        Sale.objects.select_related(
            'customer', 
            'cashier', 
            'branch'
        ),
        id=sale_id, 
        tenant=tenant
    )
    
    # Get sale items with product and product unit details
    items = sale.items.all().select_related(
        'product', 
        'product_unit',
        'product__category'
    )
    
    # Calculate total quantity
    total_quantity = sum(item.quantity for item in items)
    
    # Calculate average price
    average_price = sale.total / total_quantity if total_quantity > 0 else Decimal('0')
    
    # Get customer next of kin details
    customer = sale.customer
    next_of_kin_name = None
    next_of_kin_phone = None
    next_of_kin_relationship = None
    customer_id_number = None
    
    if customer:
        customer_id_number = customer.id_number
        next_of_kin_name = customer.next_of_kin_name
        next_of_kin_phone = customer.next_of_kin_phone
        next_of_kin_relationship = customer.next_of_kin_relationship
    
    context = {
        'tenant': tenant,
        'sale': sale,
        'items': items,
        'total_quantity': total_quantity,
        'average_price': average_price,
        'customer_id_number': customer_id_number,
        'next_of_kin_name': next_of_kin_name,
        'next_of_kin_phone': next_of_kin_phone,
        'next_of_kin_relationship': next_of_kin_relationship,
        'active_tab': 'sales',
    }
    return render(request, 'tech_master/sales/sale_detail.html', context)


# ============================================
# RECEIPT
# ============================================

@login_required
def receipt(request, sale_id):
    """View sale receipt"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    sale = get_object_or_404(Sale, id=sale_id, tenant=tenant)
    items = sale.items.all().select_related('product', 'product_unit')
    
    # ✅ Safe receipt settings loading
    receipt_settings = None
    try:
        from apps.shared.settings.models import ReceiptSetting
        receipt_settings = ReceiptSetting.objects.filter(tenant=tenant).first()
    except ImportError:
        pass  # Settings app might not exist yet
    
    context = {
        'tenant': tenant,
        'sale': sale,
        'sale_items': items,
        'receipt_settings': receipt_settings,
    }
    return render(request, 'tech_master/sales/receipt.html', context)


# ============================================
# RETURNS
# ============================================

@login_required
def create_return(request, sale_id):
    """Create a return for a sale"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    sale = get_object_or_404(Sale, id=sale_id, tenant=tenant)
    
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 0))
        reason = request.POST.get('reason', '')
        
        if not product_id or quantity <= 0:
            messages.error(request, 'Please select a product and quantity')
            return redirect('tech_master:create_return', sale_id=sale.id)
        
        product = get_object_or_404(Product, id=product_id, tenant=tenant)
        
        # Check if return already exists for this product
        existing_return = Return.objects.filter(
            sale=sale,
            product=product,
            status__in=['pending', 'approved']
        ).first()
        
        if existing_return:
            messages.error(request, f'Return already exists for {product.name}')
            return redirect('tech_master:create_return', sale_id=sale.id)
        
        # Calculate return amount
        sale_item = sale.items.filter(product=product).first()
        if sale_item:
            amount = sale_item.price * quantity
        else:
            amount = product.selling_price * quantity
        
        # Create return
        return_obj = Return.objects.create(
            tenant=tenant,
            sale=sale,
            product=product,
            quantity=quantity,
            amount=amount,
            reason=reason,
            status='pending',
            created_by=request.user
        )
        
        # ✅ Queue return creation sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='Return',
                    object_id=str(return_obj.id),
                    operation='CREATE',
                    data={
                        'id': return_obj.id,
                        'sale_id': sale.id,
                        'product_id': product.id,
                        'quantity': quantity,
                        'amount': str(amount),
                        'reason': reason,
                        'status': 'pending',
                        'created_by_id': request.user.id,
                        'tenant_id': tenant.id,
                        'created_at': return_obj.created_at.isoformat(),
                    },
                    priority=6
                )
                logger.debug(f"✅ Queued Return creation sync: #{return_obj.id}")
            except Exception as e:
                logger.error(f"Failed to queue Return sync: {e}")
        
        messages.success(request, f'Return request created for {product.name}')
        return redirect('tech_master:return_detail', return_id=return_obj.id)
    
    # Get sale items for selection
    items = sale.items.all().select_related('product')
    
    context = {
        'tenant': tenant,
        'sale': sale,
        'items': items,
        'active_tab': 'sales',
    }
    return render(request, 'tech_master/sales/create_return.html', context)


@login_required
def return_list(request):
    """List all returns"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    returns = Return.objects.filter(tenant=tenant).order_by('-created_at')
    
    # Filters
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if search:
        returns = returns.filter(
            Q(sale__invoice_no__icontains=search) |
            Q(sale__customer_name__icontains=search) |
            Q(product__name__icontains=search)
        )
    if status_filter:
        returns = returns.filter(status=status_filter)
    if date_from:
        returns = returns.filter(created_at__date__gte=date_from)
    if date_to:
        returns = returns.filter(created_at__date__lte=date_to)
    
    # Statistics
    total_returns = returns.count()
    pending_count = returns.filter(status='pending').count()
    approved_count = returns.filter(status='approved').count()
    rejected_count = returns.filter(status='rejected').count()
    completed_count = returns.filter(status='completed').count()
    
    # Pagination
    paginator = Paginator(returns, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'returns': page_obj,
        'total_returns': total_returns,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'completed_count': completed_count,
        'search': search,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'active_tab': 'sales',
    }
    return render(request, 'tech_master/sales/return_list.html', context)


@login_required
def return_detail(request, return_id):
    """View return details"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    return_obj = get_object_or_404(Return, id=return_id, tenant=tenant)
    
    context = {
        'tenant': tenant,
        'return': return_obj,
        'active_tab': 'sales',
    }
    return render(request, 'tech_master/sales/return_detail.html', context)


@login_required
def approve_return(request, return_id):
    """Approve a return with sync support"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    return_obj = get_object_or_404(Return, id=return_id, tenant=tenant)
    
    if return_obj.status != 'pending':
        messages.warning(request, 'This return is already processed')
        return redirect('tech_master:return_detail', return_id=return_obj.id)
    
    # Approve the return
    return_obj.status = 'approved'
    return_obj.approved_by = request.user
    return_obj.approved_at = timezone.now()
    return_obj.save()
    
    # Update product stock (if single item)
    if return_obj.product and return_obj.product.category.is_single_item:
        sale_item = return_obj.sale.items.filter(product=return_obj.product).first()
        if sale_item and sale_item.product_unit:
            unit = sale_item.product_unit
            unit.status = 'available'
            unit.save()
            unit.product.update_quantities()
            
            # ✅ Queue unit status update
            if getattr(settings, 'OFFLINE_MODE', False):
                try:
                    SyncQueue.objects.create(
                        tenant_id=tenant.id,
                        model_name='ProductUnit',
                        object_id=str(unit.id),
                        operation='UPDATE',
                        data={
                            'id': unit.id,
                            'status': 'available',
                            'tenant_id': tenant.id,
                        },
                        priority=7
                    )
                    logger.debug(f"✅ Queued ProductUnit update for return: {unit.id}")
                except Exception as e:
                    logger.error(f"Failed to queue ProductUnit sync: {e}")
    
    # ✅ Queue return approval sync
    if getattr(settings, 'OFFLINE_MODE', False):
        try:
            SyncQueue.objects.create(
                tenant_id=tenant.id,
                model_name='Return',
                object_id=str(return_obj.id),
                operation='UPDATE',
                data={
                    'id': return_obj.id,
                    'status': 'approved',
                    'approved_by_id': request.user.id,
                    'approved_at': return_obj.approved_at.isoformat(),
                    'tenant_id': tenant.id,
                },
                priority=7
            )
            logger.debug(f"✅ Queued Return approval sync: #{return_obj.id}")
        except Exception as e:
            logger.error(f"Failed to queue Return sync: {e}")
    
    messages.success(request, f'Return for {return_obj.product.name} approved')
    return redirect('tech_master:return_detail', return_id=return_obj.id)


@login_required
def reject_return(request, return_id):
    """Reject a return with sync support"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    return_obj = get_object_or_404(Return, id=return_id, tenant=tenant)
    
    if return_obj.status != 'pending':
        messages.warning(request, 'This return is already processed')
        return redirect('tech_master:return_detail', return_id=return_obj.id)
    
    return_obj.status = 'rejected'
    return_obj.approved_by = request.user
    return_obj.approved_at = timezone.now()
    return_obj.save()
    
    # ✅ Queue return rejection sync
    if getattr(settings, 'OFFLINE_MODE', False):
        try:
            SyncQueue.objects.create(
                tenant_id=tenant.id,
                model_name='Return',
                object_id=str(return_obj.id),
                operation='UPDATE',
                data={
                    'id': return_obj.id,
                    'status': 'rejected',
                    'approved_by_id': request.user.id,
                    'approved_at': return_obj.approved_at.isoformat(),
                    'tenant_id': tenant.id,
                },
                priority=7
            )
            logger.debug(f"✅ Queued Return rejection sync: #{return_obj.id}")
        except Exception as e:
            logger.error(f"Failed to queue Return sync: {e}")
    
    messages.success(request, f'Return for {return_obj.product.name} rejected')
    return redirect('tech_master:return_detail', return_id=return_obj.id)