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
import logging

from apps.shared.users.models import User
from apps.tech_master.models import Branch

from .models import FashionProduct, FashionVariant, FashionCategory
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Sum, Count, F
from django.core.paginator import Paginator
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
import csv
import json
import logging

from apps.shared.users.models import User
from apps.shared.expenses.models import Expense
from apps.tech_master.models import Branch

from .models import FashionProduct, FashionVariant, FashionCategory, FashionSale, FashionSaleItem, FashionReturn

# apps/fashion_master/views.py

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from decimal import Decimal
import logging

from apps.shared.users.models import User

from .models import FashionSale, FashionSaleItem, FashionProduct

logger = logging.getLogger(__name__)






logger = logging.getLogger(__name__)


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
# SEARCH SALE VIEWS
# ============================================

@login_required
def search_sale(request):
    """
    Search sales by invoice number, customer name, phone, or product
    """
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    search_query = request.GET.get('q', '').strip()
    search_type = request.GET.get('type', 'all')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    status = request.GET.get('status', '')
    
    sales = FashionSale.objects.filter(tenant=tenant).order_by('-sale_date')
    
    # Apply filters
    if search_query:
        if search_type == 'invoice':
            sales = sales.filter(invoice_no__icontains=search_query)
        elif search_type == 'customer':
            sales = sales.filter(
                Q(customer_name__icontains=search_query) |
                Q(customer_phone__icontains=search_query) |
                Q(customer_email__icontains=search_query)
            )
        elif search_type == 'product':
            # Search by product name in sale items
            sale_ids = FashionSaleItem.objects.filter(
                product_name__icontains=search_query
            ).values_list('sale_id', flat=True).distinct()
            sales = sales.filter(id__in=sale_ids)
        else:
            # All types
            sales = sales.filter(
                Q(invoice_no__icontains=search_query) |
                Q(customer_name__icontains=search_query) |
                Q(customer_phone__icontains=search_query) |
                Q(customer_email__icontains=search_query) |
                Q(id__in=FashionSaleItem.objects.filter(
                    product_name__icontains=search_query
                ).values_list('sale_id', flat=True))
            )
    
    if date_from:
        sales = sales.filter(sale_date__date__gte=date_from)
    
    if date_to:
        sales = sales.filter(sale_date__date__lte=date_to)
    
    if status:
        sales = sales.filter(status=status)
    
    # Add item count to each sale
    for sale in sales:
        sale.item_count = sale.items.count()
    
    # Statistics
    total_sales = sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    total_count = sales.count()
    
    # Pagination
    paginator = Paginator(sales, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'sales': page_obj,
        'search_query': search_query,
        'search_type': search_type,
        'date_from': date_from,
        'date_to': date_to,
        'status': status,
        'total_sales': total_sales,
        'total_count': total_count,
        'active_tab': 'sales',
    }
    return render(request, 'fashion_master/search_sale.html', context)


@login_required
def search_sale_ajax(request):
    """
    AJAX endpoint for live sale search suggestions
    """
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'results': []})
    
    results = []
    
    # Search by invoice number
    sales = FashionSale.objects.filter(
        tenant=tenant,
        invoice_no__icontains=query
    ).values('id', 'invoice_no', 'customer_name', 'total', 'status')[:10]
    
    for sale in sales:
        results.append({
            'type': 'invoice',
            'id': sale['id'],
            'invoice_no': sale['invoice_no'],
            'customer_name': sale['customer_name'] or 'Walk-in',
            'total': float(sale['total']) if sale['total'] else 0,
            'status': sale['status'],
            'url': f"/fashion/sales/{sale['id']}/"
        })
    
    # Search by customer name or phone
    if len(results) < 10:
        customer_sales = FashionSale.objects.filter(
            Q(customer_name__icontains=query) |
            Q(customer_phone__icontains=query),
            tenant=tenant
        ).values('id', 'invoice_no', 'customer_name', 'total', 'status')[:10]
        
        for sale in customer_sales:
            if sale['id'] not in [r['id'] for r in results]:
                results.append({
                    'type': 'customer',
                    'id': sale['id'],
                    'invoice_no': sale['invoice_no'],
                    'customer_name': sale['customer_name'] or 'Walk-in',
                    'total': float(sale['total']) if sale['total'] else 0,
                    'status': sale['status'],
                    'url': f"/fashion/sales/{sale['id']}/"
                })
    
    # Search by product name in sale items
    if len(results) < 10:
        product_sale_ids = FashionSaleItem.objects.filter(
            product_name__icontains=query
        ).values_list('sale_id', flat=True).distinct()[:10]
        
        product_sales = FashionSale.objects.filter(
            tenant=tenant,
            id__in=product_sale_ids
        ).values('id', 'invoice_no', 'customer_name', 'total', 'status')
        
        for sale in product_sales:
            if sale['id'] not in [r['id'] for r in results]:
                results.append({
                    'type': 'product',
                    'id': sale['id'],
                    'invoice_no': sale['invoice_no'],
                    'customer_name': sale['customer_name'] or 'Walk-in',
                    'total': float(sale['total']) if sale['total'] else 0,
                    'status': sale['status'],
                    'url': f"/fashion/sales/{sale['id']}/"
                })
    
    return JsonResponse({'results': results})

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
# REPORTS VIEWS
# ============================================

@login_required
def reports_dashboard(request):
    """
    Reports Dashboard - Main reports page with analytics
    """
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    # Date ranges
    today = timezone.now().date()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    
    # Sales statistics
    total_sales = FashionSale.objects.filter(
        tenant=tenant,
        status='completed'
    )
    
    # Today's sales
    today_sales = total_sales.filter(
        sale_date__date=today
    )
    today_total = today_sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    today_count = today_sales.count()
    
    # This month's sales
    month_sales = total_sales.filter(
        sale_date__date__gte=month_start
    )
    month_total = month_sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    month_count = month_sales.count()
    
    # This year's sales
    year_sales = total_sales.filter(
        sale_date__date__gte=year_start
    )
    year_total = year_sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    # Average sale value
    avg_sale = month_sales.aggregate(avg=Sum('total') / Count('id'))['avg'] or Decimal('0.00')
    
    # Top products
    top_products = FashionSaleItem.objects.filter(
        sale__tenant=tenant,
        sale__status='completed'
    ).values(
        'product__id',
        'product__name',
        'product__sku_code'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('subtotal')
    ).order_by('-total_revenue')[:10]
    
    # Recent sales (last 10)
    recent_sales = total_sales.select_related(
        'customer', 'cashier', 'branch'
    ).order_by('-sale_date')[:10]
    
    # Stock overview
    total_products = FashionProduct.objects.filter(
        tenant=tenant,
        is_active=True
    ).count()
    
    low_stock_products = FashionProduct.objects.filter(
        tenant=tenant,
        is_active=True,
        quantity_in_stock__lte=F('reorder_level'),
        quantity_in_stock__gt=0
    ).count()
    
    out_of_stock_products = FashionProduct.objects.filter(
        tenant=tenant,
        is_active=True,
        quantity_in_stock=0
    ).count()
    
    context = {
        'tenant': tenant,
        'today_total': today_total,
        'today_count': today_count,
        'month_total': month_total,
        'month_count': month_count,
        'year_total': year_total,
        'avg_sale': avg_sale,
        'top_products': top_products,
        'recent_sales': recent_sales,
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'active_tab': 'reports',
    }
    return render(request, 'fashion_master/reports_dashboard.html', context)


@login_required
def sales_report(request):
    """
    Detailed Sales Report with filters
    """
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    # Get filter parameters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    payment_method = request.GET.get('payment_method')
    cashier_id = request.GET.get('cashier')
    branch_id = request.GET.get('branch')
    
    # Base queryset
    sales = FashionSale.objects.filter(
        tenant=tenant,
        status='completed'
    ).select_related('customer', 'cashier', 'branch')
    
    # Apply filters
    if date_from:
        sales = sales.filter(sale_date__date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__date__lte=date_to)
    if payment_method:
        sales = sales.filter(payment_method=payment_method)
    if cashier_id:
        sales = sales.filter(cashier_id=cashier_id)
    if branch_id:
        sales = sales.filter(branch_id=branch_id)
    
    # Statistics
    total_sales = sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    total_count = sales.count()
    avg_sale = total_sales / total_count if total_count > 0 else Decimal('0.00')
    
    # Payment method breakdown
    payment_breakdown = sales.values('payment_method').annotate(
        count=Count('id'),
        total=Sum('total')
    ).order_by('-total')
    
    # Daily sales for chart
    daily_sales = []
    if date_from and date_to:
        start = datetime.strptime(date_from, '%Y-%m-%d').date()
        end = datetime.strptime(date_to, '%Y-%m-%d').date()
        delta = (end - start).days + 1
        for i in range(delta):
            date = start + timedelta(days=i)
            day_total = sales.filter(sale_date__date=date).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
            daily_sales.append({
                'date': date.strftime('%Y-%m-%d'),
                'total': float(day_total)
            })
    
    # Get cashiers and branches for filters
    cashiers = User.objects.filter(tenant=tenant, is_active=True)
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    # Pagination
    paginator = Paginator(sales, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'sales': page_obj,
        'total_sales': total_sales,
        'total_count': total_count,
        'avg_sale': avg_sale,
        'payment_breakdown': payment_breakdown,
        'daily_sales': daily_sales,
        'cashiers': cashiers,
        'branches': branches,
        'date_from': date_from,
        'date_to': date_to,
        'payment_method': payment_method,
        'cashier_id': cashier_id,
        'branch_id': branch_id,
        'active_tab': 'reports',
    }
    return render(request, 'fashion_master/sales_report.html', context)


@login_required
def inventory_report(request):
    """
    Detailed Inventory Report
    """
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    # Get filter parameters
    category_id = request.GET.get('category')
    stock_status = request.GET.get('stock_status')
    search = request.GET.get('search', '')
    
    # Base queryset
    products = FashionProduct.objects.filter(
        tenant=tenant,
        is_active=True
    ).select_related('category', 'branch', 'supplier')
    
    # Apply filters
    if category_id:
        products = products.filter(category_id=category_id)
    
    if stock_status == 'in_stock':
        products = products.filter(quantity_in_stock__gt=0)
    elif stock_status == 'low_stock':
        products = products.filter(
            quantity_in_stock__lte=F('reorder_level'),
            quantity_in_stock__gt=0
        )
    elif stock_status == 'out_of_stock':
        products = products.filter(quantity_in_stock=0)
    
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(brand__icontains=search) |
            Q(sku_code__icontains=search) |
            Q(barcode__icontains=search)
        )
    
    # Statistics
    total_products = products.count()
    total_stock_value = products.aggregate(
        total=Sum(F('quantity_in_stock') * F('buying_price'))
    )['total'] or Decimal('0.00')
    
    # Category breakdown
    category_breakdown = products.values('category__name').annotate(
        count=Count('id'),
        total_stock=Sum('quantity_in_stock'),
        total_value=Sum(F('quantity_in_stock') * F('buying_price'))
    ).order_by('-total_value')
    
    # Get categories for filter
    categories = FashionCategory.objects.filter(tenant=tenant, is_active=True)
    
    # Pagination
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'products': page_obj,
        'total_products': total_products,
        'total_stock_value': total_stock_value,
        'category_breakdown': category_breakdown,
        'categories': categories,
        'category_id': category_id,
        'stock_status': stock_status,
        'search': search,
        'active_tab': 'reports',
    }
    return render(request, 'fashion_master/inventory_report.html', context)


@login_required
def expense_report(request):
    """
    Detailed Expense Report
    """
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    # Get date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    category_id = request.GET.get('category')
    status = request.GET.get('status')
    
    # Base queryset
    expenses = Expense.objects.filter(
        tenant=tenant,
        status__in=['approved', 'paid']
    )
    
    if date_from:
        expenses = expenses.filter(date__gte=date_from)
    if date_to:
        expenses = expenses.filter(date__lte=date_to)
    if category_id:
        expenses = expenses.filter(category_id=category_id)
    if status:
        expenses = expenses.filter(status=status)
    
    # Statistics
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_count = expenses.count()
    avg_expense = total_expenses / total_count if total_count > 0 else Decimal('0.00')
    
    # Category breakdown
    category_breakdown = expenses.values('category__name').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-total')
    
    # Get categories for filter
    from apps.shared.expenses.models import ExpenseCategory
    categories = ExpenseCategory.objects.filter(tenant=tenant, is_active=True)
    
    # Pagination
    paginator = Paginator(expenses, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'expenses': page_obj,
        'total_expenses': total_expenses,
        'total_count': total_count,
        'avg_expense': avg_expense,
        'category_breakdown': category_breakdown,
        'categories': categories,
        'date_from': date_from,
        'date_to': date_to,
        'category_id': category_id,
        'status': status,
        'active_tab': 'reports',
    }
    return render(request, 'fashion_master/expense_report.html', context)


@login_required
def export_report(request):
    """
    Export reports in CSV or Excel format
    """
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    report_type = request.GET.get('type', 'sales')
    format_type = request.GET.get('format', 'csv')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if report_type == 'sales':
        return export_sales_report(tenant, format_type, date_from, date_to)
    elif report_type == 'inventory':
        return export_inventory_report(tenant, format_type)
    elif report_type == 'expenses':
        return export_expenses_report(tenant, format_type, date_from, date_to)
    else:
        messages.error(request, 'Invalid report type')
        return redirect('fashion_master:reports')


def export_sales_report(tenant, format_type, date_from, date_to):
    """Export sales report to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sales_report.csv"'
    
    sales = FashionSale.objects.filter(
        tenant=tenant,
        status='completed'
    ).select_related('customer', 'cashier', 'branch')
    
    if date_from:
        sales = sales.filter(sale_date__date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__date__lte=date_to)
    
    writer = csv.writer(response)
    writer.writerow([
        'Invoice No', 'Date', 'Customer', 'Phone', 'Branch',
        'Cashier', 'Subtotal', 'Discount', 'Tax', 'Total', 'Payment Method'
    ])
    
    for sale in sales:
        writer.writerow([
            sale.invoice_no,
            sale.sale_date.strftime('%Y-%m-%d %H:%M'),
            sale.customer_name or 'Walk-in',
            sale.customer_phone or '',
            sale.branch.name if sale.branch else '',
            sale.cashier.get_full_name() if sale.cashier else '',
            float(sale.subtotal),
            float(sale.discount),
            float(sale.tax),
            float(sale.total),
            sale.get_payment_method_display()
        ])
    
    return response


def export_inventory_report(tenant, format_type):
    """Export inventory report to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_report.csv"'
    
    products = FashionProduct.objects.filter(
        tenant=tenant,
        is_active=True
    ).select_related('category', 'supplier', 'branch')
    
    writer = csv.writer(response)
    writer.writerow([
        'SKU', 'Name', 'Brand', 'Category', 'Size', 'Color',
        'Buying Price', 'Selling Price', 'Stock', 'Reorder Level', 'Stock Value'
    ])
    
    for product in products:
        stock_value = product.quantity_in_stock * product.buying_price
        writer.writerow([
            product.sku_code,
            product.name,
            product.brand,
            product.category.name if product.category else '',
            product.size,
            product.color,
            float(product.buying_price),
            float(product.selling_price),
            product.quantity_in_stock,
            product.reorder_level,
            float(stock_value)
        ])
    
    return response


def export_expenses_report(tenant, format_type, date_from, date_to):
    """Export expenses report to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="expenses_report.csv"'
    
    expenses = Expense.objects.filter(
        tenant=tenant,
        status__in=['approved', 'paid']
    ).select_related('category', 'created_by')
    
    if date_from:
        expenses = expenses.filter(date__gte=date_from)
    if date_to:
        expenses = expenses.filter(date__lte=date_to)
    
    writer = csv.writer(response)
    writer.writerow([
        'Title', 'Category', 'Amount', 'Date', 'Status', 'Description', 'Created By'
    ])
    
    for expense in expenses:
        writer.writerow([
            expense.title,
            expense.category.name if expense.category else '',
            float(expense.amount),
            expense.date.strftime('%Y-%m-%d'),
            expense.status,
            expense.description or '',
            expense.created_by.get_full_name() if expense.created_by else ''
        ])
    
    return response




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




# ============================================
# PRICE CHECK VIEWS
# ============================================

@login_required
def price_check(request):
    """
    Price check view - Search product by name, SKU, barcode, size, or color
    Displays selling price and best price
    """
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    context = {
        'tenant': tenant,
        'active_tab': 'price_check',
    }
    return render(request, 'fashion_master/price_check.html', context)


@login_required
def price_check_search(request):
    """
    AJAX endpoint for price check - Search product by identifier
    Returns: product details with selling_price and best_price
    """
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'error': 'Please enter a search term'}, status=400)
    
    if len(query) < 2:
        return JsonResponse({'error': 'Please enter at least 2 characters'}, status=400)
    
    try:
        # Search by SKU, Barcode, Name, Size, or Color
        products = FashionProduct.objects.filter(
            tenant=tenant,
            is_active=True
        ).filter(
            Q(sku_code__icontains=query) |
            Q(barcode__icontains=query) |
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(size__icontains=query) |
            Q(color__icontains=query) |
            Q(style_code__icontains=query)
        ).select_related('category')[:10]
        
        if products.exists():
            results = []
            for product in products:
                results.append({
                    'id': product.id,
                    'sku_code': product.sku_code,
                    'name': product.name,
                    'brand': product.brand,
                    'size': product.size,
                    'color': product.color,
                    'selling_price': float(product.selling_price),
                    'best_price': float(product.best_price) if product.best_price else None,
                    'buying_price': float(product.buying_price),
                    'available_quantity': product.available_quantity,
                    'category': product.category.name if product.category else None,
                    'image': product.image.url if product.image else None,
                })
            
            return JsonResponse({
                'success': True,
                'found': True,
                'type': 'list',
                'data': results,
                'count': len(results),
                'message': f'Found {len(results)} products matching "{query}"'
            })
        
        # Search by SKU in variants
        variants = FashionVariant.objects.filter(
            tenant=tenant,
            is_active=True
        ).filter(
            Q(sku__icontains=query) |
            Q(barcode__icontains=query)
        ).select_related('product')[:5]
        
        if variants.exists():
            results = []
            for variant in variants:
                results.append({
                    'id': variant.id,
                    'type': 'variant',
                    'sku': variant.sku,
                    'product_name': variant.product.name,
                    'size': variant.size,
                    'color': variant.color,
                    'selling_price': float(variant.selling_price or variant.product.selling_price),
                    'best_price': float(variant.product.best_price) if variant.product.best_price else None,
                    'available_quantity': variant.available_quantity,
                    'image': variant.image.url if variant.image else None,
                })
            
            return JsonResponse({
                'success': True,
                'found': True,
                'type': 'variant',
                'data': results,
                'count': len(results),
                'message': f'Found {len(results)} variants matching "{query}"'
            })
        
        # No results found
        return JsonResponse({
            'success': True,
            'found': False,
            'message': f'No product found for "{query}"'
        })
        
    except Exception as e:
        logger.error(f"Price check error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================
# PRODUCT SEARCH VIEWS
# ============================================

@login_required
def product_search(request):
    """
    Product search page - Search products by name, SKU, brand, etc.
    """
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('fashion_master:dashboard')
    
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    size = request.GET.get('size', '')
    color = request.GET.get('color', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    
    products = FashionProduct.objects.filter(tenant=tenant, is_active=True)
    
    # Apply filters
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(sku_code__icontains=search_query) |
            Q(barcode__icontains=search_query) |
            Q(size__icontains=search_query) |
            Q(color__icontains=search_query) |
            Q(style_code__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    if size:
        products = products.filter(size__icontains=size)
    
    if color:
        products = products.filter(color__icontains=color)
    
    if min_price:
        try:
            products = products.filter(selling_price__gte=Decimal(min_price))
        except:
            pass
    
    if max_price:
        try:
            products = products.filter(selling_price__lte=Decimal(max_price))
        except:
            pass
    
    # Get categories for filter
    categories = FashionCategory.objects.filter(tenant=tenant, is_active=True)
    
    # Get unique sizes and colors for filters
    sizes = products.values_list('size', flat=True).distinct().order_by('size')
    colors = products.values_list('color', flat=True).distinct().order_by('color')
    
    # Pagination
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'products': page_obj,
        'categories': categories,
        'sizes': sizes,
        'colors': colors,
        'search_query': search_query,
        'selected_category': category_id,
        'selected_size': size,
        'selected_color': color,
        'min_price': min_price,
        'max_price': max_price,
        'active_tab': 'product_search',
    }
    return render(request, 'fashion_master/product_search.html', context)


@login_required
def product_search_ajax(request):
    """
    AJAX endpoint for product search - Live suggestions
    """
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'results': []})
    
    products = FashionProduct.objects.filter(
        tenant=tenant,
        is_active=True
    ).filter(
        Q(name__icontains=query) |
        Q(brand__icontains=query) |
        Q(sku_code__icontains=query) |
        Q(barcode__icontains=query) |
        Q(size__icontains=query) |
        Q(color__icontains=query)
    ).select_related('category')[:20]
    
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'sku_code': product.sku_code,
            'name': product.name,
            'brand': product.brand,
            'size': product.size,
            'color': product.color,
            'selling_price': float(product.selling_price),
            'buying_price': float(product.buying_price),
            'available_quantity': product.available_quantity,
            'category': product.category.name if product.category else None,
            'image': product.image.url if product.image else None,
            'url': f"/fashion/products/{product.id}/"
        })
    
    return JsonResponse({'results': results})


