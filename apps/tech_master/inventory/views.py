# apps/tech_master/inventory/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, F, Sum, Count
from django.utils import timezone
from decimal import Decimal
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
import json
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings

# ✅ Import once from each location
from apps.shared.powersync.sync_manager import SyncManager
from apps.shared.tenants.models import Tenant, SyncQueue
from apps.shared.users.models import User
from apps.shared.tenants.decorators import check_product_limit, check_branch_limit

from apps.tech_master.inventory.models import (
    Product, ProductUnit, Branch, Category, Supplier, 
    StockEntry, BranchTransfer, BranchStock
)

logger = logging.getLogger(__name__)


# ============================================
# BRANCH MANAGEMENT
# ============================================

@login_required
def branch_list(request):
    """List all branches for the tenant"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    branches = Branch.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    context = {
        'tenant': tenant,
        'branches': branches,
    }
    return render(request, 'tech_master/inventory/branch_list.html', context)


@login_required
@check_branch_limit
def add_branch(request):
    """Add a new branch"""
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
            return redirect('tech_master:add_branch')
        
        if Branch.objects.filter(tenant=tenant, code=code).exists():
            messages.error(request, f'Branch code "{code}" already exists')
            return redirect('tech_master:add_branch')
        
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
        # ✅ FIX: Add tech_master: namespace
        return redirect('tech_master:branch_list')
    
    context = {'tenant': tenant}
    return render(request, 'tech_master/inventory/add_branch.html', context)


@login_required
def edit_branch(request, branch_id):
    """Edit an existing branch"""
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
            return redirect('tech_master:edit_branch', branch_id=branch.id)
        
        if Branch.objects.filter(tenant=tenant, code=code).exclude(id=branch.id).exists():
            messages.error(request, f'Branch code "{code}" already exists')
            return redirect('tech_master:edit_branch', branch_id=branch.id)
        
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
        return redirect('tech_master:branch_list')
    
    context = {
        'tenant': tenant,
        'branch': branch,
    }
    return render(request, 'tech_master/inventory/edit_branch.html', context)


@login_required
def delete_branch(request, branch_id):
    """Delete a branch"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
    
    if branch.products.exists():
        messages.error(request, f'Cannot delete "{branch.name}" because it has {branch.products.count()} product(s). Move or reassign products first.')
        return redirect('tech_master:branch_list')
    
    if branch.product_units.exists():
        messages.error(request, f'Cannot delete "{branch.name}" because it has {branch.product_units.count()} product unit(s). Move or reassign units first.')
        return redirect('tech_master:branch_list')
    
    branch_name = branch.name
    branch.delete()
    messages.success(request, f'Branch "{branch_name}" deleted successfully!')
    return redirect('tech_master:branch_list')


@login_required
def assign_branch_manager(request):
    """Assign a manager to a branch - Admin only"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    # Get all branches for this tenant
    branches = Branch.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    # Get all managers and admins for this tenant (who can be assigned as branch managers)
    users = User.objects.filter(
        tenant=tenant,
        is_active=True
    ).filter(
        Q(role='manager') | Q(role='admin') | Q(role='tenant_admin')
    ).order_by('username')
    
    if request.method == 'POST':
        branch_id = request.POST.get('branch_id')
        user_id = request.POST.get('user_id')
        action = request.POST.get('action', 'assign')  # 'assign' or 'remove'
        
        if not branch_id:
            messages.error(request, 'Please select a branch')
            return redirect('tech_master:assign_branch_manager')
        
        branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
        
        if action == 'assign':
            if not user_id:
                messages.error(request, 'Please select a user to assign')
                return redirect('tech_master:assign_branch_manager')
            
            user = get_object_or_404(User, id=user_id, tenant=tenant)
            
            # Update branch manager
            branch.manager_name = user.get_full_name() or user.username
            branch.save()
            
            messages.success(request, f'Branch "{branch.name}" assigned to {user.get_full_name() or user.username} successfully!')
            
        elif action == 'remove':
            # Remove manager from branch
            branch.manager_name = ''
            branch.save()
            
            messages.success(request, f'Manager removed from "{branch.name}" successfully!')
        
        return redirect('tech_master:assign_branch_manager')
    
    # Get current branch managers for display
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
    return render(request, 'tech_master/inventory/assign_branch_manager.html', context)





# ============================================
# PRODUCT CATEGORY MANAGEMENT
# ============================================

@login_required
def category_list(request):
    """List all product categories for the tenant"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    categories = Category.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    context = {
        'tenant': tenant,
        'categories': categories,
    }
    return render(request, 'tech_master/inventory/category_list.html', context)


@login_required
def add_category(request):
    """Add a new product category"""
    tenant = request.user.tenant
    
    if request.method == 'POST':
        name = request.POST.get('name')
        item_type = request.POST.get('item_type', 'single')
        identifier_type = request.POST.get('identifier_type', 'imei')
        description = request.POST.get('description')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name:
            messages.error(request, 'Category name is required')
            return redirect('tech_master:add_category')
        
        if Category.objects.filter(tenant=tenant, name__iexact=name).exists():
            messages.error(request, f'Category "{name}" already exists')
            return redirect('tech_master:add_category')
        
        category = Category.objects.create(
            tenant=tenant,
            name=name,
            item_type=item_type,
            identifier_type=identifier_type,
            description=description,
            is_active=is_active
        )
        
        messages.success(request, f'Category "{category.name}" created successfully!')
        return redirect('tech_master:category_list')
    
    context = {'tenant': tenant}
    return render(request, 'tech_master/inventory/add_category.html', context)


@login_required
def edit_category(request, category_id):
    """Edit an existing product category"""
    tenant = request.user.tenant
    category = get_object_or_404(Category, id=category_id, tenant=tenant)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        item_type = request.POST.get('item_type')
        identifier_type = request.POST.get('identifier_type')
        description = request.POST.get('description')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name:
            messages.error(request, 'Category name is required')
            return redirect('tech_master:edit_category', category_id=category.id)
        
        if Category.objects.filter(tenant=tenant, name__iexact=name).exclude(id=category.id).exists():
            messages.error(request, f'Category "{name}" already exists')
            return redirect('tech_master:edit_category', category_id=category.id)
        
        category.name = name
        category.item_type = item_type
        category.identifier_type = identifier_type
        category.description = description
        category.is_active = is_active
        category.save()
        
        messages.success(request, f'Category "{category.name}" updated successfully!')
        return redirect('tech_master:category_list')
    
    context = {
        'tenant': tenant,
        'category': category,
    }
    return render(request, 'tech_master/inventory/edit_category.html', context)


@login_required
def delete_category(request, category_id):
    """Delete a product category"""
    tenant = request.user.tenant
    category = get_object_or_404(Category, id=category_id, tenant=tenant)
    
    if category.products.exists():
        product_count = category.products.count()
        messages.error(request, f'Cannot delete "{category.name}" because it has {product_count} product(s).')
        return redirect('tech_master:category_list')
    
    category_name = category.name
    category.delete()
    messages.success(request, f'Category "{category_name}" deleted successfully!')
    return redirect('tech_master:category_list')


# ============================================
# SUPPLIER MANAGEMENT
# ============================================

@login_required
def supplier_list(request):
    """List all suppliers"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    suppliers = Supplier.objects.filter(tenant=tenant, is_active=True).order_by('name')
    
    context = {
        'tenant': tenant,
        'suppliers': suppliers,
        'active_tab': 'suppliers',
    }
    return render(request, 'tech_master/inventory/supplier_list.html', context)


@login_required
def add_supplier(request):
    """Add a new supplier"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        contact_person = request.POST.get('contact_person', '')
        phone = request.POST.get('phone')
        email = request.POST.get('email', '')
        address = request.POST.get('address', '')
        tax_id = request.POST.get('tax_id', '')
        payment_terms = request.POST.get('payment_terms', '')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not phone:
            messages.error(request, 'Supplier name and phone are required')
            return redirect('tech_master:add_supplier')
        
        if Supplier.objects.filter(tenant=tenant, name__iexact=name).exists():
            messages.error(request, f'Supplier "{name}" already exists')
            return redirect('tech_master:add_supplier')
        
        supplier = Supplier.objects.create(
            tenant=tenant,
            name=name,
            contact_person=contact_person,
            phone=phone,
            email=email,
            address=address,
            tax_id=tax_id,
            payment_terms=payment_terms,
            is_active=is_active
        )
        
        messages.success(request, f'Supplier "{supplier.name}" created successfully!')
        return redirect('tech_master:supplier_list')
    
    context = {'tenant': tenant}
    return render(request, 'tech_master/inventory/add_supplier.html', context)


@login_required
def edit_supplier(request, supplier_id):
    """Edit a supplier"""
    tenant = request.user.tenant
    supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        contact_person = request.POST.get('contact_person', '')
        phone = request.POST.get('phone')
        email = request.POST.get('email', '')
        address = request.POST.get('address', '')
        tax_id = request.POST.get('tax_id', '')
        payment_terms = request.POST.get('payment_terms', '')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name or not phone:
            messages.error(request, 'Supplier name and phone are required')
            return redirect('tech_master:edit_supplier', supplier_id=supplier.id)
        
        if Supplier.objects.filter(tenant=tenant, name__iexact=name).exclude(id=supplier.id).exists():
            messages.error(request, f'Supplier "{name}" already exists')
            return redirect('tech_master:edit_supplier', supplier_id=supplier.id)
        
        supplier.name = name
        supplier.contact_person = contact_person
        supplier.phone = phone
        supplier.email = email
        supplier.address = address
        supplier.tax_id = tax_id
        supplier.payment_terms = payment_terms
        supplier.is_active = is_active
        supplier.save()
        
        messages.success(request, f'Supplier "{supplier.name}" updated successfully!')
        return redirect('tech_master:supplier_list')
    
    context = {
        'tenant': tenant,
        'supplier': supplier,
    }
    return render(request, 'tech_master/inventory/edit_supplier.html', context)


@login_required
def delete_supplier(request, supplier_id):
    """Delete a supplier"""
    tenant = request.user.tenant
    supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)
    
    if supplier.products.exists():
        messages.error(request, f'Cannot delete "{supplier.name}" because it has {supplier.products.count()} product(s).')
        return redirect('tech_master:supplier_list')
    
    supplier_name = supplier.name
    supplier.delete()
    messages.success(request, f'Supplier "{supplier_name}" deleted successfully!')
    return redirect('tech_master:supplier_list')


# ============================================
# INVENTORY MANAGEMENT
# ============================================

@login_required
def add_product(request):
    """Redirect to product selection"""
    return redirect('tech_master:add_product_selection')


@login_required
def transfer_product(request, product_id):
    """Transfer product to another branch (wrapper for move_product_ownership)"""
    return redirect('tech_master:move_product_ownership')


@login_required
def generate_label_pdf(request):
    """Generate PDF with barcode labels"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    product_ids = request.GET.getlist('product_ids')
    products = Product.objects.filter(tenant=tenant, id__in=product_ids) if product_ids else []
    
    # Generate PDF labels (you'll need to implement PDF generation)
    # For now, render a simple template
    context = {
        'tenant': tenant,
        'products': products,
    }
    return render(request, 'tech_master/inventory/generate_label_pdf.html', context)


@login_required
def get_inventory_item_api(request, item_id):
    """API endpoint to get inventory item details"""
    tenant = request.user.tenant
    
    # Helper function to safely convert to float
    def safe_float(value):
        """Safely convert Decimal or None to float"""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    
    # Try to find the item in Product or ProductUnit
    try:
        product = Product.objects.get(id=item_id, tenant=tenant)
        data = {
            'id': product.id,
            'type': 'product',
            'sku_code': product.sku_code,
            'name': product.name,
            'brand': product.brand,
            'model': product.model,
            'buying_price': safe_float(product.buying_price),
            'selling_price': safe_float(product.selling_price),
            'best_price': safe_float(product.best_price),
            'available_quantity': product.available_quantity,
            'total_quantity': product.total_quantity,
            'category_name': product.category.name if product.category else None,
            'branch_name': product.branch.name if product.branch else None,
            'is_active': product.is_active,
        }
        return JsonResponse(data)
    except Product.DoesNotExist:
        pass
    
    try:
        unit = ProductUnit.objects.get(id=item_id, tenant=tenant)
        
        # Safely get prices
        buying_price = unit.unit_buying_price or unit.product.buying_price
        selling_price = unit.unit_selling_price or unit.product.selling_price
        best_price = unit.best_price or unit.product.best_price
        
        data = {
            'id': unit.id,
            'type': 'unit',
            'product_id': unit.product.id,
            'product_sku': unit.product.sku_code,
            'product_name': unit.product.name,
            'imei_number': unit.imei_number,
            'serial_number': unit.serial_number,
            'buying_price': safe_float(buying_price),
            'selling_price': safe_float(selling_price),
            'best_price': safe_float(best_price),
            'status': unit.status,
            'condition': unit.condition,
            'branch_name': unit.branch.name if unit.branch else None,
            'current_owner': unit.current_owner.get_full_name() if unit.current_owner else None,
        }
        return JsonResponse(data)
    except ProductUnit.DoesNotExist:
        pass
    
    return JsonResponse({'error': 'Item not found'}, status=404)


@login_required
def update_inventory_item(request, item_id):
    """Update inventory item (handles both Product and ProductUnit)"""
    tenant = request.user.tenant
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    # Try Product first
    try:
        product = Product.objects.get(id=item_id, tenant=tenant)
        
        # Update product fields with safe conversion
        if 'name' in data:
            product.name = data['name']
        if 'brand' in data:
            product.brand = data['brand']
        if 'model' in data:
            product.model = data['model']
        if 'buying_price' in data:
            try:
                product.buying_price = Decimal(str(data['buying_price']))
            except (TypeError, ValueError):
                pass
        if 'selling_price' in data:
            try:
                product.selling_price = Decimal(str(data['selling_price']))
            except (TypeError, ValueError):
                pass
        if 'reorder_level' in data:
            try:
                product.reorder_level = int(data['reorder_level'])
            except (TypeError, ValueError):
                pass
        if 'is_active' in data:
            product.is_active = bool(data['is_active'])
        
        product.save()
        
        # Queue sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='Product',
                    object_id=str(product.id),
                    operation='UPDATE',
                    data={
                        'id': product.id,
                        'sku_code': product.sku_code,
                        'name': product.name,
                        'brand': product.brand,
                        'model': product.model,
                        'buying_price': str(product.buying_price),
                        'selling_price': str(product.selling_price),
                        'reorder_level': product.reorder_level,
                        'is_active': product.is_active,
                        'tenant_id': tenant.id,
                    },
                    priority=5
                )
            except Exception as e:
                logger.error(f"Failed to queue Product sync: {e}")
        
        return JsonResponse({
            'success': True, 
            'message': 'Product updated successfully',
            'product': {
                'id': product.id,
                'sku_code': product.sku_code,
                'name': product.name,
                'buying_price': float(product.buying_price),
                'selling_price': float(product.selling_price),
            }
        })
    except Product.DoesNotExist:
        pass
    
    # Try ProductUnit
    try:
        unit = ProductUnit.objects.get(id=item_id, tenant=tenant)
        
        # Update unit fields
        if 'imei_number' in data:
            unit.imei_number = data['imei_number'] if data['imei_number'] else None
        if 'serial_number' in data:
            unit.serial_number = data['serial_number'] if data['serial_number'] else None
        if 'status' in data:
            unit.status = data['status']
        if 'condition' in data:
            unit.condition = data['condition']
        if 'buying_price' in data:
            try:
                unit.unit_buying_price = Decimal(str(data['buying_price']))
            except (TypeError, ValueError):
                pass
        if 'selling_price' in data:
            try:
                unit.unit_selling_price = Decimal(str(data['selling_price']))
            except (TypeError, ValueError):
                pass
        if 'branch_id' in data:
            try:
                branch = Branch.objects.get(id=data['branch_id'], tenant=tenant)
                unit.branch = branch
            except Branch.DoesNotExist:
                pass
        
        unit.save()
        unit.product.update_quantities()
        
        # Queue sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='ProductUnit',
                    object_id=str(unit.id),
                    operation='UPDATE',
                    data={
                        'id': unit.id,
                        'product_id': unit.product_id,
                        'imei_number': unit.imei_number,
                        'serial_number': unit.serial_number,
                        'status': unit.status,
                        'branch_id': unit.branch_id,
                        'selling_price': str(unit.unit_selling_price) if unit.unit_selling_price else None,
                        'tenant_id': tenant.id,
                    },
                    priority=7
                )
            except Exception as e:
                logger.error(f"Failed to queue ProductUnit sync: {e}")
        
        return JsonResponse({
            'success': True, 
            'message': 'Unit updated successfully',
            'unit': {
                'id': unit.id,
                'imei_number': unit.imei_number,
                'serial_number': unit.serial_number,
                'status': unit.status,
                'selling_price': float(unit.unit_selling_price) if unit.unit_selling_price else None,
            }
        })
    except ProductUnit.DoesNotExist:
        pass
    
    return JsonResponse({'error': 'Item not found'}, status=404)


@login_required
def delete_inventory_item(request, item_id):
    """Delete inventory item (handles both Product and ProductUnit)"""
    tenant = request.user.tenant
    
    try:
        product = Product.objects.get(id=item_id, tenant=tenant)
        product_name = product.name
        product.delete()
        return JsonResponse({'success': True, 'message': f'Product "{product_name}" deleted'})
    except Product.DoesNotExist:
        pass
    
    try:
        unit = ProductUnit.objects.get(id=item_id, tenant=tenant)
        product = unit.product
        unit.delete()
        product.update_quantities()
        return JsonResponse({'success': True, 'message': 'Unit deleted successfully'})
    except ProductUnit.DoesNotExist:
        pass
    
    return JsonResponse({'error': 'Item not found'}, status=404)


@login_required
def move_inventory_item(request, item_id):
    """Move inventory item to another branch"""
    tenant = request.user.tenant
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        unit = ProductUnit.objects.get(id=item_id, tenant=tenant)
        data = json.loads(request.body)
        branch_id = data.get('branch_id')
        
        if branch_id:
            branch = Branch.objects.filter(id=branch_id, tenant=tenant).first()
            if branch:
                old_branch = unit.branch
                unit.branch = branch
                unit.save()
                
                # Create transfer record
                BranchTransfer.objects.create(
                    tenant=tenant,
                    product_unit=unit,
                    from_branch=old_branch,
                    to_branch=branch,
                    transferred_by=request.user,
                    reason=data.get('reason', ''),
                    status='completed'
                )
                
                return JsonResponse({'success': True, 'message': 'Unit moved successfully'})
        
        return JsonResponse({'error': 'Invalid branch'}, status=400)
    except ProductUnit.DoesNotExist:
        return JsonResponse({'error': 'Unit not found'}, status=404)





# ============================================
# PRODUCT MANAGEMENT
# ============================================

@login_required
def product_list(request):
    """List all products"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    category_id = request.GET.get('category')
    search_query = request.GET.get('q', '')
    
    products = Product.objects.filter(tenant=tenant, is_active=True).select_related('category')
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(model__icontains=search_query) |
            Q(sku_code__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    product_list = []
    for product in products:
        if isinstance(product.specifications, dict):
            specs = product.specifications
        else:
            try:
                specs = json.loads(product.specifications) if product.specifications else {}
            except:
                specs = {}
        
        product.specs_display = specs
        product.primary_spec = ""
        
        if specs:
            spec_parts = []
            if specs.get('ram'):
                spec_parts.append(str(specs.get('ram')))
            if specs.get('storage'):
                spec_parts.append(str(specs.get('storage')))
            if specs.get('color'):
                spec_parts.append(str(specs.get('color')))
            product.primary_spec = " | ".join(spec_parts) if spec_parts else "-"
        
        product.stock_status = 'In Stock'
        product.stock_badge = 'success'
        if product.is_low_stock:
            product.stock_status = 'Low Stock'
            product.stock_badge = 'warning'
        elif product.is_out_of_stock:
            product.stock_status = 'Out of Stock'
            product.stock_badge = 'danger'
        
        product_list.append(product)
    
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    
    paginator = Paginator(product_list, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'products': page_obj,
        'categories': categories,
        'selected_category': category_id,
        'search_query': search_query,
        'tenant': tenant,
        'total_products': products.count(),
    }
    return render(request, 'tech_master/inventory/product_list.html', context)


@login_required
def product_detail(request, product_id):
    """View product details with all inventory units"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    product = get_object_or_404(
        Product.objects.select_related('category', 'branch', 'supplier'),
        id=product_id, 
        tenant=tenant
    )
    
    units = ProductUnit.objects.filter(
        product=product,
        tenant=tenant
    ).select_related('branch', 'supplier').order_by('-created_at')
    
    for unit in units:
        unit.display_buying_price = unit.unit_buying_price if unit.unit_buying_price else product.buying_price
        unit.display_selling_price = unit.unit_selling_price if unit.unit_selling_price else product.selling_price
        
        if unit.imei_number:
            unit.display_identifier = f"IMEI: {unit.imei_number}"
        elif unit.serial_number:
            unit.display_identifier = f"S/N: {unit.serial_number}"
        else:
            unit.display_identifier = "No identifier"
    
    context = {
        'product': product,
        'units': units,
        'units_count': units.count(),
        'available_units_count': units.filter(status='available').count(),
        'sold_units_count': units.filter(status='sold').count(),
        'damaged_units_count': units.filter(status='damaged').count(),
        'reserved_units_count': units.filter(status='reserved').count(),
        'tenant': tenant,
    }
    return render(request, 'tech_master/inventory/product_detail.html', context)


@login_required
@check_product_limit
def add_product_selection(request):
    """Product type selection page"""
    tenant = request.user.tenant
    return render(request, 'tech_master/inventory/add_product_selection.html', {'tenant': tenant})


@login_required
@check_product_limit
def add_single_product(request):
    """Add single product (IMEI based)"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    suppliers = Supplier.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        branch_id = request.POST.get('branch_id')
        supplier_id = request.POST.get('supplier_id')
        name = request.POST.get('name', '').strip()
        model = request.POST.get('model', '').strip()
        brand = request.POST.get('brand', '').strip()
        category_id = request.POST.get('category_id')
        specifications = request.POST.get('specifications', '')
        color = request.POST.get('color', '')
        buying_price = request.POST.get('buying_price', 0)
        selling_price = request.POST.get('selling_price', 0)
        best_price = request.POST.get('best_price')
        reorder_level = request.POST.get('reorder_level', 5)
        warranty_months = request.POST.get('warranty_months', 12)
        
        imei_textarea = request.POST.get('imei_textarea', '')
        identifiers = [id.strip() for id in imei_textarea.split('\n') if id.strip()]
        
        if not branch_id:
            messages.error(request, 'Please select a branch')
            return redirect('tech_master:add_single_product')
        
        branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
        
        supplier = None
        if supplier_id:
            supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)
        
        if not name:
            messages.error(request, 'Product name is required')
            return redirect('tech_master:add_single_product')
        
        if not identifiers:
            messages.error(request, 'Please enter at least one IMEI or Serial Number')
            return redirect('tech_master:add_single_product')
        
        specs_dict = {}
        if specifications:
            specs_dict['description'] = specifications
        if color:
            specs_dict['color'] = color
        
        product = Product.objects.filter(
            tenant=tenant,
            name=name,
            brand=brand,
            model=model
        ).first()
        
        if not product:
            product = Product.objects.create(
                tenant=tenant,
                name=name,
                brand=brand,
                model=model,
                category_id=category_id if category_id else None,
                branch=branch,
                supplier=supplier,
                specifications=specs_dict,
                buying_price=float(buying_price) if buying_price else 0,
                selling_price=float(selling_price) if selling_price else 0,
                best_price=float(best_price) if best_price else None,
                reorder_level=int(reorder_level),
                warranty_months=int(warranty_months),
                is_active=True
            )
            messages.success(request, f'Product "{product.name}" created successfully with SKU: {product.sku_code}')
        else:
            messages.info(request, f'Using existing product "{product.name}" (SKU: {product.sku_code})')
        
        created_count = 0
        errors = []
        
        for identifier in identifiers:
            if identifier:
                is_imei = len(identifier) == 15 and identifier.isdigit()
                
                existing = None
                if is_imei:
                    existing = ProductUnit.objects.filter(tenant=tenant, imei_number=identifier).first()
                else:
                    existing = ProductUnit.objects.filter(tenant=tenant, serial_number=identifier).first()
                
                if existing:
                    errors.append(f'Identifier already exists: {identifier}')
                    continue
                
                ProductUnit.objects.create(
                    tenant=tenant,
                    product=product,
                    branch=branch,
                    supplier=supplier,
                    imei_number=identifier if is_imei else None,
                    serial_number=identifier if not is_imei else None,
                    unit_buying_price=float(buying_price) if buying_price else None,
                    unit_selling_price=float(selling_price) if selling_price else None,
                    best_price=float(best_price) if best_price else None,
                    status='available'
                )
                created_count += 1
        
        product.update_quantities()
        
        if created_count > 0:
            messages.success(request, f'{created_count} unit(s) added to {product.name}')
        
        if errors:
            for error in errors[:5]:
                messages.warning(request, error)
        
        return redirect('tech_master:product_detail', product_id=product.id)
    
    context = {
        'branches': branches,
        'categories': categories,
        'suppliers': suppliers,
        'tenant': tenant,
    }
    return render(request, 'tech_master/inventory/add_single_product.html', context)


@login_required
@check_product_limit
def add_bulk_product(request):
    """Add bulk product"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    suppliers = Supplier.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        branch_id = request.POST.get('branch_id')
        supplier_id = request.POST.get('supplier_id')
        name = request.POST.get('name', '').strip()
        model = request.POST.get('model', '').strip()
        brand = request.POST.get('brand', '').strip()
        category_id = request.POST.get('category_id')
        specifications = request.POST.get('specifications', '')
        color = request.POST.get('color', '')
        buying_price = request.POST.get('buying_price', 0)
        selling_price = request.POST.get('selling_price', 0)
        best_price = request.POST.get('best_price')
        barcode = request.POST.get('barcode', '').strip().upper()
        stock_quantity = int(request.POST.get('stock_quantity', 1))
        reorder_level = request.POST.get('reorder_level', 5)
        warranty_months = request.POST.get('warranty_months', 12)
        
        if not branch_id:
            messages.error(request, 'Please select a branch')
            return redirect('tech_master:add_bulk_product')
        
        branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
        
        supplier = None
        if supplier_id:
            supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)
        
        if not name:
            messages.error(request, 'Product name is required')
            return redirect('tech_master:add_bulk_product')
        
        if not barcode:
            messages.error(request, 'Barcode is required')
            return redirect('tech_master:add_bulk_product')
        
        if stock_quantity <= 0:
            messages.error(request, 'Stock quantity must be greater than 0')
            return redirect('tech_master:add_bulk_product')
        
        specs_dict = {}
        if specifications:
            specs_dict['description'] = specifications
        if color:
            specs_dict['color'] = color
        
        product = Product.objects.filter(tenant=tenant, barcode=barcode).first()
        
        if product:
            product.bulk_quantity += stock_quantity
            product.total_quantity += stock_quantity
            product.available_quantity += stock_quantity
            product.save()
            messages.success(request, f'Added {stock_quantity} units to existing product "{product.name}" (SKU: {product.sku_code})')
        else:
            product = Product.objects.create(
                tenant=tenant,
                name=name,
                brand=brand,
                model=model,
                barcode=barcode,
                category_id=category_id if category_id else None,
                branch=branch,
                supplier=supplier,
                specifications=specs_dict,
                buying_price=float(buying_price) if buying_price else 0,
                selling_price=float(selling_price) if selling_price else 0,
                best_price=float(best_price) if best_price else None,
                bulk_quantity=stock_quantity,
                total_quantity=stock_quantity,
                available_quantity=stock_quantity,
                reorder_level=int(reorder_level),
                warranty_months=int(warranty_months),
                is_active=True
            )
            messages.success(request, f'Product "{product.name}" added successfully with SKU: {product.sku_code}')
        
        return redirect('tech_master:product_list')
    
    context = {
        'branches': branches,
        'categories': categories,
        'suppliers': suppliers,
        'tenant': tenant,
    }
    return render(request, 'tech_master/inventory/add_bulk_product.html', context)


@login_required
def edit_bulk_product(request, product_id):
    """Edit bulk product information"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    product = get_object_or_404(Product, id=product_id, tenant=tenant)
    
    if not product.category.is_bulk_item:
        messages.error(request, 'This is not a bulk product')
        return redirect('tech_master:product_detail', product_id=product.id)
    
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    suppliers = Supplier.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        brand = request.POST.get('brand', '').strip()
        model = request.POST.get('model', '').strip()
        category_id = request.POST.get('category_id')
        branch_id = request.POST.get('branch_id')
        supplier_id = request.POST.get('supplier_id')
        barcode = request.POST.get('barcode', '').strip().upper()
        buying_price = request.POST.get('buying_price', 0)
        selling_price = request.POST.get('selling_price', 0)
        best_price = request.POST.get('best_price')
        reorder_level = request.POST.get('reorder_level', 5)
        warranty_months = request.POST.get('warranty_months', 12)
        specifications = request.POST.get('specifications', '')
        color = request.POST.get('color', '')
        is_active = request.POST.get('is_active') == 'on'
        is_discontinued = request.POST.get('is_discontinued') == 'on'
        
        if not name:
            messages.error(request, 'Product name is required')
            return redirect('tech_master:edit_bulk_product', product_id=product.id)
        
        if not selling_price:
            messages.error(request, 'Selling price is required')
            return redirect('tech_master:edit_bulk_product', product_id=product.id)
        
        specs_dict = product.specifications or {}
        if specifications:
            specs_dict['description'] = specifications
        if color:
            specs_dict['color'] = color
        else:
            specs_dict.pop('color', None)
        
        product.name = name
        product.brand = brand
        product.model = model
        product.category_id = category_id if category_id else None
        product.branch_id = branch_id if branch_id else None
        product.supplier_id = supplier_id if supplier_id else None
        product.barcode = barcode if barcode else None
        product.buying_price = float(buying_price) if buying_price else 0
        product.selling_price = float(selling_price) if selling_price else 0
        product.best_price = float(best_price) if best_price else None
        product.reorder_level = int(reorder_level) if reorder_level else 5
        product.warranty_months = int(warranty_months) if warranty_months else 12
        product.specifications = specs_dict
        product.is_active = is_active
        product.is_discontinued = is_discontinued
        product.last_modified_by = request.user
        product.save()
        
        messages.success(request, f'Product "{product.name}" updated successfully!')
        return redirect('tech_master:product_detail', product_id=product.id)
    
    context = {
        'product': product,
        'branches': branches,
        'categories': categories,
        'suppliers': suppliers,
        'tenant': tenant,
    }
    return render(request, 'tech_master/inventory/edit_bulk_product.html', context)


@login_required
def restock_product(request, product_id):
    """Restock a bulk product"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    product = get_object_or_404(Product, id=product_id, tenant=tenant)
    
    if not product.category.is_bulk_item:
        messages.error(request, 'Restock is only available for bulk products')
        return redirect('tech_master:product_detail', product_id=product.id)
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 0))
        buying_price = request.POST.get('buying_price', product.buying_price)
        selling_price = request.POST.get('selling_price', product.selling_price)
        notes = request.POST.get('notes', '')
        
        if quantity <= 0:
            messages.error(request, 'Please enter a valid quantity')
            return redirect('tech_master:restock_product', product_id=product.id)
        
        product.bulk_quantity += quantity
        product.total_quantity += quantity
        product.available_quantity += quantity
        
        if float(buying_price) != product.buying_price:
            product.buying_price = float(buying_price)
        if float(selling_price) != product.selling_price:
            product.selling_price = float(selling_price)
        
        product.save()
        
        StockEntry.objects.create(
            tenant=tenant,
            product_sku=product,
            quantity=quantity,
            entry_type='purchase',
            unit_price=float(buying_price),
            total_amount=quantity * float(buying_price),
            notes=f"Restock: {notes}",
            created_by=request.user
        )
        
        messages.success(request, f'Successfully added {quantity} units to {product.name}')
        return redirect('tech_master:product_detail', product_id=product.id)
    
    context = {
        'product': product,
        'tenant': tenant,
    }
    return render(request, 'tech_master/inventory/restock_product.html', context)


@login_required
def edit_product(request, product_id):
    """Edit product information with sync support"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    product = get_object_or_404(Product, id=product_id, tenant=tenant)
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        brand = request.POST.get('brand', '')
        model = request.POST.get('model', '')
        buying_price = request.POST.get('buying_price', 0)
        selling_price = request.POST.get('selling_price', 0)
        reorder_level = request.POST.get('reorder_level', 5)
        category_id = request.POST.get('category_id')
        branch_id = request.POST.get('branch_id')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        is_discontinued = request.POST.get('is_discontinued') == 'on'
        
        if not name:
            messages.error(request, 'Product name is required')
            return redirect('tech_master:edit_product', product_id=product.id)
        
        if not selling_price:
            messages.error(request, 'Selling price is required')
            return redirect('tech_master:edit_product', product_id=product.id)
        
        specs_dict = product.specifications or {}
        if description:
            specs_dict['description'] = description
        
        # Track old values for sync
        old_data = {
            'name': product.name,
            'brand': product.brand,
            'model': product.model,
            'buying_price': float(product.buying_price),
            'selling_price': float(product.selling_price),
            'reorder_level': product.reorder_level,
            'is_active': product.is_active,
            'is_discontinued': product.is_discontinued,
        }
        
        product.name = name
        product.brand = brand
        product.model = model
        product.buying_price = float(buying_price)
        product.selling_price = float(selling_price)
        product.reorder_level = int(reorder_level)
        product.specifications = specs_dict
        product.is_active = is_active
        product.is_discontinued = is_discontinued
        
        if category_id:
            product.category_id = category_id
        if branch_id:
            product.branch_id = branch_id
        
        product.save()
        
        # ✅ Queue sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='Product',
                    object_id=str(product.id),
                    operation='UPDATE',
                    data={
                        'id': product.id,
                        'sku_code': product.sku_code,
                        'name': product.name,
                        'brand': product.brand,
                        'model': product.model,
                        'buying_price': str(product.buying_price),
                        'selling_price': str(product.selling_price),
                        'reorder_level': product.reorder_level,
                        'is_active': product.is_active,
                        'is_discontinued': product.is_discontinued,
                        'previous_data': old_data,
                        'tenant_id': tenant.id,
                    },
                    priority=5
                )
                logger.debug(f"✅ Queued Product update sync: {product.sku_code}")
            except Exception as e:
                logger.error(f"Failed to queue Product sync: {e}")
        
        messages.success(request, 'Product updated successfully!')
        return redirect('tech_master:product_detail', product_id=product.id)
    
    context = {
        'product': product,
        'branches': branches,
        'categories': categories,
        'tenant': tenant,
    }
    return render(request, 'tech_master/inventory/edit_product.html', context)


@login_required
def delete_product(request, product_id):
    """Delete product with sync support"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    product = get_object_or_404(Product, id=product_id, tenant=tenant)
    product_name = product.name
    
    # ✅ Queue deletion sync if offline
    if getattr(settings, 'OFFLINE_MODE', False):
        try:
            SyncQueue.objects.create(
                tenant_id=tenant.id,
                model_name='Product',
                object_id=str(product.id),
                operation='DELETE',
                data={
                    'id': product.id,
                    'sku_code': product.sku_code,
                    'name': product.name,
                    'tenant_id': tenant.id,
                }
            )
            logger.debug(f"✅ Queued Product deletion sync: {product.sku_code}")
        except Exception as e:
            logger.error(f"Failed to queue Product deletion sync: {e}")
    
    product.delete()
    messages.success(request, f'Product "{product_name}" deleted successfully')
    return redirect('tech_master:product_list')


# ============================================
# STOCK ADJUSTMENT VIEW
# ============================================

@login_required
def stock_adjustment(request, product_id):
    """Handle stock adjustments for bulk products"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    product = get_object_or_404(Product, id=product_id, tenant=tenant)
    
    if not product.category.is_bulk_item:
        messages.error(request, 'Stock adjustment is only available for bulk products')
        return redirect('tech_master:product_detail', product_id=product.id)
    
    if request.method == 'POST':
        adjustment_type = request.POST.get('adjustment_type')
        quantity = int(request.POST.get('quantity', 0))
        reason = request.POST.get('reason', '')
        
        if quantity <= 0:
            messages.error(request, 'Please enter a valid quantity')
            return redirect('tech_master:product_detail', product_id=product.id)
        
        if adjustment_type == 'add':
            # Add stock
            product.bulk_quantity += quantity
            product.total_quantity += quantity
            product.available_quantity += quantity
            
            StockEntry.objects.create(
                tenant=tenant,
                product_sku=product,
                quantity=quantity,
                entry_type='adjustment',
                unit_price=product.buying_price,
                total_amount=quantity * product.buying_price,
                notes=f"Stock addition: {reason}",
                created_by=request.user
            )
            messages.success(request, f'Added {quantity} units to {product.name}')
            
        elif adjustment_type == 'remove':
            # Remove stock
            if quantity > product.bulk_quantity:
                messages.error(request, f'Cannot remove {quantity} units. Only {product.bulk_quantity} units in stock.')
                return redirect('tech_master:product_detail', product_id=product.id)
            
            product.bulk_quantity -= quantity
            product.total_quantity -= quantity
            product.available_quantity -= quantity
            
            StockEntry.objects.create(
                tenant=tenant,
                product_sku=product,
                quantity=-quantity,
                entry_type='adjustment',
                unit_price=product.buying_price,
                total_amount=-(quantity * product.buying_price),
                notes=f"Stock removal: {reason}",
                created_by=request.user
            )
            messages.success(request, f'Removed {quantity} units from {product.name}')
            
        elif adjustment_type == 'damage':
            # Mark as damaged/loss
            if quantity > product.bulk_quantity:
                messages.error(request, f'Cannot mark {quantity} units as damaged. Only {product.bulk_quantity} units in stock.')
                return redirect('tech_master:product_detail', product_id=product.id)
            
            product.bulk_quantity -= quantity
            product.total_quantity -= quantity
            product.available_quantity -= quantity
            product.damaged_quantity += quantity
            
            StockEntry.objects.create(
                tenant=tenant,
                product_sku=product,
                quantity=-quantity,
                entry_type='damage',
                unit_price=product.buying_price,
                total_amount=-(quantity * product.buying_price),
                notes=f"Damaged/Loss: {reason}",
                created_by=request.user
            )
            messages.success(request, f'Marked {quantity} units as damaged/loss for {product.name}')
        
        product.save()
        return redirect('tech_master:product_detail', product_id=product.id)
    
    return redirect('tech_master:product_detail', product_id=product.id)


@login_required
def add_unit(request, product_id):
    """Add multiple units to a product"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    product = get_object_or_404(Product, id=product_id, tenant=tenant)
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        buying_price = request.POST.get('buying_price', product.buying_price)
        selling_price = request.POST.get('selling_price', product.selling_price)
        best_price = request.POST.get('best_price')
        branch_id = request.POST.get('branch_id')
        status = request.POST.get('status', 'available')
        warehouse_location = request.POST.get('warehouse_location', '')
        purchase_date = request.POST.get('purchase_date')
        notes = request.POST.get('notes', '')
        
        imei_text = request.POST.get('imei_list', '')
        imei_list = [imei.strip() for imei in imei_text.split('\n') if imei.strip()]
        
        serial_text = request.POST.get('serial_list', '')
        serial_list = [serial.strip() for serial in serial_text.split('\n') if serial.strip()]
        
        if not imei_list and not serial_list:
            messages.error(request, 'Please enter at least one IMEI or Serial Number')
            return redirect('tech_master:add_unit', product_id=product.id)
        
        branch = None
        if branch_id:
            branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
        
        created_count = 0
        errors = []
        
        for imei in imei_list:
            if imei:
                if len(imei) != 15 or not imei.isdigit():
                    errors.append(f'Invalid IMEI: {imei} (must be 15 digits)')
                    continue
                
                if ProductUnit.objects.filter(tenant=tenant, imei_number=imei).exists():
                    errors.append(f'IMEI already exists: {imei}')
                    continue
                
                ProductUnit.objects.create(
                    tenant=tenant,
                    product=product,
                    branch=branch,
                    imei_number=imei,
                    unit_buying_price=float(buying_price) if buying_price else None,
                    unit_selling_price=float(selling_price) if selling_price else None,
                    best_price=float(best_price) if best_price else None,
                    status=status,
                    warehouse_location=warehouse_location,
                    notes=notes,
                    purchase_date=purchase_date if purchase_date else timezone.now()
                )
                created_count += 1
        
        for serial in serial_list:
            if serial:
                if ProductUnit.objects.filter(tenant=tenant, serial_number=serial).exists():
                    errors.append(f'Serial number already exists: {serial}')
                    continue
                
                ProductUnit.objects.create(
                    tenant=tenant,
                    product=product,
                    branch=branch,
                    serial_number=serial,
                    unit_buying_price=float(buying_price) if buying_price else None,
                    unit_selling_price=float(selling_price) if selling_price else None,
                    best_price=float(best_price) if best_price else None,
                    status=status,
                    warehouse_location=warehouse_location,
                    notes=notes,
                    purchase_date=purchase_date if purchase_date else timezone.now()
                )
                created_count += 1
        
        product.update_quantities()
        
        if created_count > 0:
            messages.success(request, f'Successfully added {created_count} unit(s) to {product.name}')
        
        if errors:
            for error in errors[:5]:
                messages.warning(request, error)
        
        return redirect('tech_master:product_detail', product_id=product.id)
    
    context = {
        'product': product,
        'branches': branches,
        'tenant': tenant,
    }
    return render(request, 'tech_master/inventory/add_unit.html', context)


@login_required
def edit_unit(request, unit_id):
    """Edit an individual product unit with sync support"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    unit = get_object_or_404(ProductUnit, id=unit_id, tenant=tenant)
    product = unit.product
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        imei_number = request.POST.get('imei_number')
        serial_number = request.POST.get('serial_number')
        selling_price = request.POST.get('selling_price')
        status = request.POST.get('status')
        branch_id = request.POST.get('branch_id')
        
        # Track old values
        old_data = {
            'imei_number': unit.imei_number,
            'serial_number': unit.serial_number,
            'status': unit.status,
            'branch_id': unit.branch_id,
            'selling_price': float(unit.unit_selling_price) if unit.unit_selling_price else None,
        }
        
        # Validate
        if not imei_number and not serial_number:
            messages.error(request, 'IMEI or Serial Number is required')
            return redirect('tech_master:edit_unit', unit_id=unit.id)
        
        # Check uniqueness
        if imei_number and ProductUnit.objects.filter(tenant=tenant, imei_number=imei_number).exclude(id=unit.id).exists():
            messages.error(request, f'IMEI "{imei_number}" already exists')
            return redirect('tech_master:edit_unit', unit_id=unit.id)
        
        if serial_number and ProductUnit.objects.filter(tenant=tenant, serial_number=serial_number).exclude(id=unit.id).exists():
            messages.error(request, f'Serial number "{serial_number}" already exists')
            return redirect('tech_master:edit_unit', unit_id=unit.id)
        
        # Update unit
        unit.imei_number = imei_number if imei_number else None
        unit.serial_number = serial_number if serial_number else None
        unit.unit_selling_price = float(selling_price) if selling_price else None
        unit.status = status
        
        if branch_id:
            unit.branch_id = branch_id
        
        unit.save()
        product.update_quantities()
        
        # ✅ Queue sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='ProductUnit',
                    object_id=str(unit.id),
                    operation='UPDATE',
                    data={
                        'id': unit.id,
                        'product_id': unit.product_id,
                        'imei_number': unit.imei_number,
                        'serial_number': unit.serial_number,
                        'status': unit.status,
                        'branch_id': unit.branch_id,
                        'selling_price': str(unit.unit_selling_price) if unit.unit_selling_price else None,
                        'previous_data': old_data,
                        'tenant_id': tenant.id,
                    },
                    priority=7  # Status changes are important
                )
                logger.debug(f"✅ Queued ProductUnit update sync: {unit.unique_identifier}")
            except Exception as e:
                logger.error(f"Failed to queue ProductUnit sync: {e}")
        
        messages.success(request, 'Unit updated successfully')
        return redirect('tech_master:product_detail', product_id=product.id)
    
    context = {
        'unit': unit,
        'product': product,
        'branches': branches,
        'tenant': tenant,
    }
    return render(request, 'tech_master/inventory/edit_unit.html', context)


@login_required
def delete_unit(request, unit_id):
    """Delete an individual product unit with sync support"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    unit = get_object_or_404(ProductUnit, id=unit_id, tenant=tenant)
    product = unit.product
    
    # ✅ Queue deletion sync if offline
    if getattr(settings, 'OFFLINE_MODE', False):
        try:
            SyncQueue.objects.create(
                tenant_id=tenant.id,
                model_name='ProductUnit',
                object_id=str(unit.id),
                operation='DELETE',
                data={
                    'id': unit.id,
                    'imei_number': unit.imei_number,
                    'serial_number': unit.serial_number,
                    'product_sku': unit.product.sku_code,
                    'tenant_id': tenant.id,
                }
            )
            logger.debug(f"✅ Queued ProductUnit deletion sync: {unit.unique_identifier}")
        except Exception as e:
            logger.error(f"Failed to queue ProductUnit deletion sync: {e}")
    
    unit.delete()
    product.update_quantities()
    
    messages.success(request, 'Unit deleted successfully')
    return redirect('tech_master:product_detail', product_id=product.id)






# ============================================
# LOW STOCK ALERT
# ============================================

@login_required
def low_stock_alert(request):
    """Display products with low stock alerts"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'Tenant not found.')
        return redirect('dashboard')
    
    low_stock_products = Product.objects.filter(
        tenant=tenant,
        is_active=True,
        is_discontinued=False,
        available_quantity__lte=F('reorder_level'),
        available_quantity__gt=0
    ).select_related('category', 'supplier', 'branch').order_by('available_quantity')
    
    out_of_stock_products = Product.objects.filter(
        tenant=tenant,
        is_active=True,
        is_discontinued=False,
        available_quantity=0
    ).select_related('category', 'supplier', 'branch').order_by('sku_code')
    
    context = {
        'tenant': tenant,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'low_stock_count': low_stock_products.count(),
        'out_of_stock_count': out_of_stock_products.count(),
        'has_low_stock': low_stock_products.exists(),
        'has_out_of_stock': out_of_stock_products.exists(),
        'current_time': timezone.now(),
        'total_products': Product.objects.filter(tenant=tenant, is_active=True, is_discontinued=False).count(),
    }
    return render(request, 'tech_master/inventory/low_stock_alert.html', context)


# ============================================
# PRODUCT TRANSFER VIEWS
# ============================================


@login_required
def move_product_ownership(request):
    """Move products between branches or agents"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    # ✅ Handle POST request
    if request.method == 'POST':
        to_agent_id = request.POST.get('to_agent_id')
        product_ids = request.POST.getlist('product_ids')
        
        if not to_agent_id:
            messages.error(request, 'Please select a destination agent')
            return redirect('tech_master:move_product_ownership')
        
        if not product_ids:
            messages.error(request, 'Please select at least one product to move')
            return redirect('tech_master:move_product_ownership')
        
        # Get the destination agent
        to_agent = get_object_or_404(User, id=to_agent_id, tenant=tenant)
        
        moved_count = 0
        errors = []
        
        for product_id in product_ids:
            try:
                unit = ProductUnit.objects.get(
                    id=product_id,
                    tenant=tenant,
                    status='available'
                )
                
                # Check if unit is already assigned to this agent
                if unit.current_owner and unit.current_owner.id == to_agent.id:
                    errors.append(f'Unit {unit.imei_number or unit.serial_number} is already assigned to {to_agent.get_full_name()}')
                    continue
                
                # Move the unit
                unit.current_owner = to_agent
                unit.assigned_date = timezone.now()
                unit.assigned_by = request.user
                unit.save()
                moved_count += 1
                
            except ProductUnit.DoesNotExist:
                errors.append(f'Product unit {product_id} not found or not available')
            except Exception as e:
                errors.append(f'Error moving unit {product_id}: {str(e)}')
        
        if moved_count > 0:
            messages.success(request, f'Successfully moved {moved_count} unit(s) to {to_agent.get_full_name()}')
        
        if errors:
            for error in errors[:5]:
                messages.warning(request, error)
        
        return redirect('tech_master:move_product_ownership')
    
    # ✅ GET request - show the form
    # Get all sales agents for this tenant
    sales_agents = User.objects.filter(
        tenant=tenant,
        role='sales_agent',
        is_active=True
    ).order_by('username')
    
    # ✅ For each agent, calculate the actual available stock count
    for agent in sales_agents:
        # ✅ Count only available and reserved units (not sold)
        agent.available_stock_count = ProductUnit.objects.filter(
            tenant=tenant,
            current_owner=agent,
            status__in=['available', 'reserved']  # ✅ EXCLUDE sold units
        ).count()
    
    # ✅ Get all product units that are available and assigned to agents
    product_units = ProductUnit.objects.filter(
        tenant=tenant,
        status='available'
    ).select_related(
        'product',
        'current_owner',
        'branch'
    ).order_by('product__name')
    
    context = {
        'tenant': tenant,
        'sales_agents': sales_agents,  # Now includes available_stock_count
        'products': product_units,
        'active_tab': 'transfer',
    }
    return render(request, 'tech_master/inventory/move_product_ownership.html', context)


@login_required
def assign_products_to_agent(request):
    """Assign products to sales agent"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    # ✅ Get all sales agents
    sales_agents = User.objects.filter(
        tenant=tenant,
        role='sales_agent',
        is_active=True
    ).order_by('username')
    
    # ✅ Get all unassigned product units (available and no current_owner)
    products = ProductUnit.objects.filter(
        tenant=tenant,
        status='available',
        current_owner__isnull=True  # Only unassigned units
    ).select_related(
        'product',
        'branch'
    ).order_by('product__name')
    
    # Format products for the template
    product_list = []
    for unit in products:
        product_list.append({
            'id': unit.id,
            'name': unit.product.name,
            'sku': unit.product.sku_code,
            'brand': unit.product.brand,
            'imei': unit.imei_number or unit.serial_number or 'No ID',
            'selling_price': float(unit.unit_selling_price or unit.product.selling_price),
            'branch_name': unit.branch.name if unit.branch else 'Main Shop',
        })
    
    context = {
        'tenant': tenant,
        'sales_agents': sales_agents,
        'products': product_list,
        'active_tab': 'assign',
    }
    return render(request, 'tech_master/inventory/assign_products.html', context)


# ============================================
# BARCODE VIEWS
# ============================================
@login_required
def barcode_label(request, product_id):
    """Generate barcode image for a product"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    product = get_object_or_404(Product, id=product_id, tenant=tenant)
    
    context = {
        'product': product,
        'barcode': product.sku_code,
        'tenant': tenant,
    }
    return render(request, 'tech_master/inventory/barcode_label.html', context)


@login_required
def barcode_labels_list(request):
    """List products with barcodes"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    products = Product.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'products': products,
        'active_tab': 'barcodes',
    }
    return render(request, 'tech_master/inventory/barcode_label_list.html', context)


@login_required
def print_labels(request):
    """Print barcode labels for selected products"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    product_ids = request.GET.getlist('product_ids')
    products = Product.objects.filter(tenant=tenant, id__in=product_ids) if product_ids else []
    
    context = {
        'tenant': tenant,
        'products': products,
    }
    return render(request, 'tech_master/inventory/print_labels.html', context)



@login_required
def bulk_print_labels(request):
    """Bulk print labels page - shows each unit individually"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    items = []
    
    # Get all products
    products = Product.objects.filter(tenant=tenant, is_active=True)
    
    for product in products:
        if product.category.is_single_item:
            # For single items, show each unit
            units = ProductUnit.objects.filter(
                tenant=tenant,
                product=product,
                status='available'
            )
            for unit in units:
                price = unit.unit_selling_price or product.selling_price
                items.append({
                    'id': unit.id,
                    'type': 'unit',
                    'name': product.name,
                    'identifier': unit.imei_number or unit.serial_number or product.sku_code,
                    'brand': product.brand,
                    'model': product.model,
                    'price': float(price),
                    'category': product.category.name if product.category else 'Uncategorized',
                    'is_single': True,
                })
        else:
            # For bulk items, show the product once
            items.append({
                'id': product.id,
                'type': 'product',
                'name': product.name,
                'identifier': product.barcode or product.sku_code,
                'brand': product.brand,
                'model': product.model,
                'price': float(product.selling_price),
                'category': product.category.name if product.category else 'Uncategorized',
                'is_single': False,
            })
    
    context = {
        'tenant': tenant,
        'items': items,
        'active_tab': 'barcodes',
    }
    return render(request, 'tech_master/inventory/bulk_print_labels.html', context)



# ============================================
# IMPORT/EXPORT VIEWS
# ============================================

@login_required
def import_products(request):
    """Import products from Excel/CSV"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if request.method == 'POST':
        file = request.FILES.get('file')
        import_type = request.POST.get('import_type', 'auto')
        
        if not file:
            messages.error(request, 'Please select a file')
            return redirect('tech_master:import_products')
        
        if not file.name.endswith(('.xlsx', '.xls', '.csv')):
            messages.error(request, 'Please upload Excel or CSV file')
            return redirect('tech_master:import_products')
        
        result = import_products_from_excel(file, tenant.id, import_type)
        
        if result.get('error'):
            messages.error(request, result['error'])
        else:
            msg = f"✅ Import complete! Created: {result['created']}, Updated: {result['updated']}"
            messages.success(request, msg)
            if result['errors']:
                for err in result['errors'][:5]:
                    messages.warning(request, err)
        
        return redirect('tech_master:product_list')
    
    context = {'tenant': tenant}
    return render(request, 'tech_master/inventory/import_products.html', context)


def import_products_from_excel(file, tenant_id, import_type='auto'):
    """Import products from Excel/CSV file"""
    errors = []
    success_count = 0
    update_count = 0
    
    try:
        import pandas as pd
        
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        required_columns = ['name', 'selling_price']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return {'error': f'Missing columns: {", ".join(missing_columns)}'}
        
        tenant = Tenant.objects.get(id=tenant_id)
        branch = Branch.objects.filter(tenant=tenant, is_main_branch=True).first()
        if not branch:
            branch = Branch.objects.filter(tenant=tenant).first()
        
        for index, row in df.iterrows():
            try:
                name = str(row.get('name', '')).strip()
                selling_price = float(row.get('selling_price', 0))
                buying_price = float(row.get('buying_price', 0)) if pd.notna(row.get('buying_price')) else 0
                brand = str(row.get('brand', '')).strip() if pd.notna(row.get('brand')) else ''
                model = str(row.get('model', '')).strip() if pd.notna(row.get('model')) else ''
                sku_code = str(row.get('sku_code', '')).strip().upper() if pd.notna(row.get('sku_code')) else None
                category_name = str(row.get('category', '')).strip() if pd.notna(row.get('category')) else ''
                reorder_level = int(row.get('reorder_level', 5)) if pd.notna(row.get('reorder_level')) else 5
                
                if not name or selling_price <= 0:
                    errors.append(f"Row {str(index)}: Name and selling price are required")
                    continue
                
                category = None
                if category_name:
                    category, _ = Category.objects.get_or_create(
                        tenant=tenant,
                        name=category_name,
                        defaults={'is_active': True}
                    )
                
                sku_code_value = sku_code if sku_code else f"{name.replace(' ', '_')}_{str(index)}"
                
                product, created = Product.objects.update_or_create(
                    tenant=tenant,
                    sku_code=sku_code_value,
                    defaults={
                        'name': name,
                        'brand': brand,
                        'model': model,
                        'category': category,
                        'branch': branch,
                        'buying_price': buying_price,
                        'selling_price': selling_price,
                        'reorder_level': reorder_level,
                        'is_active': True
                    }
                )
                
                if created:
                    success_count += 1
                else:
                    update_count += 1
                    
            except Exception as e:
                errors.append(f"Row {str(index)}: {str(e)}")
        
        return {
            'success': True,
            'created': success_count,
            'updated': update_count,
            'errors': errors
        }
        
    except ImportError:
        return {'error': 'pandas library is not installed. Please run: pip install pandas openpyxl'}
    except Exception as e:
        return {'error': str(e)}
# apps/tech_master/inventory/views.py

@login_required
def download_product_template(request):
    """Download Excel template for product import"""
    import pandas as pd
    from io import BytesIO
    
    # ✅ Empty template with only headers (no sample data)
    data = {
        'name': [''],
        'sku_code': [''],
        'selling_price': [''],
        'buying_price': [''],
        'brand': [''],
        'model': [''],
        'category': [''],
        'reorder_level': [''],
        'description': [''],
    }
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Products', index=False)
        
        # Instructions sheet with formatting
        instructions_data = [
            ['📋 PRODUCT IMPORT TEMPLATE INSTRUCTIONS'],
            [''],
            ['REQUIRED COLUMNS:'],
            ['- name: Product name (e.g., Samsung Galaxy A07)'],
            ['- selling_price: Selling price in KES (e.g., 18000)'],
            [''],
            ['OPTIONAL COLUMNS:'],
            ['- sku_code: Unique product code (auto-generated if empty)'],
            ['- buying_price: Cost price in KES'],
            ['- brand: Product brand (e.g., Samsung, Apple)'],
            ['- model: Product model (e.g., A07, iPhone 14)'],
            ['- category: Category name (will be created if not exists)'],
            ['- reorder_level: Minimum stock alert level (default: 5)'],
            ['- description: Product description'],
            [''],
            ['📌 IMPORTANT NOTES:'],
            ['- First row must contain column headers'],
            ['- Do not rename or remove columns'],
            ['- For single products, each row should have a unique identifier'],
            ['- For bulk products, use the quantity column'],
            ['- Empty rows will be ignored'],
            ['- Date format: YYYY-MM-DD'],
        ]
        
        instructions_df = pd.DataFrame({'Instructions': instructions_data})
        instructions_df.to_excel(writer, sheet_name='Instructions', index=False, header=False)
    
    output.seek(0)
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="product_import_template.xlsx"'
    
    return response


@login_required
def download_imei_template(request):
    """Download Excel template for IMEI/Serial number import"""
    import pandas as pd
    from io import BytesIO
    
    # ✅ Empty template with only headers (no sample data)
    data = {
        'product_name': [''],
        'imei_number': [''],
        'serial_number': [''],
        'selling_price': [''],
        'branch_code': [''],
    }
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='IMEI_Devices', index=False)
        
        # Instructions sheet with formatting
        instructions_data = [
            ['📱 IMEI/SERIAL NUMBER IMPORT TEMPLATE INSTRUCTIONS'],
            [''],
            ['REQUIRED COLUMNS:'],
            ['- product_name: Exact name of existing product'],
            ['- Either imei_number OR serial_number (at least one is required)'],
            [''],
            ['OPTIONAL COLUMNS:'],
            ['- imei_number: 15-digit IMEI number (unique)'],
            ['- serial_number: Serial number (unique)'],
            ['- selling_price: Override price (optional)'],
            ['- branch_code: Branch code where unit is located'],
            [''],
            ['📌 IMPORTANT NOTES:'],
            ['- IMEI must be exactly 15 digits'],
            ['- Serial number must be unique'],
            ['- Product name must match existing product exactly'],
            ['- Branch code must exist in the system'],
            ['- Empty rows will be ignored'],
        ]
        
        instructions_df = pd.DataFrame({'Instructions': instructions_data})
        instructions_df.to_excel(writer, sheet_name='Instructions', index=False, header=False)
    
    output.seek(0)
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="imei_import_template.xlsx"'
    
    return response


# ============================================
# BRANCH STOCK VIEWS (MISSING)
# ============================================

@login_required
def branch_stock_list(request):
    """View stock levels by branch"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    
    # Get stock for each branch
    branch_stock_data = []
    for branch in branches:
        stock_count = BranchStock.objects.filter(
            tenant=tenant,
            branch=branch
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        branch_stock_data.append({
            'branch': branch,
            'stock_count': stock_count,
            'product_count': branch.products.count(),
            'unit_count': branch.product_units.count(),
        })
    
    context = {
        'tenant': tenant,
        'branch_stock_data': branch_stock_data,
        'active_tab': 'stock',
    }
    return render(request, 'tech_master/inventory/branch_stock_list.html', context)


@login_required
def branch_stock_detail(request, branch_id):
    """View detailed stock for a specific branch"""
    tenant = request.user.tenant
    branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
    
    # Get all products with stock in this branch
    branch_stocks = BranchStock.objects.filter(
        tenant=tenant,
        branch=branch
    ).select_related('product')
    
    context = {
        'tenant': tenant,
        'branch': branch,
        'branch_stocks': branch_stocks,
        'active_tab': 'stock',
    }
    return render(request, 'tech_master/inventory/branch_stock_detail.html', context)


# ============================================
# STOCK TRANSFER VIEWS (MISSING)
# ============================================

@login_required
def transfer_stock(request):
    """Transfer stock between branches"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    products = Product.objects.filter(tenant=tenant, is_active=True)
    
    if request.method == 'POST':
        from_branch_id = request.POST.get('from_branch')
        to_branch_id = request.POST.get('to_branch')
        product_id = request.POST.get('product')
        quantity = int(request.POST.get('quantity', 0))
        reason = request.POST.get('reason', '')
        
        if not from_branch_id or not to_branch_id or not product_id:
            messages.error(request, 'Please fill all required fields')
            return redirect('tech_master:transfer_stock')
        
        from_branch = get_object_or_404(Branch, id=from_branch_id, tenant=tenant)
        to_branch = get_object_or_404(Branch, id=to_branch_id, tenant=tenant)
        product = get_object_or_404(Product, id=product_id, tenant=tenant)
        
        # Check if product is single item
        if product.category.is_single_item:
            # Get available units
            units = ProductUnit.objects.filter(
                tenant=tenant,
                product=product,
                branch=from_branch,
                status='available'
            )[:quantity]
            
            if len(units) < quantity:
                messages.error(request, f'Only {len(units)} units available in {from_branch.name}')
                return redirect('tech_master:transfer_stock')
            
            # Transfer each unit
            for unit in units:
                unit.branch = to_branch
                unit.save()
                
                # Create transfer record
                BranchTransfer.objects.create(
                    tenant=tenant,
                    product_unit=unit,
                    from_branch=from_branch,
                    to_branch=to_branch,
                    quantity=1,
                    status='completed',
                    transferred_by=request.user,
                    reason=reason
                )
            
            messages.success(request, f'Transferred {quantity} unit(s) from {from_branch.name} to {to_branch.name}')
            
        else:
            # Bulk product - update quantity
            branch_stock, created = BranchStock.objects.get_or_create(
                tenant=tenant,
                branch=from_branch,
                product=product,
                defaults={'quantity': 0}
            )
            
            if branch_stock.quantity < quantity:
                messages.error(request, f'Only {branch_stock.quantity} units available in {from_branch.name}')
                return redirect('tech_master:transfer_stock')
            
            # Remove from source
            branch_stock.quantity -= quantity
            branch_stock.save()
            
            # Add to destination
            to_stock, _ = BranchStock.objects.get_or_create(
                tenant=tenant,
                branch=to_branch,
                product=product,
                defaults={'quantity': 0}
            )
            to_stock.quantity += quantity
            to_stock.save()
            
            messages.success(request, f'Transferred {quantity} units from {from_branch.name} to {to_branch.name}')
        
        return redirect('tech_master:branch_stock_list')
    
    context = {
        'tenant': tenant,
        'branches': branches,
        'products': products,
        'active_tab': 'transfer',
    }
    return render(request, 'tech_master/inventory/transfer_stock.html', context)


# ============================================
# STOCK HISTORY VIEWS (MISSING)
# ============================================

@login_required
def stock_history(request, product_id=None):
    """View stock movement history"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    stock_entries = StockEntry.objects.filter(tenant=tenant).select_related(
        'product_sku', 'product_unit', 'branch', 'created_by'
    ).order_by('-created_at')
    
    if product_id:
        product = get_object_or_404(Product, id=product_id, tenant=tenant)
        stock_entries = stock_entries.filter(
            Q(product_sku=product) | Q(product_unit__product=product)
        )
    
    # Pagination
    paginator = Paginator(stock_entries, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tenant': tenant,
        'stock_entries': page_obj,
        'active_tab': 'stock',
    }
    return render(request, 'tech_master/inventory/stock_history.html', context)


# ============================================
# STOCK REPORT VIEWS (MISSING)
# ============================================

@login_required
def stock_report(request):
    """Generate stock reports"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    # Get all products with stock info
    products = Product.objects.filter(
        tenant=tenant,
        is_active=True
    ).select_related('category', 'branch')
    
    # Total stock value
    total_value = products.aggregate(
        total=Sum(F('available_quantity') * F('buying_price'))
    )['total'] or Decimal('0.00')
    
    # Products by category
    category_stats = products.values('category__name').annotate(
        count=Count('id'),
        total_stock=Sum('available_quantity'),
        total_value=Sum(F('available_quantity') * F('buying_price'))
    ).order_by('-total_value')
    
    context = {
        'tenant': tenant,
        'products': products,
        'total_value': total_value,
        'category_stats': category_stats,
        'total_products': products.count(),
        'active_tab': 'reports',
    }
    return render(request, 'tech_master/inventory/stock_report.html', context)


# ============================================
# DAMAGED/WASTE REPORT (MISSING)
# ============================================

@login_required
def damaged_units_report(request):
    """View damaged or written-off units"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    damaged_units = ProductUnit.objects.filter(
        tenant=tenant,
        status__in=['damaged', 'stolen', 'lost', 'writeoff']
    ).select_related('product', 'branch', 'supplier').order_by('-updated_at')
    
    context = {
        'tenant': tenant,
        'damaged_units': damaged_units,
        'total_damaged': damaged_units.count(),
        'active_tab': 'reports',
    }
    return render(request, 'tech_master/inventory/damaged_units_report.html', context)




# ============================================
# API VIEWS
# ============================================

@login_required
@require_http_methods(["POST"])
def api_add_units(request, product_id):
    """API endpoint to add multiple units to a product"""
    tenant = request.user.tenant
    product = get_object_or_404(Product, id=product_id, tenant=tenant)
    data = json.loads(request.body)
    
    identifiers = data.get('identifiers', [])
    buying_price = data.get('buying_price', product.buying_price)
    selling_price = data.get('selling_price', product.selling_price)
    best_price = data.get('best_price', product.best_price)
    branch_id = data.get('branch_id')
    unit_status = data.get('status', 'available')
    
    branch = None
    if branch_id:
        branch = Branch.objects.filter(id=branch_id, tenant=tenant).first()
    
    created_units = []
    for identifier in identifiers:
        if identifier.strip():
            is_imei = len(identifier.strip()) == 15 and identifier.strip().isdigit()
            
            new_unit = ProductUnit.objects.create(
                tenant=tenant,
                product=product,
                branch=branch,
                imei_number=identifier.strip() if is_imei else None,
                serial_number=identifier.strip() if not is_imei else None,
                unit_buying_price=float(buying_price) if buying_price else None,
                unit_selling_price=float(selling_price) if selling_price else None,
                best_price=float(best_price) if best_price else None,
                status=unit_status
            )
            created_units.append({
                'id': new_unit.id,
                'identifier': identifier,
                'branch_name': new_unit.branch.name if new_unit.branch else 'Main Shop',
                'selling_price': float(new_unit.unit_selling_price or product.selling_price),
                'buying_price': float(new_unit.unit_buying_price or product.buying_price)
            })
    
    product.update_quantities()
    
    return JsonResponse({
        'success': True,
        'items': created_units,
        'new_available_units': product.available_quantity,
        'total_units': product.total_quantity
    })


@login_required
@require_http_methods(["GET"])
def get_unit_api(request, unit_id):
    """API endpoint to get unit details for editing"""
    tenant = request.user.tenant
    unit = get_object_or_404(ProductUnit, id=unit_id, tenant=tenant)
    
    # ✅ Use safe_float helper
    def safe_float(value):
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    
    data = {
        'id': unit.id,
        'imei_number': unit.imei_number,
        'serial_number': unit.serial_number,
        'buying_price': safe_float(unit.unit_buying_price) or safe_float(unit.product.buying_price),
        'selling_price': safe_float(unit.unit_selling_price) or safe_float(unit.product.selling_price),
        'best_price': safe_float(unit.best_price) or safe_float(unit.product.best_price),
        'status': unit.status,
        'branch_id': unit.branch.id if unit.branch else None,
        'branch_name': unit.branch.name if unit.branch else 'Main Shop',
        'created_at': unit.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': unit.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
    }
    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def api_update_unit(request, unit_id):
    """API endpoint to update a single unit"""
    tenant = request.user.tenant
    unit = get_object_or_404(ProductUnit, id=unit_id, tenant=tenant)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    # Helper function for safe Decimal conversion
    def safe_decimal(value):
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (TypeError, ValueError):
            return None
    
    # Update fields with safe conversion
    if 'imei_number' in data:
        unit.imei_number = data['imei_number'] if data['imei_number'] else None
    
    if 'serial_number' in data:
        unit.serial_number = data['serial_number'] if data['serial_number'] else None
    
    if 'buying_price' in data:
        unit.unit_buying_price = safe_decimal(data['buying_price'])
    
    if 'selling_price' in data:
        unit.unit_selling_price = safe_decimal(data['selling_price'])
    
    if 'best_price' in data:
        unit.best_price = safe_decimal(data['best_price'])
    
    if 'status' in data:
        unit.status = data['status']
    
    if 'branch_id' in data:
        try:
            branch = Branch.objects.get(id=data['branch_id'], tenant=tenant)
            unit.branch = branch
        except Branch.DoesNotExist:
            pass
    
    unit.save()
    unit.product.update_quantities()
    
    # Queue sync if offline
    if getattr(settings, 'OFFLINE_MODE', False):
        try:
            SyncQueue.objects.create(
                tenant_id=tenant.id,
                model_name='ProductUnit',
                object_id=str(unit.id),
                operation='UPDATE',
                data={
                    'id': unit.id,
                    'product_id': unit.product_id,
                    'imei_number': unit.imei_number,
                    'serial_number': unit.serial_number,
                    'status': unit.status,
                    'branch_id': unit.branch_id,
                    'buying_price': str(unit.unit_buying_price) if unit.unit_buying_price else None,
                    'selling_price': str(unit.unit_selling_price) if unit.unit_selling_price else None,
                    'best_price': str(unit.best_price) if unit.best_price else None,
                    'tenant_id': tenant.id,
                },
                priority=7
            )
        except Exception as e:
            logger.error(f"Failed to queue ProductUnit sync: {e}")
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["DELETE"])
def api_delete_unit(request, unit_id):
    """API endpoint to delete a unit"""
    tenant = request.user.tenant
    unit = get_object_or_404(ProductUnit, id=unit_id, tenant=tenant)
    product = unit.product
    
    unit.delete()
    product.update_quantities()
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def api_move_unit(request, unit_id):
    """API endpoint to move a unit to another branch"""
    tenant = request.user.tenant
    unit = get_object_or_404(ProductUnit, id=unit_id, tenant=tenant)
    data = json.loads(request.body)
    branch_id = data.get('branch_id')
    
    if branch_id:
        branch = Branch.objects.filter(id=branch_id, tenant=tenant).first()
        if branch:
            old_branch = unit.branch
            unit.branch = branch
            unit.save()
            
            BranchTransfer.objects.create(
                tenant=tenant,
                product_unit=unit,
                from_branch=old_branch,
                to_branch=branch,
                transferred_by=request.user,
                reason=data.get('reason', ''),
                status='completed'
            )
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def api_bulk_assign_units(request):
    """Bulk assign units to a sales agent"""
    tenant = request.user.tenant
    data = json.loads(request.body)
    unit_ids = data.get('unit_ids', [])
    owner_id = data.get('owner_id')
    
    owner = None
    if owner_id:
        owner = User.objects.filter(id=owner_id, tenant=tenant).first()
    
    for unit_id in unit_ids:
        unit = get_object_or_404(ProductUnit, id=unit_id, tenant=tenant)
        unit.current_owner = owner
        unit.assigned_date = timezone.now() if owner else None
        unit.save()
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def api_assign_unit_owner(request, unit_id):
    """Assign a single unit to a sales agent"""
    tenant = request.user.tenant
    unit = get_object_or_404(ProductUnit, id=unit_id, tenant=tenant)
    data = json.loads(request.body)
    owner_id = data.get('owner_id')
    
    owner = None
    if owner_id:
        owner = User.objects.filter(id=owner_id, tenant=tenant).first()
    
    unit.current_owner = owner
    unit.assigned_date = timezone.now() if owner else None
    unit.save()
    
    return JsonResponse({'success': True})


class InventorySyncViewSet(viewsets.ViewSet):
    """API endpoint for inventory sync operations"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def sync(self, request):
        """Sync local changes to the server"""
        tenant = request.user.tenant
        
        results = SyncManager.process_pending_operations(
            tenant_id=tenant.id,
            limit=int(request.data.get('limit', 50))
        )
        
        return Response({
            'status': 'success',
            'results': results
        })
    
    @action(detail=False, methods=['post'])
    def get_pending(self, request):
        """Get list of pending sync operations"""
        tenant = request.user.tenant
        
        pending = SyncQueue.objects.filter(
            tenant=tenant,
            status='PENDING'
        ).values('id', 'model_name', 'operation', 'created_at', 'priority')
        
        return Response({
            'status': 'success',
            'pending_count': pending.count(),
            'operations': list(pending)
        })
    
    @action(detail=False, methods=['post'])
    def resolve_conflict(self, request):
        """Resolve a sync conflict manually"""
        operation_id = request.data.get('operation_id')
        resolution = request.data.get('resolution')
        
        if not operation_id or not resolution:
            return Response({
                'error': 'operation_id and resolution are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        success = SyncManager.resolve_conflict(
            operation_id=operation_id,
            resolution_data=resolution,
            resolved_by=request.user
        )
        
        if success:
            return Response({'status': 'success'})
        else:
            return Response({
                'error': 'Failed to resolve conflict'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def pull_updates(self, request):
        """Pull latest updates from server (for mobile apps)"""
        tenant = request.user.tenant
        last_sync = request.data.get('last_sync')
        
        # Get all models updated after last_sync
        updates = {
            'products': [],
            'product_units': [],
            'branch_transfers': [],
            'stock_entries': [],
        }
        
        if last_sync:
            # Get updates from each model
            for model, key in [
                (Product, 'products'),
                (ProductUnit, 'product_units'),
                (BranchTransfer, 'branch_transfers'),
                (StockEntry, 'stock_entries'),
            ]:
                queryset = model.objects.filter(
                    tenant=tenant,
                    updated_at__gt=last_sync
                )
                updates[key] = list(queryset.values())
        
        return Response({
            'status': 'success',
            'updates': updates,
            'timestamp': timezone.now().isoformat()
        })
    

