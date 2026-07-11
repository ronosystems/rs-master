# apps/fashion_master/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from django.utils import timezone
from decimal import Decimal

from .models import (
    FashionCategory, FashionProduct, FashionVariant,
    FashionSale, FashionSaleItem, FashionInventoryMovement,
    FashionReturn
)
from apps.tech_master.models import Branch, Supplier


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import json

from .models import (
    FashionCategory, FashionProduct, FashionVariant,
    FashionSale, FashionSaleItem, FashionInventoryMovement,
    FashionReturn
)
from apps.tech_master.models import Branch, Supplier
from apps.shared.customers.models import Customer
from django.contrib.auth import get_user_model



User = get_user_model()






# ============================================
# BRANCH MANAGEMENT VIEWS
# ============================================

@login_required
def branch_list(request):
    """List all fashion branches"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    branches = Branch.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    context = {
        'tenant': tenant,
        'branches': branches,
        'active_tab': 'branches',
    }
    return render(request, 'fashion_master/branch_list.html', context)


@login_required
def add_branch(request):
    """Add a new fashion branch"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        address = request.POST.get('address')
        city = request.POST.get('city')
        phone = request.POST.get('phone')
        branch_type = request.POST.get('branch_type', 'sub_branch')
        is_main_branch = request.POST.get('is_main_branch') == 'on'
        
        if not name or not code:
            messages.error(request, 'Branch name and code are required')
            return redirect('fashion_master:add_branch')
        
        if Branch.objects.filter(tenant=tenant, code=code).exists():
            messages.error(request, f'Branch code "{code}" already exists')
            return redirect('fashion_master:add_branch')
        
        branch = Branch.objects.create(
            tenant=tenant,
            name=name,
            code=code.upper(),
            address=address,
            city=city,
            phone=phone,
            branch_type=branch_type,
            is_main_branch=is_main_branch,
            is_active=True
        )
        
        messages.success(request, f'Branch "{branch.name}" created successfully!')
        return redirect('fashion_master:branch_list')
    
    context = {
        'tenant': tenant,
        'active_tab': 'branches',
    }
    return render(request, 'fashion_master/add_branch.html', context)


@login_required
def edit_branch(request, branch_id):
    """Edit an existing fashion branch"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        address = request.POST.get('address')
        city = request.POST.get('city')
        phone = request.POST.get('phone')
        branch_type = request.POST.get('branch_type', branch.branch_type)
        is_active = request.POST.get('is_active') == 'on'
        is_main_branch = request.POST.get('is_main_branch') == 'on'
        
        if not name or not code:
            messages.error(request, 'Branch name and code are required')
            return redirect('fashion_master:edit_branch', branch_id=branch.id)
        
        if Branch.objects.filter(tenant=tenant, code=code).exclude(id=branch.id).exists():
            messages.error(request, f'Branch code "{code}" already exists')
            return redirect('fashion_master:edit_branch', branch_id=branch.id)
        
        branch.name = name
        branch.code = code.upper()
        branch.address = address
        branch.city = city
        branch.phone = phone
        branch.branch_type = branch_type
        branch.is_active = is_active
        branch.is_main_branch = is_main_branch
        branch.save()
        
        messages.success(request, f'Branch "{branch.name}" updated successfully!')
        return redirect('fashion_master:branch_list')
    
    context = {
        'tenant': tenant,
        'branch': branch,
        'active_tab': 'branches',
    }
    return render(request, 'fashion_master/edit_branch.html', context)


@login_required
def branch_stock_detail(request, branch_id):
    """View detailed stock for a specific fashion branch"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
    
    # Get fashion products in this branch
    products = FashionProduct.objects.filter(
        tenant=tenant,
        branch=branch,
        is_active=True
    ).order_by('name')
    
    # Calculate totals
    total_products = products.count()
    total_stock = products.aggregate(total=Sum('quantity_in_stock'))['total'] or 0
    total_value = products.aggregate(
        total=Sum(F('quantity_in_stock') * F('buying_price'))
    )['total'] or Decimal('0.00')
    
    context = {
        'tenant': tenant,
        'branch': branch,
        'products': products,
        'total_products': total_products,
        'total_stock': total_stock,
        'total_value': total_value,
        'active_tab': 'branches',
    }
    return render(request, 'fashion_master/branch_stock_detail.html', context)


@login_required
def delete_branch(request, branch_id):
    """Delete a fashion branch"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
    
    if request.method == 'POST':
        branch_name = branch.name
        branch.delete()
        messages.success(request, f'Branch "{branch_name}" deleted successfully!')
        return redirect('fashion_master:branch_list')
    
    context = {
        'tenant': tenant,
        'branch': branch,
        'active_tab': 'branches',
    }
    return render(request, 'fashion_master/delete_branch.html', context)


@login_required
def assign_branch_manager(request):
    """Assign a manager to a fashion branch"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    branches = Branch.objects.filter(tenant=tenant, is_active=True).order_by('name')
    users = User.objects.filter(tenant=tenant, is_active=True).order_by('username')
    
    if request.method == 'POST':
        branch_id = request.POST.get('branch_id')
        user_id = request.POST.get('user_id')
        action = request.POST.get('action', 'assign')
        
        if not branch_id:
            messages.error(request, 'Please select a branch')
            return redirect('fashion_master:assign_branch_manager')
        
        branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
        
        if action == 'assign':
            if not user_id:
                messages.error(request, 'Please select a user to assign')
                return redirect('fashion_master:assign_branch_manager')
            
            user = get_object_or_404(User, id=user_id, tenant=tenant)
            branch.manager_name = user.get_full_name() or user.username
            branch.save()
            messages.success(request, f'Branch "{branch.name}" assigned to {user.get_full_name() or user.username}!')
            
        elif action == 'remove':
            branch.manager_name = ''
            branch.save()
            messages.success(request, f'Manager removed from "{branch.name}"!')
        
        return redirect('fashion_master:assign_branch_manager')
    
    branch_managers = {}
    for branch in branches:
        branch_managers[branch.id] = branch.manager_name or 'Not Assigned'
    
    context = {
        'tenant': tenant,
        'branches': branches,
        'users': users,
        'branch_managers': branch_managers,
        'active_tab': 'branches',
    }
    return render(request, 'fashion_master/assign_branch_manager.html', context)


@login_required
def branch_stock_list(request):
    """View stock levels by fashion branch"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    branch_stock_data = []
    for branch in branches:
        # Get fashion products in this branch
        products = FashionProduct.objects.filter(tenant=tenant, branch=branch, is_active=True)
        total_products = products.count()
        total_stock = products.aggregate(total=Sum('quantity_in_stock'))['total'] or 0
        total_value = products.aggregate(
            total=Sum(F('quantity_in_stock') * F('buying_price'))
        )['total'] or Decimal('0.00')
        
        branch_stock_data.append({
            'branch': branch,
            'product_count': total_products,
            'total_stock': total_stock,
            'total_value': total_value,
        })
    
    context = {
        'tenant': tenant,
        'branch_stock_data': branch_stock_data,
        'active_tab': 'branches',
    }
    return render(request, 'fashion_master/branch_stock_list.html', context)


@login_required
def transfer_stock(request):
    """Transfer stock between fashion branches"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    products = FashionProduct.objects.filter(tenant=tenant, is_active=True, quantity_in_stock__gt=0)
    
    if request.method == 'POST':
        from_branch_id = request.POST.get('from_branch')
        to_branch_id = request.POST.get('to_branch')
        product_id = request.POST.get('product')
        quantity = int(request.POST.get('quantity', 0))
        notes = request.POST.get('notes', '')
        
        if not from_branch_id or not to_branch_id or not product_id:
            messages.error(request, 'Please fill all required fields')
            return redirect('fashion_master:transfer_stock')
        
        if from_branch_id == to_branch_id:
            messages.error(request, 'Source and destination branches cannot be the same')
            return redirect('fashion_master:transfer_stock')
        
        if quantity <= 0:
            messages.error(request, 'Quantity must be greater than 0')
            return redirect('fashion_master:transfer_stock')
        
        from_branch = get_object_or_404(Branch, id=from_branch_id, tenant=tenant)
        to_branch = get_object_or_404(Branch, id=to_branch_id, tenant=tenant)
        product = get_object_or_404(FashionProduct, id=product_id, tenant=tenant)
        
        if product.quantity_in_stock < quantity:
            messages.error(request, f'Only {product.quantity_in_stock} units available in {from_branch.name}')
            return redirect('fashion_master:transfer_stock')
        
        # Update product branch
        product.branch = to_branch
        product.save()
        
        # Create inventory movement
        FashionInventoryMovement.objects.create(
            tenant=tenant,
            product=product,
            movement_type='transfer',
            quantity=-quantity,
            unit_price=product.buying_price,
            total_amount=-(quantity * product.buying_price),
            branch=from_branch,
            reference=f"Transfer to {to_branch.name}",
            notes=notes,
            created_by=request.user
        )
        
        FashionInventoryMovement.objects.create(
            tenant=tenant,
            product=product,
            movement_type='transfer',
            quantity=quantity,
            unit_price=product.buying_price,
            total_amount=quantity * product.buying_price,
            branch=to_branch,
            reference=f"Transfer from {from_branch.name}",
            notes=notes,
            created_by=request.user
        )
        
        messages.success(request, f'Transferred {quantity} units of {product.name} from {from_branch.name} to {to_branch.name}')
        return redirect('fashion_master:branch_stock_list')
    
    context = {
        'tenant': tenant,
        'branches': branches,
        'products': products,
        'active_tab': 'branches',
    }
    return render(request, 'fashion_master/transfer_stock.html', context)



# ============================================
# DASHBOARD
# ============================================

@login_required
def dashboard(request):
    """Fashion Master Dashboard"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    # Statistics
    total_products = FashionProduct.objects.filter(tenant=tenant, is_active=True).count()
    total_categories = FashionCategory.objects.filter(tenant=tenant, is_active=True).count()
    
    # Sales stats
    today = timezone.now().date()
    today_sales = FashionSale.objects.filter(
        tenant=tenant,
        status='completed',
        sale_date__date=today
    )
    today_total = today_sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    month_sales = FashionSale.objects.filter(
        tenant=tenant,
        status='completed',
        sale_date__month=today.month
    )
    month_total = month_sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    # Low stock
    low_stock_products = FashionProduct.objects.filter(
        tenant=tenant,
        is_active=True,
        quantity_in_stock__lte=F('reorder_level')
    ).count()
    
    context = {
        'tenant': tenant,
        'total_products': total_products,
        'total_categories': total_categories,
        'today_sales': today_sales.count(),
        'today_total': today_total,
        'month_total': month_total,
        'low_stock_products': low_stock_products,
        'active_tab': 'dashboard',
    }
    return render(request, 'fashion_master/dashboard.html', context)


# ============================================
# CATEGORY VIEWS
# ============================================

@login_required
def category_list(request):
    """List fashion categories"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    categories = FashionCategory.objects.filter(tenant=tenant).order_by('category_type', 'name')
    
    context = {
        'tenant': tenant,
        'categories': categories,
        'active_tab': 'categories',
    }
    return render(request, 'fashion_master/category_list.html', context)


@login_required
def category_create(request):
    """Create fashion category"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        category_type = request.POST.get('category_type')
        gender = request.POST.get('gender', 'unisex')
        size_type = request.POST.get('size_type')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not category_type:
            messages.error(request, 'Name and category type are required')
            return redirect('fashion_master:category_create')
        
        if FashionCategory.objects.filter(tenant=tenant, name=name).exists():
            messages.error(request, f'Category "{name}" already exists')
            return redirect('fashion_master:category_create')
        
        category = FashionCategory.objects.create(
            tenant=tenant,
            name=name,
            category_type=category_type,
            gender=gender,
            size_type=size_type,
            description=description,
            is_active=is_active,
            created_by=request.user
        )
        
        messages.success(request, f'Category "{category.name}" created successfully!')
        return redirect('fashion_master:category_list')
    
    context = {
        'tenant': tenant,
        'active_tab': 'categories',
    }
    return render(request, 'fashion_master/category_form.html', context)


@login_required
def category_edit(request, pk):
    """Edit fashion category"""
    tenant = request.user.tenant
    category = get_object_or_404(FashionCategory, id=pk, tenant=tenant)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        category_type = request.POST.get('category_type')
        gender = request.POST.get('gender', 'unisex')
        size_type = request.POST.get('size_type')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not category_type:
            messages.error(request, 'Name and category type are required')
            return redirect('fashion_master:category_edit', pk=category.id)
        
        if FashionCategory.objects.filter(tenant=tenant, name=name).exclude(id=category.id).exists():
            messages.error(request, f'Category "{name}" already exists')
            return redirect('fashion_master:category_edit', pk=category.id)
        
        category.name = name
        category.category_type = category_type
        category.gender = gender
        category.size_type = size_type
        category.description = description
        category.is_active = is_active
        category.save()
        
        messages.success(request, f'Category "{category.name}" updated successfully!')
        return redirect('fashion_master:category_list')
    
    context = {
        'tenant': tenant,
        'category': category,
        'active_tab': 'categories',
    }
    return render(request, 'fashion_master/category_form.html', context)


@login_required
def category_delete(request, pk):
    """Delete fashion category"""
    tenant = request.user.tenant
    category = get_object_or_404(FashionCategory, id=pk, tenant=tenant)
    
    if request.method == 'POST':
        # Check if category has products
        if category.fashion_products.exists():
            messages.error(request, f'Cannot delete "{category.name}" because it has products.')
            return redirect('fashion_master:category_list')
        
        category_name = category.name
        category.delete()
        messages.success(request, f'Category "{category_name}" deleted successfully!')
        return redirect('fashion_master:category_list')
    
    context = {
        'tenant': tenant,
        'category': category,
        'active_tab': 'categories',
    }
    return render(request, 'fashion_master/category_confirm_delete.html', context)


# ============================================
# PRODUCT VIEWS
# ============================================

@login_required
def product_list(request):
    """List fashion products"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    category_id = request.GET.get('category')
    search = request.GET.get('q', '')
    
    products = FashionProduct.objects.filter(tenant=tenant, is_active=True).select_related('category', 'branch')
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(brand__icontains=search) |
            Q(sku_code__icontains=search)
        )
    
    paginator = Paginator(products, 20)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    categories = FashionCategory.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'products': page_obj,
        'categories': categories,
        'selected_category': category_id,
        'search': search,
        'active_tab': 'products',
    }
    return render(request, 'fashion_master/product_list.html', context)


@login_required
def product_create(request):
    """Create fashion product"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    categories = FashionCategory.objects.filter(tenant=tenant, is_active=True)
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    suppliers = Supplier.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        category_id = request.POST.get('category')
        name = request.POST.get('name')
        brand = request.POST.get('brand', '')
        size = request.POST.get('size', '')
        color = request.POST.get('color', '')
        material = request.POST.get('material', '')
        buying_price = request.POST.get('buying_price', 0)
        selling_price = request.POST.get('selling_price', 0)
        quantity = request.POST.get('quantity', 0)
        reorder_level = request.POST.get('reorder_level', 10)
        branch_id = request.POST.get('branch')
        supplier_id = request.POST.get('supplier')
        is_active = request.POST.get('is_active') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        is_new_arrival = request.POST.get('is_new_arrival') == 'on'
        
        if not category_id or not name:
            messages.error(request, 'Category and name are required')
            return redirect('fashion_master:product_create')
        
        category = get_object_or_404(FashionCategory, id=category_id, tenant=tenant)
        branch = None
        if branch_id:
            branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
        supplier = None
        if supplier_id:
            supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)
        
        product = FashionProduct.objects.create(
            tenant=tenant,
            category=category,
            branch=branch,
            supplier=supplier,
            name=name,
            brand=brand,
            size=size,
            color=color,
            material=material,
            buying_price=Decimal(str(buying_price)),
            selling_price=Decimal(str(selling_price)),
            quantity_in_stock=int(quantity),
            reorder_level=int(reorder_level),
            is_active=is_active,
            is_featured=is_featured,
            is_new_arrival=is_new_arrival,
            created_by=request.user
        )
        
        messages.success(request, f'Product "{product.name}" created successfully!')
        return redirect('fashion_master:product_detail', pk=product.id)
    
    context = {
        'tenant': tenant,
        'categories': categories,
        'branches': branches,
        'suppliers': suppliers,
        'active_tab': 'products',
    }
    return render(request, 'fashion_master/product_form.html', context)


@login_required
def product_detail(request, pk):
    """View fashion product details"""
    tenant = request.user.tenant
    product = get_object_or_404(FashionProduct, id=pk, tenant=tenant)
    variants = product.variants.filter(is_active=True)
    
    context = {
        'tenant': tenant,
        'product': product,
        'variants': variants,
        'active_tab': 'products',
    }
    return render(request, 'fashion_master/product_detail.html', context)


@login_required
def product_edit(request, pk):
    """Edit fashion product"""
    tenant = request.user.tenant
    product = get_object_or_404(FashionProduct, id=pk, tenant=tenant)
    
    categories = FashionCategory.objects.filter(tenant=tenant, is_active=True)
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    suppliers = Supplier.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        category_id = request.POST.get('category')
        name = request.POST.get('name')
        brand = request.POST.get('brand', '')
        size = request.POST.get('size', '')
        color = request.POST.get('color', '')
        material = request.POST.get('material', '')
        buying_price = request.POST.get('buying_price', 0)
        selling_price = request.POST.get('selling_price', 0)
        quantity = request.POST.get('quantity', 0)
        reorder_level = request.POST.get('reorder_level', 10)
        branch_id = request.POST.get('branch')
        supplier_id = request.POST.get('supplier')
        is_active = request.POST.get('is_active') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        is_new_arrival = request.POST.get('is_new_arrival') == 'on'
        
        if not category_id or not name:
            messages.error(request, 'Category and name are required')
            return redirect('fashion_master:product_edit', pk=product.id)
        
        category = get_object_or_404(FashionCategory, id=category_id, tenant=tenant)
        branch = None
        if branch_id:
            branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
        supplier = None
        if supplier_id:
            supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)
        
        product.category = category
        product.branch = branch
        product.supplier = supplier
        product.name = name
        product.brand = brand
        product.size = size
        product.color = color
        product.material = material
        product.buying_price = Decimal(str(buying_price))
        product.selling_price = Decimal(str(selling_price))
        product.quantity_in_stock = int(quantity)
        product.reorder_level = int(reorder_level)
        product.is_active = is_active
        product.is_featured = is_featured
        product.is_new_arrival = is_new_arrival
        product.last_modified_by = request.user
        product.save()
        
        messages.success(request, f'Product "{product.name}" updated successfully!')
        return redirect('fashion_master:product_detail', pk=product.id)
    
    context = {
        'tenant': tenant,
        'product': product,
        'categories': categories,
        'branches': branches,
        'suppliers': suppliers,
        'active_tab': 'products',
    }
    return render(request, 'fashion_master/product_form.html', context)


@login_required
def product_delete(request, pk):
    """Delete fashion product"""
    tenant = request.user.tenant
    product = get_object_or_404(FashionProduct, id=pk, tenant=tenant)
    
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f'Product "{product_name}" deleted successfully!')
        return redirect('fashion_master:product_list')
    
    context = {
        'tenant': tenant,
        'product': product,
        'active_tab': 'products',
    }
    return render(request, 'fashion_master/product_confirm_delete.html', context)


@login_required
def add_variant(request, pk):
    """Add variant to product"""
    tenant = request.user.tenant
    product = get_object_or_404(FashionProduct, id=pk, tenant=tenant)
    
    if request.method == 'POST':
        size = request.POST.get('size')
        color = request.POST.get('color')
        sku = request.POST.get('sku')
        buying_price = request.POST.get('buying_price', 0)
        selling_price = request.POST.get('selling_price', 0)
        quantity = request.POST.get('quantity', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if not size or not color:
            messages.error(request, 'Size and color are required')
            return redirect('fashion_master:add_variant', pk=product.id)
        
        if not sku:
            sku = f"{product.sku_code}-{size.upper()}-{color.upper()}"
        
        if FashionVariant.objects.filter(tenant=tenant, sku=sku).exists():
            messages.error(request, f'Variant SKU "{sku}" already exists')
            return redirect('fashion_master:add_variant', pk=product.id)
        
        variant = FashionVariant.objects.create(
            tenant=tenant,
            product=product,
            size=size,
            color=color,
            sku=sku,
            buying_price=Decimal(str(buying_price)) if buying_price else None,
            selling_price=Decimal(str(selling_price)) if selling_price else None,
            quantity=int(quantity),
            is_active=is_active
        )
        
        messages.success(request, f'Variant {size}-{color} added successfully!')
        return redirect('fashion_master:product_detail', pk=product.id)
    
    context = {
        'tenant': tenant,
        'product': product,
        'active_tab': 'products',
    }
    return render(request, 'fashion_master/variant_form.html', context)


# ============================================
# VARIANT VIEWS
# ============================================

@login_required
def variant_edit(request, pk):
    """Edit fashion variant"""
    tenant = request.user.tenant
    variant = get_object_or_404(FashionVariant, id=pk, tenant=tenant)
    
    if request.method == 'POST':
        size = request.POST.get('size')
        color = request.POST.get('color')
        sku = request.POST.get('sku')
        buying_price = request.POST.get('buying_price', 0)
        selling_price = request.POST.get('selling_price', 0)
        quantity = request.POST.get('quantity', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if not size or not color:
            messages.error(request, 'Size and color are required')
            return redirect('fashion_master:variant_edit', pk=variant.id)
        
        if FashionVariant.objects.filter(tenant=tenant, sku=sku).exclude(id=variant.id).exists():
            messages.error(request, f'Variant SKU "{sku}" already exists')
            return redirect('fashion_master:variant_edit', pk=variant.id)
        
        variant.size = size
        variant.color = color
        variant.sku = sku
        variant.buying_price = Decimal(str(buying_price)) if buying_price else None
        variant.selling_price = Decimal(str(selling_price)) if selling_price else None
        variant.quantity = int(quantity)
        variant.is_active = is_active
        variant.save()
        
        messages.success(request, f'Variant updated successfully!')
        return redirect('fashion_master:product_detail', pk=variant.product.id)
    
    context = {
        'tenant': tenant,
        'variant': variant,
        'active_tab': 'products',
    }
    return render(request, 'fashion_master/variant_form.html', context)


@login_required
def variant_delete(request, pk):
    """Delete fashion variant"""
    tenant = request.user.tenant
    variant = get_object_or_404(FashionVariant, id=pk, tenant=tenant)
    product_id = variant.product.id
    
    if request.method == 'POST':
        variant.delete()
        messages.success(request, 'Variant deleted successfully!')
        return redirect('fashion_master:product_detail', pk=product_id)
    
    context = {
        'tenant': tenant,
        'variant': variant,
        'active_tab': 'products',
    }
    return render(request, 'fashion_master/variant_confirm_delete.html', context)


# ============================================
# SALE VIEWS
# ============================================

@login_required
def sale_list(request):
    """List fashion sales"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    sales = FashionSale.objects.filter(tenant=tenant).order_by('-sale_date')
    
    paginator = Paginator(sales, 20)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    context = {
        'tenant': tenant,
        'sales': page_obj,
        'active_tab': 'sales',
    }
    return render(request, 'fashion_master/sale_list.html', context)


@login_required
def sale_create(request):
    """Create fashion sale"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    products = FashionProduct.objects.filter(tenant=tenant, is_active=True, quantity_in_stock__gt=0)
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        # This would handle the sale creation logic
        # For now, redirect to sale list
        messages.success(request, 'Sale created successfully!')
        return redirect('fashion_master:sale_list')
    
    context = {
        'tenant': tenant,
        'products': products,
        'branches': branches,
        'active_tab': 'sales',
    }
    return render(request, 'fashion_master/sale_form.html', context)


@login_required
def sale_detail(request, pk):
    """View fashion sale details"""
    tenant = request.user.tenant
    sale = get_object_or_404(FashionSale, id=pk, tenant=tenant)
    items = sale.items.all()
    
    context = {
        'tenant': tenant,
        'sale': sale,
        'items': items,
        'active_tab': 'sales',
    }
    return render(request, 'fashion_master/sale_detail.html', context)


@login_required
def sale_receipt(request, pk):
    """View fashion sale receipt"""
    tenant = request.user.tenant
    sale = get_object_or_404(FashionSale, id=pk, tenant=tenant)
    items = sale.items.all()
    
    context = {
        'tenant': tenant,
        'sale': sale,
        'items': items,
        'active_tab': 'sales',
    }
    return render(request, 'fashion_master/receipt.html', context)


# ============================================
# RETURN VIEWS
# ============================================

@login_required
def return_list(request):
    """List fashion returns"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    returns = FashionReturn.objects.filter(tenant=tenant).order_by('-created_at')
    
    paginator = Paginator(returns, 20)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    context = {
        'tenant': tenant,
        'returns': page_obj,
        'active_tab': 'returns',
    }
    return render(request, 'fashion_master/return_list.html', context)


@login_required
def return_detail(request, pk):
    """View fashion return details"""
    tenant = request.user.tenant
    return_obj = get_object_or_404(FashionReturn, id=pk, tenant=tenant)
    
    context = {
        'tenant': tenant,
        'return': return_obj,
        'active_tab': 'returns',
    }
    return render(request, 'fashion_master/return_detail.html', context)


@login_required
def return_approve(request, pk):
    """Approve fashion return"""
    tenant = request.user.tenant
    return_obj = get_object_or_404(FashionReturn, id=pk, tenant=tenant)
    
    if return_obj.status != 'pending':
        messages.warning(request, 'This return is already processed')
        return redirect('fashion_master:return_detail', pk=return_obj.id)
    
    return_obj.status = 'approved'
    return_obj.approved_by = request.user
    return_obj.approved_at = timezone.now()
    return_obj.save()
    
    messages.success(request, f'Return for {return_obj.product.name} approved successfully!')
    return redirect('fashion_master:return_detail', pk=return_obj.id)


@login_required
def return_reject(request, pk):
    """Reject fashion return"""
    tenant = request.user.tenant
    return_obj = get_object_or_404(FashionReturn, id=pk, tenant=tenant)
    
    if return_obj.status != 'pending':
        messages.warning(request, 'This return is already processed')
        return redirect('fashion_master:return_detail', pk=return_obj.id)
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '')
        
        return_obj.status = 'rejected'
        return_obj.approved_by = request.user
        return_obj.approved_at = timezone.now()
        return_obj.rejection_reason = rejection_reason
        return_obj.save()
        
        messages.success(request, f'Return for {return_obj.product.name} rejected.')
        return redirect('fashion_master:return_detail', pk=return_obj.id)
    
    context = {
        'tenant': tenant,
        'return': return_obj,
        'active_tab': 'returns',
    }
    return render(request, 'fashion_master/return_reject.html', context)


# ============================================
# INVENTORY VIEWS
# ============================================

@login_required
def inventory_list(request):
    """List fashion inventory"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    products = FashionProduct.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    paginator = Paginator(products, 20)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    context = {
        'tenant': tenant,
        'products': page_obj,
        'active_tab': 'inventory',
    }
    return render(request, 'fashion_master/inventory_list.html', context)


@login_required
def inventory_movements(request):
    """View fashion inventory movements"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    movements = FashionInventoryMovement.objects.filter(tenant=tenant).order_by('-created_at')
    
    paginator = Paginator(movements, 20)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    context = {
        'tenant': tenant,
        'movements': page_obj,
        'active_tab': 'inventory',
    }
    return render(request, 'fashion_master/inventory_movements.html', context)


# ============================================
# REPORT VIEWS
# ============================================

@login_required
def reports(request):
    """Fashion reports"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    # Sales summary
    today = timezone.now().date()
    total_sales = FashionSale.objects.filter(tenant=tenant, status='completed')
    total_revenue = total_sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    total_orders = total_sales.count()
    
    # Top products
    top_products = FashionSaleItem.objects.filter(
        sale__tenant=tenant,
        sale__status='completed'
    ).values('product_name').annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('subtotal')
    ).order_by('-total_sold')[:10]
    
    context = {
        'tenant': tenant,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'top_products': top_products,
        'active_tab': 'reports',
    }
    return render(request, 'fashion_master/reports.html', context)





# ============================================
# API VIEWS
# ============================================

@login_required
def api_search_products(request):
    """API endpoint for searching fashion products"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category')
    limit = int(request.GET.get('limit', 50))
    
    products = FashionProduct.objects.filter(
        tenant=tenant,
        is_active=True,
        quantity_in_stock__gt=0
    ).select_related('category')
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(sku_code__icontains=query) |
            Q(barcode__icontains=query)
        )
    
    products = products[:limit]
    
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'name': product.name,
            'sku_code': product.sku_code,
            'brand': product.brand,
            'size': product.size,
            'color': product.color,
            'selling_price': float(product.selling_price),
            'buying_price': float(product.buying_price),
            'quantity_in_stock': product.quantity_in_stock,
            'category': product.category.name if product.category else None,
            'image': product.image.url if product.image else None,
            'is_featured': product.is_featured,
            'is_new_arrival': product.is_new_arrival,
        })
    
    return JsonResponse({
        'success': True,
        'products': results,
        'count': len(results)
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_process_sale(request):
    """API endpoint for processing fashion sales"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        customer_name = data.get('customer_name', 'Walk-in Customer')
        customer_phone = data.get('customer_phone', '')
        payment_method = data.get('payment_method', 'cash')
        amount_paid = Decimal(str(data.get('amount_paid', 0)))
        subtotal = Decimal(str(data.get('subtotal', 0)))
        tax = Decimal(str(data.get('tax', 0)))
        total = Decimal(str(data.get('total', 0)))
        
        if not items:
            return JsonResponse({'error': 'No items in cart'}, status=400)
        
        # Get or create customer
        customer = None
        if customer_phone:
            customer = Customer.objects.filter(tenant=tenant, phone=customer_phone).first()
            if not customer and customer_name != 'Walk-in Customer':
                customer = Customer.objects.create(
                    tenant=tenant,
                    name=customer_name,
                    phone=customer_phone,
                    created_by=request.user
                )
        
        # Get user's branch
        user_branch = None
        if hasattr(request.user, 'branch') and request.user.branch:
            user_branch = request.user.branch
        elif hasattr(request.user, 'tech_staff_profile') and request.user.tech_staff_profile:
            user_branch = request.user.tech_staff_profile.branch
        
        # Create sale
        sale = FashionSale.objects.create(
            tenant=tenant,
            customer=customer,
            customer_name=customer_name,
            customer_phone=customer_phone,
            cashier=request.user,
            branch=user_branch,
            subtotal=subtotal,
            tax=tax,
            total=total,
            payment_method=payment_method,
            amount_paid=amount_paid,
            change_given=amount_paid - total,
            status='completed',
            invoice_no=f"FSH-{timezone.now().strftime('%Y%m%d')}-{FashionSale.objects.filter(tenant=tenant).count() + 1:04d}"
        )
        
        # Create sale items and update stock
        for item in items:
            product_id = item.get('id')
            quantity = int(item.get('quantity', 1))
            price = Decimal(str(item.get('price', 0)))
            
            product = FashionProduct.objects.filter(id=product_id, tenant=tenant).first()
            if not product:
                continue
            
            # Update stock
            product.quantity_in_stock -= quantity
            product.save()
            
            # Create sale item
            FashionSaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=quantity,
                price=price,
                subtotal=price * quantity,
                product_name=product.name,
                product_size=product.size or '',
                product_color=product.color or '',
                product_sku=product.sku_code
            )
            
            # Create inventory movement
            FashionInventoryMovement.objects.create(
                tenant=tenant,
                product=product,
                movement_type='sale',
                quantity=-quantity,
                unit_price=price,
                total_amount=-(price * quantity),
                reference=sale.invoice_no,
                notes=f"Sale {sale.invoice_no}",
                created_by=request.user
            )
        
        return JsonResponse({
            'success': True,
            'sale_id': sale.id,
            'receipt_number': sale.invoice_no,
            'total': float(total),
            'amount_paid': float(amount_paid),
            'change': float(amount_paid - total)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_approve_return(request, return_id):
    """API endpoint for approving a return"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    try:
        return_obj = get_object_or_404(FashionReturn, id=return_id, tenant=tenant)
        
        if return_obj.status != 'pending':
            return JsonResponse({'error': 'Return already processed'}, status=400)
        
        # Approve return
        return_obj.status = 'approved'
        return_obj.approved_by = request.user
        return_obj.approved_at = timezone.now()
        return_obj.save()
        
        # Restore stock
        return_obj.product.quantity_in_stock += return_obj.quantity
        return_obj.product.save()
        
        # Create inventory movement
        FashionInventoryMovement.objects.create(
            tenant=tenant,
            product=return_obj.product,
            movement_type='return',
            quantity=return_obj.quantity,
            unit_price=return_obj.amount / return_obj.quantity if return_obj.quantity > 0 else 0,
            total_amount=return_obj.amount,
            reference=return_obj.sale.invoice_no,
            notes=f"Return approved - {return_obj.reason}",
            created_by=request.user
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_reject_return(request, return_id):
    """API endpoint for rejecting a return"""
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    try:
        return_obj = get_object_or_404(FashionReturn, id=return_id, tenant=tenant)
        
        if return_obj.status != 'pending':
            return JsonResponse({'error': 'Return already processed'}, status=400)
        
        return_obj.status = 'rejected'
        return_obj.approved_by = request.user
        return_obj.approved_at = timezone.now()
        return_obj.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)   