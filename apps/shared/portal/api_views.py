# apps/shared/portal/api_views.py

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils import timezone
import json
from decimal import Decimal
import logging

from apps.tronic_master.models import Product, ProductUnit, Sale, SaleItem
from apps.shared.customers.models import Customer
from .helpers import get_user_branch

logger = logging.getLogger(__name__)


# ============================================
# SEARCH PRODUCT - FIXED FOR YOUR MODELS
# ============================================

@login_required
def search_product(request):
    """Search products by name, SKU, IMEI, or serial number"""
    try:
        tenant = request.user.tenant
        
        if not tenant:
            return JsonResponse({'error': 'No tenant assigned'}, status=400)
        
        # Get user's branch
        user_branch = get_user_branch(request.user)
        
        # Get query parameter
        query = request.GET.get('q', '').strip()
        
        # Remove problematic characters
        if query:
            query = query.replace(':', '').replace(';', '').replace('(', '').replace(')', '')
        
        logger.info(f"Search products - Tenant: {tenant.id}, Query: '{query}', Branch: {user_branch}")
        
        results = []
        
        # Search Products
        products = Product.objects.filter(
            tenant=tenant,
            is_active=True
        ).select_related('category', 'branch')
        
        # Filter by branch if user has one
        if user_branch:
            products = products.filter(
                Q(branch=user_branch) | Q(branch__isnull=True)
            )
        
        # Apply search filter
        if query:
            products = products.filter(
                Q(name__icontains=query) |
                Q(brand__icontains=query) |
                Q(model__icontains=query) |
                Q(sku_code__icontains=query)
            )
        
        # Limit results
        products = products[:20]
        
        for product in products:
            try:
                # Check if category is single item type
                is_single = product.category.is_single_item if product.category else False
                
                # Get available units for single items
                units_count = 0
                if is_single:
                    units_qs = ProductUnit.objects.filter(
                        product=product,
                        tenant=tenant,
                        status='available'
                    )
                    if user_branch:
                        units_qs = units_qs.filter(branch=user_branch)
                    units_count = units_qs.count()
                
                # For bulk items, use available_quantity
                available_stock = units_count if is_single else product.available_quantity
                
                results.append({
                    'id': product.id,
                    'type': 'product',
                    'name': product.name or f"{product.brand} {product.model}",
                    'sku': product.sku_code,
                    'barcode': '',  # Not in your Product model
                    'price': float(product.default_selling_price),
                    'buying_price': float(product.default_buying_price),
                    'stock': available_stock,
                    'identifier': product.sku_code,
                    'has_stock': available_stock > 0,
                    'is_single': is_single,
                    'branch': product.branch.name if product.branch else None,
                    'category': product.category.name if product.category else 'Uncategorized',
                })
            except Exception as e:
                logger.error(f"Error processing product {product.id}: {e}")
                continue
        
        # Search Product Units (IMEI/Serial)
        if query and len(query) >= 3:
            units = ProductUnit.objects.filter(
                tenant=tenant,
                status='available'
            ).select_related('product', 'branch', 'product__category')
            
            # Filter by branch
            if user_branch:
                units = units.filter(branch=user_branch)
            
            # Search by IMEI or Serial
            units = units.filter(
                Q(imei_number__icontains=query) |
                Q(serial_number__icontains=query)
            )
            
            units = units[:20]
            
            for unit in units:
                try:
                    price = unit.unit_selling_price or unit.product.default_selling_price
                    results.append({
                        'id': unit.id,
                        'type': 'unit',
                        'name': unit.product.name or f"{unit.product.brand} {unit.product.model}",
                        'sku': unit.product.sku_code,
                        'imei': unit.imei_number or '',
                        'serial': unit.serial_number or '',
                        'price': float(price),
                        'buying_price': float(unit.unit_buying_price or unit.product.default_buying_price),
                        'identifier': unit.imei_number or unit.serial_number or unit.product.sku_code,
                        'product_id': unit.product.id,
                        'stock': 1,
                        'has_stock': True,
                        'is_single': True,
                        'branch': unit.branch.name if unit.branch else None,
                        'category': unit.product.category.name if unit.product.category else 'Uncategorized',
                    })
                except Exception as e:
                    logger.error(f"Error processing unit {unit.id}: {e}")
                    continue
        
        return JsonResponse({
            'success': True,
            'results': results,
            'user_branch': user_branch.name if user_branch else None,
            'query': query,
            'count': len(results)
        })
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        logger.error(f"ERROR in search_product: {error_msg}")
        logger.error(traceback_str)
        
        return JsonResponse({
            'success': False,
            'error': error_msg,
            'traceback': traceback_str
        }, status=500)


# ============================================
# GET PRODUCT UNITS - FIXED
# ============================================

@login_required
def get_product_units(request):
    """Get available units for a product (single items)"""
    try:
        tenant = request.user.tenant
        product_id = request.GET.get('product_id')
        
        if not tenant:
            return JsonResponse({'error': 'No tenant assigned'}, status=400)
        
        if not product_id:
            return JsonResponse({'error': 'Product ID required'}, status=400)
        
        # Get user's branch
        user_branch = get_user_branch(request.user)
        
        units = ProductUnit.objects.filter(
            tenant=tenant,
            product_id=product_id,
            status='available'
        ).select_related('product', 'branch')
        
        # Filter units by user's branch
        if user_branch:
            units = units.filter(branch=user_branch)
        
        unit_list = []
        for unit in units:
            price = unit.unit_selling_price or unit.product.default_selling_price
            unit_list.append({
                'id': unit.id,
                'identifier': unit.imei_number or unit.serial_number or unit.product.sku_code,
                'price': float(price),
                'condition': unit.get_condition_display() if hasattr(unit, 'get_condition_display') else 'New',
                'branch': unit.branch.name if unit.branch else None,
                'imei': unit.imei_number or '',
                'serial': unit.serial_number or '',
            })
        
        return JsonResponse({
            'success': True,
            'units': unit_list,
            'user_branch': user_branch.name if user_branch else None,
            'count': len(unit_list)
        })
        
    except Exception as e:
        logger.error(f"Error in get_product_units: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================
# CART FUNCTIONS - Keep these as they are
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
    """Add item to cart"""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        item_type = data.get('type', 'product')
        quantity = int(data.get('quantity', 1))
    except Exception as e:
        return JsonResponse({'error': f'Invalid data: {str(e)}'}, status=400)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    user_branch = get_user_branch(request.user)
    cart = request.session.get('pos_cart', [])
    
    # Check if item already in cart
    for item in cart:
        if item.get('id') == item_id and item.get('type') == item_type:
            is_single = item.get('is_single', False)
            
            if is_single:
                # Single items don't accumulate
                pass
            else:
                # Bulk items accumulate
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
    
    # Get item details
    item_data = None
    
    if item_type == 'product':
        product = Product.objects.filter(id=item_id, tenant=tenant).first()
        if product:
            is_single = product.category.is_single_item if product.category else False
            
            if user_branch and product.branch and product.branch.id != user_branch.id:
                return JsonResponse({
                    'error': f'This product belongs to branch "{product.branch.name}". You are assigned to "{user_branch.name}".'
                }, status=403)
            
            if not is_single and product.available_quantity < quantity:
                return JsonResponse({
                    'error': f'Only {product.available_quantity} units available in stock.',
                    'available_stock': product.available_quantity
                }, status=400)
            
            if is_single:
                available_units = ProductUnit.objects.filter(
                    product=product,
                    tenant=tenant,
                    status='available'
                )
                if user_branch:
                    available_units = available_units.filter(branch=user_branch)
                available_count = available_units.count()
                
                if available_count < quantity:
                    return JsonResponse({
                        'error': f'Only {available_count} units available in your branch.',
                        'available_units': available_count
                    }, status=400)
                
                quantity = 1
            
            item_data = {
                'id': product.id,
                'type': 'product',
                'name': product.name or f"{product.brand} {product.model}",
                'sku': product.sku_code,
                'price': float(product.default_selling_price),
                'quantity': quantity,
                'identifier': product.sku_code,
                'stock': product.available_quantity,
                'has_stock': product.available_quantity > 0,
                'is_single': is_single,
                'category': product.category.name if product.category else 'Uncategorized',
                'branch': product.branch.name if product.branch else None,
            }
    
    elif item_type == 'unit':
        unit = ProductUnit.objects.filter(id=item_id, tenant=tenant, status='available').first()
        if unit:
            if user_branch and unit.branch and unit.branch.id != user_branch.id:
                return JsonResponse({
                    'error': f'This unit belongs to branch "{unit.branch.name}". You are assigned to "{user_branch.name}".'
                }, status=403)
            
            price = unit.unit_selling_price or unit.product.default_selling_price
            
            existing_unit = next((item for item in cart if item.get('id') == item_id and item.get('type') == 'unit'), None)
            if existing_unit:
                return JsonResponse({
                    'error': f'This unit ({unit.imei_number or unit.serial_number}) is already in the cart.'
                }, status=400)
            
            item_data = {
                'id': unit.id,
                'type': 'unit',
                'name': unit.product.name or f"{unit.product.brand} {unit.product.model}",
                'sku': unit.product.sku_code,
                'imei': unit.imei_number or '',
                'serial': unit.serial_number or '',
                'price': float(price),
                'quantity': 1,
                'identifier': unit.imei_number or unit.serial_number or unit.product.sku_code,
                'product_id': unit.product.id,
                'stock': 1,
                'has_stock': True,
                'is_single': True,
                'category': unit.product.category.name if unit.product.category else 'Uncategorized',
                'branch': unit.branch.name if unit.branch else None,
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
            
            if is_single:
                return JsonResponse({
                    'error': 'Quantity cannot be changed for single items (IMEI/Serial based).',
                    'is_single': True
                }, status=400)
            
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
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'full_name': customer.name,
                'customer_name': customer.name,
                'phone': customer.phone,
                'phone_number': customer.phone,
                'email': customer.email or '',
            }
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
    """Add new customer - Accepts both JSON and FormData"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    if request.content_type and 'application/json' in request.content_type:
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            phone = data.get('phone', '').strip()
            email = data.get('email', '').strip()
        except:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    else:
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
        email=email or '',
        created_by=request.user
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Customer added successfully',
        'customer': {
            'id': customer.id,
            'name': customer.name,
            'phone': customer.phone,
            'email': customer.email or '',
        }
    })


# ============================================
# SEARCH PAYMENTS
# ============================================

@login_required
def search_payments(request):
    """Search payments by transaction ID, phone, or date"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    txn_id = request.GET.get('txn_id', '').strip()
    phone = request.GET.get('phone', '').strip()
    date = request.GET.get('date', '').strip()
    
    payments = Sale.objects.filter(tenant=tenant)
    
    if txn_id:
        payments = payments.filter(invoice_no__icontains=txn_id)
    if phone:
        payments = payments.filter(customer_phone__icontains=phone)
    if date:
        payments = payments.filter(created_at__date=date)
    
    payments = payments.order_by('-created_at')[:20]
    
    results = []
    for payment in payments:
        results.append({
            'txn_id': payment.invoice_no,
            'amount': float(payment.total),
            'phone': payment.customer_phone or '',
            'status': 'completed' if payment.status == 'completed' else payment.status,
            'date': payment.created_at.strftime('%Y-%m-%d %H:%M'),
            'payment_method': payment.payment_method,
        })
    
    return JsonResponse({
        'success': True,
        'payments': results,
        'count': len(results)
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
    
    # ✅ Get user's branch
    user_branch = get_user_branch(request.user)
    
    cart = request.session.get('pos_cart', [])
    
    if not cart:
        return JsonResponse({'error': 'Cart is empty'}, status=400)
    
    # ✅ Validate stock before creating sale
    stock_errors = []
    for item in cart:
        is_single = item.get('is_single', False)
        
        if item.get('type') == 'product' and not is_single:
            product = Product.objects.filter(id=item.get('id'), tenant=tenant).first()
            if not product:
                stock_errors.append(f"Product '{item.get('name')}' not found")
            elif product.available_quantity < item.get('quantity'):
                stock_errors.append(
                    f"Not enough stock for '{product.name}'. "
                    f"Available: {product.available_quantity}, Requested: {item.get('quantity')}"
                )
        elif item.get('type') == 'unit' or is_single:
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
    
    # ✅ Create sale with user's branch
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
        branch=user_branch,  # ✅ Set branch from user
        invoice_no=f"INV-{timezone.now().strftime('%Y%m%d')}-{Sale.objects.filter(tenant=tenant).count() + 1:04d}"
    )
    
    # ✅ Create sale items and update stock
    sold_items = []
    for item in cart:
        product = None
        product_unit = None
        is_single = item.get('is_single', False)
        
        if item.get('type') == 'product' and not is_single:
            product = Product.objects.filter(id=item.get('id'), tenant=tenant).first()
            if product:
                product.available_quantity -= item.get('quantity')
                product.save()
                
        elif item.get('type') == 'unit' or is_single:
            product_unit = ProductUnit.objects.filter(id=item.get('id'), tenant=tenant).first()
            if product_unit:
                product = product_unit.product
                product_unit.status = 'sold'
                product_unit.sold_at_price = float(item.get('price'))
                product_unit.sold_date = timezone.now()
                product_unit.sold_by = request.user
                product_unit.save()
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
    
    # Update customer total spent
    if customer:
        customer.total_spent = (customer.total_spent or Decimal('0')) + Decimal(str(total))
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
        'branch': user_branch.name if user_branch else None,
    })