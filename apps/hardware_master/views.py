from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from decimal import Decimal
from django.utils import timezone
from .models import (
    HardwareCategory, HardwareProduct, HardwareSupplier,
    HardwareSale, HardwareSaleItem
)


@login_required
def dashboard(request):
    """Hardware Master Dashboard"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')
    
    # Get statistics
    total_products = HardwareProduct.objects.filter(tenant=tenant, is_active=True).count()
    total_categories = HardwareCategory.objects.filter(tenant=tenant, is_active=True).count()
    total_suppliers = HardwareSupplier.objects.filter(tenant=tenant, is_active=True).count()
    
    # Today's sales
    today = timezone.now().date()
    today_sales = HardwareSale.objects.filter(
        tenant=tenant,
        created_at__date=today,
        status='completed'
    ).aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')
    
    # Low stock products
    low_stock = HardwareProduct.objects.filter(
        tenant=tenant,
        is_active=True,
        quantity__lte=models.F('reorder_level') # pyright: ignore[reportUndefinedVariable]
    ).count()
    
    # Recent sales
    recent_sales = HardwareSale.objects.filter(
        tenant=tenant
    ).order_by('-created_at')[:10]
    
    context = {
        'tenant': tenant,
        'total_products': total_products,
        'total_categories': total_categories,
        'total_suppliers': total_suppliers,
        'today_sales': today_sales,
        'low_stock': low_stock,
        'recent_sales': recent_sales,
        'active_tab': 'dashboard',
        'project_type': 'HARDWARE_MASTER',
    }
    return render(request, 'hardware_master/dashboard.html', context)


@login_required
def category_list(request):
    """List hardware categories"""
    tenant = request.user.tenant
    
    categories = HardwareCategory.objects.filter(tenant=tenant).order_by('name')
    
    context = {
        'tenant': tenant,
        'categories': categories,
        'active_tab': 'categories',
    }
    return render(request, 'hardware_master/categories.html', context)


@login_required
def category_create(request):
    """Create a new category"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        
        if HardwareCategory.objects.filter(tenant=tenant, name=name).exists():
            messages.error(request, f'Category "{name}" already exists')
            return redirect('hardware_master:category_create')
        
        category = HardwareCategory.objects.create(
            tenant=tenant,
            name=name,
            description=description,
            is_active=True
        )
        messages.success(request, f'Category "{name}" created successfully!')
        return redirect('hardware_master:categories')
    
    context = {
        'tenant': tenant,
        'active_tab': 'categories',
    }
    return render(request, 'hardware_master/category_form.html', context)


@login_required
def product_list(request):
    """List hardware products"""
    tenant = request.user.tenant
    
    products = HardwareProduct.objects.filter(
        tenant=tenant
    ).select_related('category').order_by('name')
    
    # Filters
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
    
    search = request.GET.get('search')
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(sku__icontains=search) |
            Q(description__icontains=search)
        )
    
    context = {
        'tenant': tenant,
        'products': products,
        'categories': HardwareCategory.objects.filter(tenant=tenant, is_active=True),
        'active_tab': 'products',
    }
    return render(request, 'hardware_master/products.html', context)


@login_required
def product_create(request):
    """Create a new product"""
    tenant = request.user.tenant
    categories = HardwareCategory.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        sku = request.POST.get('sku')
        description = request.POST.get('description', '')
        unit = request.POST.get('unit', 'piece')
        unit_price = request.POST.get('unit_price', 0)
        cost_price = request.POST.get('cost_price', 0)
        quantity = request.POST.get('quantity', 0)
        reorder_level = request.POST.get('reorder_level', 10)
        location = request.POST.get('location', '')
        
        if not all([name, category_id, sku, unit_price]):
            messages.error(request, 'Please fill in all required fields')
            return redirect('hardware_master:product_create')
        
        if HardwareProduct.objects.filter(tenant=tenant, sku=sku).exists():
            messages.error(request, f'Product with SKU "{sku}" already exists')
            return redirect('hardware_master:product_create')
        
        category = get_object_or_404(HardwareCategory, id=category_id, tenant=tenant)
        
        product = HardwareProduct.objects.create(
            tenant=tenant,
            name=name,
            category=category,
            sku=sku,
            description=description,
            unit=unit,
            unit_price=unit_price,
            cost_price=cost_price,
            quantity=quantity,
            reorder_level=reorder_level,
            location=location,
            is_active=True
        )
        
        messages.success(request, f'Product "{name}" created successfully!')
        return redirect('hardware_master:products')
    
    context = {
        'tenant': tenant,
        'categories': categories,
        'active_tab': 'products',
    }
    return render(request, 'hardware_master/product_form.html', context)


@login_required
def sale_list(request):
    """List hardware sales"""
    tenant = request.user.tenant
    
    sales = HardwareSale.objects.filter(
        tenant=tenant
    ).order_by('-created_at')
    
    context = {
        'tenant': tenant,
        'sales': sales,
        'active_tab': 'sales',
    }
    return render(request, 'hardware_master/sales.html', context)


@login_required
def sale_create(request):
    """Create a new sale"""
    tenant = request.user.tenant
    products = HardwareProduct.objects.filter(tenant=tenant, is_active=True, quantity__gt=0)
    
    if request.method == 'POST':
        customer_name = request.POST.get('customer_name')
        customer_phone = request.POST.get('customer_phone')
        payment_method = request.POST.get('payment_method', 'cash')
        product_ids = request.POST.getlist('product_ids')
        quantities = request.POST.getlist('quantities')
        
        if not customer_name:
            messages.error(request, 'Customer name is required')
            return redirect('hardware_master:sale_create')
        
        if not product_ids:
            messages.error(request, 'Please select at least one product')
            return redirect('hardware_master:sale_create')
        
        # Generate invoice number
        today = timezone.now().strftime('%Y%m%d')
        last_sale = HardwareSale.objects.filter(
            tenant=tenant,
            invoice_number__startswith=f'HW-{today}'
        ).order_by('-invoice_number').first()
        
        if last_sale:
            last_number = int(last_sale.invoice_number.split('-')[-1])
            invoice_number = f'HW-{today}-{last_number + 1:04d}'
        else:
            invoice_number = f'HW-{today}-0001'
        
        sale = HardwareSale.objects.create(
            tenant=tenant,
            invoice_number=invoice_number,
            customer_name=customer_name,
            customer_phone=customer_phone,
            payment_method=payment_method,
            status='completed',
            created_by=request.user
        )
        
        total_amount = Decimal('0.00')
        
        for product_id, quantity in zip(product_ids, quantities):
            if product_id and int(quantity) > 0:
                product = get_object_or_404(HardwareProduct, id=product_id, tenant=tenant)
                quantity = int(quantity)
                
                if product.quantity < quantity:
                    messages.error(request, f'Insufficient stock for {product.name}')
                    sale.delete()
                    return redirect('hardware_master:sale_create')
                
                total_price = product.unit_price * quantity
                total_amount += total_price
                
                HardwareSaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=quantity,
                    unit_price=product.unit_price,
                    total_price=total_price
                )
                
                # Update stock
                product.quantity -= quantity
                product.save()
        
        sale.total_amount = total_amount
        sale.net_amount = total_amount
        sale.save()
        
        messages.success(request, f'Sale #{invoice_number} created successfully!')
        return redirect('hardware_master:sale_detail', sale_id=sale.id)
    
    context = {
        'tenant': tenant,
        'products': products,
        'active_tab': 'sales',
    }
    return render(request, 'hardware_master/sale_form.html', context)


@login_required
def sale_detail(request, sale_id):
    """View sale details"""
    tenant = request.user.tenant
    sale = get_object_or_404(HardwareSale, id=sale_id, tenant=tenant)
    items = sale.items.all().select_related('product')
    
    context = {
        'tenant': tenant,
        'sale': sale,
        'items': items,
        'active_tab': 'sales',
    }
    return render(request, 'hardware_master/sale_detail.html', context)