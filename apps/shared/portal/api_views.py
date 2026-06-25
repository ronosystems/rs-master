# apps/shared/portal/api_views.py

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils import timezone
import json

from apps.tech_master.inventory.models import Product, ProductUnit
from apps.shared.customers.models import Customer
from apps.tech_master.sales.models import Sale, SaleItem


# ============================================
# SEARCH PRODUCT
# ============================================

@login_required
def search_product(request):
    """Search products by name, SKU, IMEI, or serial number"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    query = request.GET.get('q', '').strip()
    results = []
    
    # Search Products (only show products with stock > 0)
    products = Product.objects.filter(
        tenant=tenant,
        is_active=True,
        available_quantity__gt=0
    )
    
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(model__icontains=query) |
            Q(sku_code__icontains=query) |
            Q(barcode__icontains=query)
        )
    
    products = products[:20]
    
    for product in products:
        # ✅ Check if product is single item or bulk
        is_single = product.category.is_single_item if product.category else False
        
        results.append({
            'id': product.id,
            'type': 'product',
            'name': product.name,
            'sku': product.sku_code,
            'barcode': product.barcode or '',
            'price': float(product.selling_price),
            'buying_price': float(product.buying_price),
            'stock': product.available_quantity,
            'identifier': product.sku_code,
            'has_stock': product.available_quantity > 0,
            'is_single': is_single,  # ✅ Flag for frontend
        })
    
    # Search Product Units (IMEI/Serial) - Single items only
    if query and len(query) >= 3:
        units = ProductUnit.objects.filter(
            tenant=tenant,
            status='available'
        ).filter(
            Q(imei_number__icontains=query) |
            Q(serial_number__icontains=query)
        ).select_related('product', 'product__category')[:20]
        
        for unit in units:
            price = unit.unit_selling_price or unit.product.selling_price
            results.append({
                'id': unit.id,
                'type': 'unit',
                'name': unit.product.name,
                'sku': unit.product.sku_code,
                'imei': unit.imei_number or '',
                'serial': unit.serial_number or '',
                'price': float(price),
                'buying_price': float(unit.unit_buying_price or unit.product.buying_price),
                'identifier': unit.imei_number or unit.serial_number,
                'product_id': unit.product.id,
                'stock': 1,
                'has_stock': True,
                'is_single': True,  # ✅ Units are always single items
            })
    
    return JsonResponse({'results': results})


@login_required
def get_product_units(request):
    """Get available units for a product (single items)"""
    tenant = request.user.tenant
    product_id = request.GET.get('product_id')
    
    if not tenant or not product_id:
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    units = ProductUnit.objects.filter(
        tenant=tenant,
        product_id=product_id,
        status='available'
    ).select_related('product')
    
    unit_list = []
    for unit in units:
        price = unit.unit_selling_price or unit.product.selling_price
        unit_list.append({
            'id': unit.id,
            'identifier': unit.imei_number or unit.serial_number,
            'price': float(price),
            'condition': unit.get_condition_display(),
        })
    
    return JsonResponse({'units': unit_list})



# ============================================
# CART FUNCTIONS
# ============================================

@login_required
def get_cart(request):
    """Get current user's cart from session"""
    cart = request.session.get('pos_cart', [])
    
    subtotal = 0
    total = 0
    
    for item in cart:
        price = float(item.get('price', 0))
        quantity = int(item.get('quantity', 0))
        subtotal += price * quantity
    
    total = subtotal
    
    return JsonResponse({
        'success': True,
        'cart': cart,
        'subtotal': subtotal,
        'total': total,
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def add_to_cart(request):
    """Add item to cart - Units go as separate rows, Bulk products accumulate"""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        item_type = data.get('type', 'product')
        quantity = int(data.get('quantity', 1))
    except:
        return JsonResponse({'error': 'Invalid data'}, status=400)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    cart = request.session.get('pos_cart', [])
    
    # ✅ Check if item already in cart
    for item in cart:
        if item.get('id') == item_id and item.get('type') == item_type:
            # ✅ Only accumulate if it's a BULK product (not single/unit)
            is_single = item.get('is_single', False)
            
            if is_single:
                # ✅ SINGLE ITEMS - Add as new row (don't accumulate)
                # Check if this specific unit is already in cart
                # Units are identified by ID, so they won't match here anyway
                pass
            else:
                # ✅ BULK ITEMS - Accumulate quantity
                new_quantity = item['quantity'] + quantity
                max_stock = item.get('stock', 999)
                
                if new_quantity > max_stock:
                    return JsonResponse({
                        'error': f'Only {max_stock} units available. You already have {item["quantity"]} in cart.',
                        'max_stock': max_stock,
                        'current_cart': item['quantity']
                    }, status=400)
                
                item['quantity'] = new_quantity
                request.session['pos_cart'] = cart
                return get_cart(request)
    
    # ✅ Get item details with stock validation
    item_data = None
    is_single = False
    
    if item_type == 'product':
        product = Product.objects.filter(id=item_id, tenant=tenant).first()
        if product:
            # ✅ Check if product is single or bulk
            is_single = product.category.is_single_item if product.category else False
            
            # ✅ Validate stock for bulk items
            if not is_single and product.available_quantity < quantity:
                return JsonResponse({
                    'error': f'Only {product.available_quantity} units available in stock.',
                    'available_stock': product.available_quantity
                }, status=400)
            
            # ✅ For single items, only allow quantity 1
            if is_single and quantity > 1:
                # Check if there are enough available units
                available_units = ProductUnit.objects.filter(
                    product=product,
                    tenant=tenant,
                    status='available'
                ).count()
                
                if available_units < quantity:
                    return JsonResponse({
                        'error': f'Only {available_units} units available for this product.',
                        'available_units': available_units
                    }, status=400)
                
                # For single items, we'll add each unit separately
                # But for now, just add one with quantity 1
                quantity = 1
            
            item_data = {
                'id': product.id,
                'type': 'product',
                'name': product.name,
                'sku': product.sku_code,
                'price': float(product.selling_price),
                'quantity': quantity,
                'identifier': product.sku_code,
                'stock': product.available_quantity,
                'has_stock': product.available_quantity > 0,
                'is_single': is_single,
                'category': product.category.name if product.category else 'Uncategorized',
            }
    
    elif item_type == 'unit':
        unit = ProductUnit.objects.filter(id=item_id, tenant=tenant, status='available').first()
        if unit:
            price = unit.unit_selling_price or unit.product.selling_price
            is_single = True  # ✅ Units are always single items
            
            # ✅ Check if this exact unit is already in cart
            existing_unit = next((item for item in cart if item.get('id') == item_id and item.get('type') == 'unit'), None)
            if existing_unit:
                return JsonResponse({
                    'error': f'This unit ({unit.imei_number or unit.serial_number}) is already in the cart.',
                    'unit_identifier': unit.imei_number or unit.serial_number
                }, status=400)
            
            item_data = {
                'id': unit.id,
                'type': 'unit',
                'name': unit.product.name,
                'sku': unit.product.sku_code,
                'imei': unit.imei_number or '',
                'serial': unit.serial_number or '',
                'price': float(price),
                'quantity': 1,  # ✅ Units always quantity 1
                'identifier': unit.imei_number or unit.serial_number,
                'product_id': unit.product.id,
                'stock': 1,
                'has_stock': True,
                'is_single': True,
                'category': unit.product.category.name if unit.product.category else 'Uncategorized',
            }
    
    if not item_data:
        return JsonResponse({'error': 'Item not found'}, status=404)
    
    cart.append(item_data)
    request.session['pos_cart'] = cart
    
    return get_cart(request)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_cart(request):
    """Update cart item quantity - Only for bulk products"""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        item_type = data.get('type', 'product')
        quantity = int(data.get('quantity', 1))
    except:
        return JsonResponse({'error': 'Invalid data'}, status=400)
    
    cart = request.session.get('pos_cart', [])
    
    for item in cart:
        if item.get('id') == item_id and item.get('type') == item_type:
            is_single = item.get('is_single', False)
            
            # ✅ Prevent quantity change for single items
            if is_single:
                return JsonResponse({
                    'error': 'Quantity cannot be changed for single items (IMEI/Serial based).',
                    'is_single': True
                }, status=400)
            
            # ✅ Validate stock before updating bulk quantity
            max_stock = item.get('stock', 999)
            if quantity > max_stock:
                return JsonResponse({
                    'error': f'Only {max_stock} units available in stock.',
                    'max_stock': max_stock
                }, status=400)
            
            item['quantity'] = max(1, quantity)
            break
    
    request.session['pos_cart'] = cart
    return get_cart(request)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_cart_price(request):
    """Update cart item custom price"""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        item_type = data.get('type', 'product')
        price = float(data.get('price', 0))
    except:
        return JsonResponse({'error': 'Invalid data'}, status=400)
    
    if price < 0:
        return JsonResponse({'error': 'Price cannot be negative'}, status=400)
    
    cart = request.session.get('pos_cart', [])
    
    for item in cart:
        if item.get('id') == item_id and item.get('type') == item_type:
            item['price'] = price
            break
    
    request.session['pos_cart'] = cart
    return get_cart(request)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def remove_from_cart(request):
    """Remove item from cart"""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        item_type = data.get('type', 'product')
    except:
        return JsonResponse({'error': 'Invalid data'}, status=400)
    
    cart = request.session.get('pos_cart', [])
    
    cart = [item for item in cart if not (item.get('id') == item_id and item.get('type') == item_type)]
    
    request.session['pos_cart'] = cart
    
    return get_cart(request)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def clear_cart(request):
    """Clear cart"""
    request.session['pos_cart'] = []
    return get_cart(request)


# ============================================
# CUSTOMER FUNCTIONS
# ============================================

@login_required
def search_customer(request):
    """Search customer by phone"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    phone = request.GET.get('phone', '').strip()
    
    if not phone:
        return JsonResponse({'error': 'Phone number required'}, status=400)
    
    customer = Customer.objects.filter(tenant=tenant, phone=phone).first()
    
    if customer:
        return JsonResponse({
            'success': True,
            'found': True,
            'id': customer.id,
            'name': customer.name,
            'phone': customer.phone,
            'email': customer.email or '',
        })
    else:
        return JsonResponse({
            'success': True,
            'found': False,
        })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def add_customer(request):
    """Add new customer"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    name = request.POST.get('name', '').strip()
    phone = request.POST.get('phone', '').strip()
    email = request.POST.get('email', '').strip()
    
    if not name or not phone:
        return JsonResponse({'error': 'Name and phone are required'}, status=400)
    
    if Customer.objects.filter(tenant=tenant, phone=phone).exists():
        return JsonResponse({'error': 'Customer with this phone already exists'}, status=400)
    
    customer = Customer.objects.create(
        tenant=tenant,
        name=name,
        phone=phone,
        email=email,
        created_by=request.user
    )
    
    return JsonResponse({
        'success': True,
        'id': customer.id,
        'name': customer.name,
        'phone': customer.phone,
    })


# ============================================
# PAYMENT PROCESSING
# ============================================

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def process_payment(request):
    """Process payment and create sale with stock validation"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    try:
        data = json.loads(request.body)
        payment_method = data.get('payment_method', 'cash')
        amount_paid = float(data.get('amount_paid', 0))
        customer_id = data.get('customer_id')
    except:
        return JsonResponse({'error': 'Invalid data'}, status=400)
    
    cart = request.session.get('pos_cart', [])
    
    if not cart:
        return JsonResponse({'error': 'Cart is empty'}, status=400)
    
    # ✅ Validate stock before creating sale
    stock_errors = []
    for item in cart:
        is_single = item.get('is_single', False)
        
        if item.get('type') == 'product' and not is_single:
            # Bulk product validation
            product = Product.objects.filter(id=item.get('id'), tenant=tenant).first()
            if not product:
                stock_errors.append(f"Product '{item.get('name')}' not found")
            elif product.available_quantity < item.get('quantity'):
                stock_errors.append(
                    f"Not enough stock for '{product.name}'. "
                    f"Available: {product.available_quantity}, Requested: {item.get('quantity')}"
                )
        elif item.get('type') == 'unit' or is_single:
            # Unit/Single item validation
            unit = ProductUnit.objects.filter(id=item.get('id'), tenant=tenant).first()
            if not unit:
                stock_errors.append(f"Unit '{item.get('identifier')}' is no longer available")
            elif unit.status != 'available':
                stock_errors.append(f"Unit '{item.get('identifier')}' is no longer available (Status: {unit.status})")
    
    if stock_errors:
        return JsonResponse({
            'error': 'Stock validation failed',
            'details': stock_errors[:5]
        }, status=400)
    
    # Calculate total
    total = 0
    for item in cart:
        total += float(item.get('price', 0)) * int(item.get('quantity', 0))
    
    if amount_paid < total:
        return JsonResponse({'error': f'Insufficient payment. Total: {total}, Paid: {amount_paid}'}, status=400)
    
    # Get customer
    customer = None
    if customer_id:
        customer = Customer.objects.filter(id=customer_id, tenant=tenant).first()
    
    # ✅ Create sale
    sale = Sale.objects.create(
        tenant=tenant,
        customer=customer,
        customer_name=customer.name if customer else 'Walk-in',
        customer_phone=customer.phone if customer else '',
        cashier=request.user,
        subtotal=total,
        total=total,
        payment_method=payment_method,
        status='completed',
        tax_inclusive=True,
        invoice_no=f"INV-{timezone.now().strftime('%Y%m%d')}-{Sale.objects.filter(tenant=tenant).count() + 1:04d}"
    )
    
    # ✅ Create sale items and update stock
    sold_items = []
    for item in cart:
        product = None
        product_unit = None
        is_single = item.get('is_single', False)
        
        if item.get('type') == 'product' and not is_single:
            # Bulk product
            product = Product.objects.filter(id=item.get('id'), tenant=tenant).first()
            if product:
                # Update product stock
                product.available_quantity -= item.get('quantity')
                product.save()
                
        elif item.get('type') == 'unit' or is_single:
            # Unit/Single item
            product_unit = ProductUnit.objects.filter(id=item.get('id'), tenant=tenant).first()
            if product_unit:
                product = product_unit.product
                # Mark unit as sold
                product_unit.status = 'sold'
                product_unit.sold_at_price = float(item.get('price'))
                product_unit.sold_date = timezone.now()
                product_unit.sold_by = request.user
                product_unit.save()
                # Update product quantities
                product.update_quantities()
        
        if product:
            SaleItem.objects.create(
                sale=sale,
                product=product,
                product_unit=product_unit,
                quantity=int(item.get('quantity', 1)),
                price=float(item.get('price', 0)),
                subtotal=float(item.get('price', 0)) * int(item.get('quantity', 1))
            )
            sold_items.append({
                'name': product.name,
                'identifier': item.get('identifier', product.sku_code),
                'quantity': item.get('quantity'),
                'price': float(item.get('price', 0)),
                'is_single': is_single,
            })
    
    # ✅ Update customer total spent
    if customer:
        customer.total_spent = (customer.total_spent or 0) + total
        customer.save()
    
    # Clear cart
    request.session['pos_cart'] = []
    
    return JsonResponse({
        'success': True,
        'sale_id': sale.id,
        'receipt_number': sale.invoice_no,
        'total': total,
        'amount_paid': amount_paid,
        'change': amount_paid - total,
        'items_sold': sold_items,
    })