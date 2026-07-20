# apps/tronic_master/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, F, Sum, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import IntegrityError 
from django.views.decorators.http import require_http_methods
from django.conf import settings
from decimal import Decimal
from datetime import datetime, timedelta
import json
import logging

# Rest Framework
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

# Shared Apps
from apps.shared.powersync.sync_manager import SyncManager
from apps.shared.tenants.models import Tenant, SyncQueue
from apps.shared.users.models import User
from apps.shared.tenants.decorators import check_product_limit, check_branch_limit, check_user_limit
from apps.shared.customers.models import Customer
from apps.shared.expenses.models import Expense, ExpenseCategory

# Tech Master Models
from apps.tronic_master.models import (
    Product, ProductUnit, Branch, Category, Supplier,
    StockEntry, BranchTransfer, BranchStock,
    Sale, SaleItem, Return, CashDrawer, CashTransaction
)
from django.contrib.auth import get_user_model
from apps.shared.permissions.models import  UserRoleAssignment
from apps.shared.roles.models import ProjectRole
from django.views.decorators.csrf import csrf_exempt
from apps.shared.portal.helpers import is_admin_user



User = get_user_model()


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
    return render(request, 'tronic_master/branch_list.html', context)


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
            return redirect('tronic_master:add_branch')

        if Branch.objects.filter(tenant=tenant, code=code).exists():
            messages.error(request, f'Branch code "{code}" already exists')
            return redirect('tronic_master:add_branch')

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
        # ✅ FIX: Add tronic_master: namespace
        return redirect('tronic_master:branch_list')

    context = {'tenant': tenant}
    return render(request, 'tronic_master/add_branch.html', context)


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
            return redirect('tronic_master:edit_branch', branch_id=branch.id)

        if Branch.objects.filter(tenant=tenant, code=code).exclude(id=branch.id).exists():
            messages.error(request, f'Branch code "{code}" already exists')
            return redirect('tronic_master:edit_branch', branch_id=branch.id)

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
        return redirect('tronic_master:branch_list')

    context = {
        'tenant': tenant,
        'branch': branch,
    }
    return render(request, 'tronic_master/edit_branch.html', context)


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
        return redirect('tronic_master:branch_list')

    if branch.product_units.exists():
        messages.error(request, f'Cannot delete "{branch.name}" because it has {branch.product_units.count()} product unit(s). Move or reassign units first.')
        return redirect('tronic_master:branch_list')

    branch_name = branch.name
    branch.delete()
    messages.success(request, f'Branch "{branch_name}" deleted successfully!')
    return redirect('tronic_master:branch_list')


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
            return redirect('tronic_master:assign_branch_manager')

        branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)

        if action == 'assign':
            if not user_id:
                messages.error(request, 'Please select a user to assign')
                return redirect('tronic_master:assign_branch_manager')

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

        return redirect('tronic_master:assign_branch_manager')

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
    return render(request, 'tronic_master/assign_branch_manager.html', context)





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
    return render(request, 'tronic_master/category_list.html', context)


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
            return redirect('tronic_master:add_category')

        if Category.objects.filter(tenant=tenant, name__iexact=name).exists():
            messages.error(request, f'Category "{name}" already exists')
            return redirect('tronic_master:add_category')

        category = Category.objects.create(
            tenant=tenant,
            name=name,
            item_type=item_type,
            identifier_type=identifier_type,
            description=description,
            is_active=is_active
        )

        messages.success(request, f'Category "{category.name}" created successfully!')
        return redirect('tronic_master:category_list')

    context = {'tenant': tenant}
    return render(request, 'tronic_master/add_category.html', context)


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
            return redirect('tronic_master:edit_category', category_id=category.id)

        if Category.objects.filter(tenant=tenant, name__iexact=name).exclude(id=category.id).exists():
            messages.error(request, f'Category "{name}" already exists')
            return redirect('tronic_master:edit_category', category_id=category.id)

        category.name = name
        category.item_type = item_type
        category.identifier_type = identifier_type
        category.description = description
        category.is_active = is_active
        category.save()

        messages.success(request, f'Category "{category.name}" updated successfully!')
        return redirect('tronic_master:category_list')

    context = {
        'tenant': tenant,
        'category': category,
    }
    return render(request, 'tronic_master/edit_category.html', context)


@login_required
def delete_category(request, category_id):
    """Delete a product category"""
    tenant = request.user.tenant
    category = get_object_or_404(Category, id=category_id, tenant=tenant)

    if category.products.exists():
        product_count = category.products.count()
        messages.error(request, f'Cannot delete "{category.name}" because it has {product_count} product(s).')
        return redirect('tronic_master:category_list')

    category_name = category.name
    category.delete()
    messages.success(request, f'Category "{category_name}" deleted successfully!')
    return redirect('tronic_master:category_list')



# ============================================
# MANAGE CATEGORIES VIEW
# ============================================

@login_required
def manage_categories(request):
    """Manage all categories - list, edit, delete in one place"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    categories = Category.objects.filter(tenant=tenant).order_by('name')

    # Get product count for each category
    for category in categories:
        category.product_count = Product.objects.filter(
            tenant=tenant,
            category=category,
            is_active=True
        ).count()

    # Calculate statistics
    active_count = categories.filter(is_active=True).count()
    total_products = 0
    for category in categories:
        total_products += category.product_count

    if request.method == 'POST':
        action = request.POST.get('action')
        category_ids = request.POST.getlist('category_ids')

        if action == 'delete':
            deleted_count = 0
            for category_id in category_ids:
                try:
                    category = Category.objects.get(id=category_id, tenant=tenant)
                    # Check if category has products
                    product_count = Product.objects.filter(
                        tenant=tenant,
                        category=category,
                        is_active=True
                    ).count()

                    if product_count == 0:
                        category.delete()
                        deleted_count += 1
                    else:
                        messages.warning(
                            request,
                            f'Cannot delete "{category.name}" - it has {product_count} products'
                        )
                except Category.DoesNotExist:
                    pass
            if deleted_count > 0:
                messages.success(request, f'Successfully deleted {deleted_count} category(s)!')
        elif action == 'activate':
            Category.objects.filter(id__in=category_ids, tenant=tenant).update(is_active=True)
            messages.success(request, 'Selected categories activated!')
        elif action == 'deactivate':
            Category.objects.filter(id__in=category_ids, tenant=tenant).update(is_active=False)
            messages.success(request, 'Selected categories deactivated!')

        return redirect('tronic_master:manage_categories')

    context = {
        'tenant': tenant,
        'categories': categories,
        'active_count': active_count,
        'total_products': total_products,
        'active_tab': 'inventory',
    }
    return render(request, 'tronic_master/manage_categories.html', context)



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
    return render(request, 'tronic_master/supplier_list.html', context)


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
            return redirect('tronic_master:add_supplier')

        if Supplier.objects.filter(tenant=tenant, name__iexact=name).exists():
            messages.error(request, f'Supplier "{name}" already exists')
            return redirect('tronic_master:add_supplier')

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
        return redirect('tronic_master:supplier_list')

    context = {'tenant': tenant}
    return render(request, 'tronic_master/add_supplier.html', context)


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
            return redirect('tronic_master:edit_supplier', supplier_id=supplier.id)

        if Supplier.objects.filter(tenant=tenant, name__iexact=name).exclude(id=supplier.id).exists():
            messages.error(request, f'Supplier "{name}" already exists')
            return redirect('tronic_master:edit_supplier', supplier_id=supplier.id)

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
        return redirect('tronic_master:supplier_list')

    context = {
        'tenant': tenant,
        'supplier': supplier,
    }
    return render(request, 'tronic_master/edit_supplier.html', context)


@login_required
def delete_supplier(request, supplier_id):
    """Delete a supplier"""
    tenant = request.user.tenant
    supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)

    if supplier.products.exists():
        messages.error(request, f'Cannot delete "{supplier.name}" because it has {supplier.products.count()} product(s).')
        return redirect('tronic_master:supplier_list')

    supplier_name = supplier.name
    supplier.delete()
    messages.success(request, f'Supplier "{supplier_name}" deleted successfully!')
    return redirect('tronic_master:supplier_list')


# ============================================
# MANAGE SUPPLIERS VIEW
# ============================================

@login_required
def manage_suppliers(request):
    """Manage all suppliers - list, edit, delete in one place"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    # Use annotate to add product_count as a field in the query
    suppliers = Supplier.objects.filter(tenant=tenant).annotate(
        product_count=Count('products', filter=Q(products__is_active=True))
    ).order_by('name')

    # Calculate statistics
    active_count = suppliers.filter(is_active=True).count()
    total_products = suppliers.aggregate(
        total=Sum('product_count')
    )['total'] or 0

    if request.method == 'POST':
        action = request.POST.get('action')
        supplier_ids = request.POST.getlist('supplier_ids')

        if action == 'delete':
            deleted_count = 0
            for supplier_id in supplier_ids:
                try:
                    supplier = Supplier.objects.get(id=supplier_id, tenant=tenant)
                    # Check if supplier has products
                    product_count = supplier.products.count()
                    if product_count == 0:
                        supplier.delete()
                        deleted_count += 1
                    else:
                        messages.warning(
                            request,
                            f'Cannot delete "{supplier.name}" - it has {product_count} products'
                        )
                except Supplier.DoesNotExist:
                    pass
            if deleted_count > 0:
                messages.success(request, f'Successfully deleted {deleted_count} supplier(s)!')
        elif action == 'activate':
            Supplier.objects.filter(id__in=supplier_ids, tenant=tenant).update(is_active=True)
            messages.success(request, 'Selected suppliers activated!')
        elif action == 'deactivate':
            Supplier.objects.filter(id__in=supplier_ids, tenant=tenant).update(is_active=False)
            messages.success(request, 'Selected suppliers deactivated!')

        return redirect('tronic_master:manage_suppliers')

    context = {
        'tenant': tenant,
        'suppliers': suppliers,
        'active_count': active_count,
        'total_products': total_products,
        'active_tab': 'inventory',
    }
    return render(request, 'tronic_master/manage_suppliers.html', context)


# ============================================
# INVENTORY MANAGEMENT
# ============================================

@login_required
def add_product(request):
    """Redirect to product selection"""
    return redirect('tronic_master:add_product_selection')


@login_required
def transfer_product(request, product_id):
    """Transfer product to another branch (wrapper for move_product_ownership)"""
    return redirect('tronic_master:move_product_ownership')


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
    return render(request, 'tronic_master/generate_label_pdf.html', context)


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
            'buying_price': safe_float(product.default_buying_price),
            'selling_price': safe_float(product.default_selling_price),
            'best_price': safe_float(product.default_best_price),
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
        buying_price = unit.unit_buying_price or unit.product.default_buying_price
        selling_price = unit.unit_selling_price or unit.product.default_selling_price
        best_price = unit.best_price or unit.product.default_best_price

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
                product.default_buying_price = Decimal(str(data['buying_price']))
            except (TypeError, ValueError):
                pass
        if 'selling_price' in data:
            try:
                product.default_selling_price = Decimal(str(data['selling_price']))
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
                        'buying_price': str(product.default_buying_price),
                        'selling_price': str(product.default_selling_price),
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
                'buying_price': float(product.default_buying_price),
                'selling_price': float(product.default_selling_price),
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
# MANAGE PRODUCTS VIEW (LIST, EDIT, DELETE)
# ============================================

@login_required
def manage_products(request):
    """Manage all products - list, edit, delete in one place"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    # Get filter parameters
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    stock_filter = request.GET.get('stock', '')
    sort_by = request.GET.get('sort', 'name')

    # Base queryset
    products = Product.objects.filter(tenant=tenant).select_related(
        'category', 'branch', 'supplier'
    )

    # Apply filters
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(model__icontains=search_query) |
            Q(sku_code__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)
    elif status_filter == 'discontinued':
        products = products.filter(is_discontinued=True)

    if stock_filter == 'in_stock':
        products = products.filter(available_quantity__gt=0)
    elif stock_filter == 'out_of_stock':
        products = products.filter(available_quantity=0)
    elif stock_filter == 'low_stock':
        products = products.filter(
            available_quantity__lte=F('reorder_level'),
            available_quantity__gt=0
        )

    # Apply sorting
    if sort_by == 'name':
        products = products.order_by('name')
    elif sort_by == '-name':
        products = products.order_by('-name')
    elif sort_by == 'sku':
        products = products.order_by('sku_code')
    elif sort_by == 'price_asc':
        products = products.order_by('default_selling_price')
    elif sort_by == 'price_desc':
        products = products.order_by('default_selling_price')
    elif sort_by == 'stock_asc':
        products = products.order_by('available_quantity')
    elif sort_by == 'stock_desc':
        products = products.order_by('-available_quantity')
    elif sort_by == 'created':
        products = products.order_by('-created_at')
    else:
        products = products.order_by('name')

    # Get categories for filter
    categories = Category.objects.filter(tenant=tenant, is_active=True)

    # Calculate statistics
    total_products = products.count()
    total_value = products.aggregate(
        total=Sum(F('available_quantity') * F('default_buying_price')) 
    )['total'] or Decimal('0.00')

    # Pagination
    paginator = Paginator(products, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'tenant': tenant,
        'products': page_obj,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_id,
        'status_filter': status_filter,
        'stock_filter': stock_filter,
        'sort_by': sort_by,
        'total_products': total_products,
        'total_value': total_value,
        'active_tab': 'inventory',
    }
    return render(request, 'tronic_master/manage_products.html', context)




# ============================================
# PRODUCT SEARCH VIEW
# ============================================

@login_required
def product_search(request):
    """Quick product search page"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    search_query = request.GET.get('q', '').strip()
    products = []

    if search_query:
        products = Product.objects.filter(
            tenant=tenant,
            is_active=True
        ).filter(
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(model__icontains=search_query) |
            Q(sku_code__icontains=search_query) |
            Q(description__icontains=search_query)
        ).select_related('category', 'branch')[:50]

    context = {
        'tenant': tenant,
        'products': products,
        'search_query': search_query,
        'active_tab': 'search',
    }
    return render(request, 'tronic_master/product_search.html', context)

@login_required
def product_search_ajax(request):
    """AJAX endpoint for product search"""
    tenant = request.user.tenant

    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)

    query = request.GET.get('q', '').strip()

    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    products = Product.objects.filter(
        tenant=tenant,
        is_active=True
    ).filter(
        Q(name__icontains=query) |
        Q(brand__icontains=query) |
        Q(model__icontains=query) |
        Q(sku_code__icontains=query)
        # ❌ REMOVE this line: Q(barcode__icontains=query)
    ).select_related('category')[:20]

    results = []
    for product in products:
        results.append({
            'id': product.id,
            'sku_code': product.sku_code,
            'name': product.name,
            'brand': product.brand,
            'model': product.model,
            # ❌ REMOVE this line: 'barcode': product.barcode,
            'selling_price': float(product.default_selling_price),
            'buying_price': float(product.default_buying_price),
            'available_quantity': product.available_quantity,
            'category': product.category.name if product.category else None,
            'image': product.image.url if product.image else None,
            'url': f"/tech/inventory/{product.id}/"
        })

    return JsonResponse({'results': results})



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
        # ✅ FIX: specifications is on ProductVariant, not Product
        # Instead of trying to get specifications from Product,
        # get the first available variant's specifications
        
        # Get the first variant to display specs
        first_variant = product.variants.first()
        if first_variant and first_variant.specifications:
            specs = first_variant.specifications
        else:
            specs = {}

        # For display purposes, create a primary_spec string
        primary_spec = ""
        if specs:
            spec_parts = []
            if specs.get('ram'):
                spec_parts.append(str(specs.get('ram')))
            if specs.get('storage'):
                spec_parts.append(str(specs.get('storage')))
            if specs.get('color'):
                spec_parts.append(str(specs.get('color')))
            primary_spec = " | ".join(spec_parts) if spec_parts else "-"

        product.primary_spec = primary_spec
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
    return render(request, 'tronic_master/product_list.html', context)


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
        unit.display_buying_price = unit.unit_buying_price if unit.unit_buying_price else product.default_buying_price
        unit.display_selling_price = unit.unit_selling_price if unit.unit_selling_price else product.default_selling_price

        if unit.imei_number:
            unit.display_identifier = f"IMEI: {unit.imei_number}"
        elif unit.serial_number:
            unit.display_identifier = f"S/N: {unit.serial_number}"
        else:
            unit.display_identifier = "No identifier"

    # ✅ ADD FINANCIAL CALCULATIONS HERE
    # Stock value calculations
    stock_value = product.available_quantity * product.default_buying_price
    retail_value = product.available_quantity * product.default_selling_price
    profit_margin = retail_value - stock_value
    profit_percentage = (profit_margin / stock_value * 100) if stock_value > 0 else 0

    context = {
        'product': product,
        'units': units,
        'units_count': units.count(),
        'available_units_count': units.filter(status='available').count(),
        'sold_units_count': units.filter(status='sold').count(),
        'damaged_units_count': units.filter(status='damaged').count(),
        'reserved_units_count': units.filter(status='reserved').count(),
        'tenant': tenant,
        # ✅ ADD THESE TO CONTEXT
        'stock_value': stock_value,
        'retail_value': retail_value,
        'profit_margin': profit_margin,
        'profit_percentage': profit_percentage,
    }
    return render(request, 'tronic_master/product_detail.html', context)


@login_required
@check_product_limit
def add_product_selection(request):
    """Product type selection page"""
    tenant = request.user.tenant
    return render(request, 'tronic_master/add_product_selection.html', {'tenant': tenant})



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
            return redirect('tronic_master:add_single_product')

        branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)

        supplier = None
        if supplier_id:
            supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)

        if not name:
            messages.error(request, 'Product name is required')
            return redirect('tronic_master:add_single_product')

        if not identifiers:
            messages.error(request, 'Please enter at least one IMEI or Serial Number')
            return redirect('tronic_master:add_single_product')

        # ✅ Prepare specifications for ProductVariant (NOT Product)
        specs_dict = {}
        if specifications:
            specs_dict['description'] = specifications
        if color:
            specs_dict['color'] = color

        # ✅ Find or create Product (WITHOUT variant fields)
        product = Product.objects.filter(
            tenant=tenant,
            name=name,
            brand=brand,
            model=model
        ).first()

        if not product:
            # ✅ Create Product with CORRECT fields
            product = Product.objects.create(
                tenant=tenant,
                name=name,
                brand=brand,
                model=model,
                category_id=category_id if category_id else None,
                branch=branch,
                supplier=supplier,
                # ✅ These are the correct fields for Product
                default_buying_price=float(buying_price) if buying_price else 0,
                default_selling_price=float(selling_price) if selling_price else 0,
                default_best_price=float(best_price) if best_price else None,
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

                # ✅ Create ProductUnit with CORRECT fields
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

        return redirect('tronic_master:product_detail', product_id=product.id)

    context = {
        'branches': branches,
        'categories': categories,
        'suppliers': suppliers,
        'tenant': tenant,
    }
    return render(request, 'tronic_master/add_single_product.html', context)


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
        buying_price = request.POST.get('buying_price', 0)
        selling_price = request.POST.get('selling_price', 0)
        best_price = request.POST.get('best_price')
        sku_code = request.POST.get('sku_code', '').strip().upper()
        stock_quantity = int(request.POST.get('stock_quantity', 1))
        reorder_level = request.POST.get('reorder_level', 5)
        warranty_months = request.POST.get('warranty_months', 12)
        barcode = request.POST.get('barcode', '').strip().upper()
        color = request.POST.get('color', '').strip()
        description = request.POST.get('description', '').strip()

        if not branch_id:
            messages.error(request, 'Please select a branch')
            return redirect('tronic_master:add_bulk_product')

        branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)

        supplier = None
        if supplier_id:
            supplier = get_object_or_404(Supplier, id=supplier_id, tenant=tenant)

        if not name:
            messages.error(request, 'Product name is required')
            return redirect('tronic_master:add_bulk_product')

        if stock_quantity <= 0:
            messages.error(request, 'Stock quantity must be greater than 0')
            return redirect('tronic_master:add_bulk_product')

        # ✅ TRY TO FIND EXISTING PRODUCT
        product = None
        
        # 1. Try by SKU code (if provided)
        if sku_code:
            product = Product.objects.filter(tenant=tenant, sku_code=sku_code).first()
        
        # 2. Try by Name
        if not product:
            product = Product.objects.filter(tenant=tenant, name=name).first()
        
        # 3. Try by Brand + Model
        if not product and brand and model:
            product = Product.objects.filter(tenant=tenant, brand=brand, model=model).first()

        if product:
            # ✅ UPDATE EXISTING PRODUCT - NO bulk_quantity!
            product.total_quantity += stock_quantity
            product.available_quantity += stock_quantity
            
            if buying_price:
                product.default_buying_price = float(buying_price)
            if selling_price:
                product.default_selling_price = float(selling_price)
            if best_price:
                product.default_best_price = float(best_price)
            
            product.save()

            # ✅ CREATE OR UPDATE BranchStock record
            branch_stock, created = BranchStock.objects.get_or_create(
                tenant=tenant,
                branch=branch,
                product=product,
                defaults={'quantity': 0}
            )
            branch_stock.quantity += stock_quantity
            branch_stock.save()

            # Create stock entry
            StockEntry.objects.create(
                tenant=tenant,
                product_sku=product,
                quantity=stock_quantity,
                entry_type='purchase',
                unit_price=float(buying_price) if buying_price else product.default_buying_price,
                total_amount=stock_quantity * (float(buying_price) if buying_price else product.default_buying_price),
                branch=branch,
                notes=f"Bulk product restock",
                created_by=request.user
            )

            messages.success(request, f'Added {stock_quantity} units to existing product "{product.name}" (SKU: {product.sku_code})')
        else:
            # ✅ CREATE NEW PRODUCT - NO bulk_quantity!
            try:
                product = Product.objects.create(
                    tenant=tenant,
                    name=name,
                    brand=brand,
                    model=model,
                    sku_code=sku_code if sku_code else None,
                    barcode=barcode if barcode else None,
                    category_id=category_id if category_id else None,
                    branch=branch,
                    supplier=supplier,
                    default_buying_price=float(buying_price) if buying_price else 0,
                    default_selling_price=float(selling_price) if selling_price else 0,
                    default_best_price=float(best_price) if best_price else None,
                    description=description,
                    total_quantity=stock_quantity,
                    available_quantity=stock_quantity,
                    reorder_level=int(reorder_level),
                    warranty_months=int(warranty_months),
                    is_active=True,
                    is_discontinued=False, 
                )

                # ✅ CREATE BranchStock record
                BranchStock.objects.create(
                    tenant=tenant,
                    branch=branch,
                    product=product,
                    quantity=stock_quantity
                )

                # Create stock entry
                StockEntry.objects.create(
                    tenant=tenant,
                    product_sku=product,
                    quantity=stock_quantity,
                    entry_type='purchase',
                    unit_price=float(buying_price) if buying_price else 0,
                    total_amount=stock_quantity * (float(buying_price) if buying_price else 0),
                    branch=branch,
                    notes=f"New bulk product added",
                    created_by=request.user
                )

                messages.success(request, f'Product "{product.name}" added successfully with SKU: {product.sku_code}')
                
            except IntegrityError as e:
                if 'brand' in str(e) and 'model' in str(e):
                    existing = Product.objects.filter(
                        tenant=tenant,
                        brand=brand,
                        model=model
                    ).first()
                    
                    if existing:
                        existing.total_quantity += stock_quantity
                        existing.available_quantity += stock_quantity
                        existing.save()
                        
                        messages.warning(request, f'Product with same brand and model found. Added stock to "{existing.name}"')
                    else:
                        messages.error(request, f'Error creating product: {str(e)}')
                else:
                    messages.error(request, f'Error creating product: {str(e)}')
                
                return redirect('tronic_master:product_list')

        return redirect('tronic_master:product_list')

    context = {
        'branches': branches,
        'categories': categories,
        'suppliers': suppliers,
        'tenant': tenant,
    }
    return render(request, 'tronic_master/add_bulk_product.html', context)


@login_required
def edit_bulk_product(request, product_id):
    """Edit bulk product information - SKU CANNOT BE CHANGED"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    product = get_object_or_404(Product, id=product_id, tenant=tenant)

    if not product.category.is_bulk_item:
        messages.error(request, 'This is not a bulk product')
        return redirect('tronic_master:product_detail', product_id=product.id)

    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    suppliers = Supplier.objects.filter(tenant=tenant, is_active=True)

    if request.method == 'POST':
        # ✅ Store original SKU before any changes
        original_sku = product.sku_code
        
        # ✅ Get all POST data
        name = request.POST.get('name', '').strip()
        brand = request.POST.get('brand', '').strip()
        model = request.POST.get('model', '').strip()
        category_id = request.POST.get('category_id')
        branch_id = request.POST.get('branch_id')
        supplier_id = request.POST.get('supplier_id')
        
        # ✅ Barcode is optional
        barcode = request.POST.get('barcode', '').strip().upper()
        
        # ✅ Get color and description
        color = request.POST.get('color', '').strip()
        description = request.POST.get('description', '').strip()
        
        # ✅ Get pricing
        buying_price = request.POST.get('buying_price', 0)
        selling_price = request.POST.get('selling_price', 0)
        best_price = request.POST.get('best_price')
        reorder_level = request.POST.get('reorder_level', 5)
        warranty_months = request.POST.get('warranty_months', 12)
        
        # ✅ ✅ ✅ GET is_active and is_discontinued from POST
        is_active = request.POST.get('is_active') == 'on'
        is_discontinued = request.POST.get('is_discontinued') == 'on'

        if not name:
            messages.error(request, 'Product name is required')
            return redirect('tronic_master:edit_bulk_product', product_id=product.id)

        if not selling_price:
            messages.error(request, 'Selling price is required')
            return redirect('tronic_master:edit_bulk_product', product_id=product.id)

        # Track old branch
        old_branch = product.branch

        # ✅ Update product - KEEP ORIGINAL SKU
        product.name = name
        product.brand = brand
        product.model = model
        product.category_id = category_id if category_id else None
        product.branch_id = branch_id if branch_id else None
        product.supplier_id = supplier_id if supplier_id else None
        
        # ✅ IMPORTANT: Keep the original SKU
        product.sku_code = original_sku  # ❌ DO NOT change this!
        
        # ✅ Update barcode if field exists
        if hasattr(product, 'barcode'):
            product.barcode = barcode if barcode else None
        
        # ✅ Store color in description as JSON
        if color:
            if product.description and isinstance(product.description, dict):
                product.description['color'] = color
            else:
                product.description = {'color': color} if color else {}
        elif product.description and isinstance(product.description, dict):
            product.description.pop('color', None)
        
        # ✅ Update description
        if description:
            if product.description and isinstance(product.description, dict):
                product.description['description'] = description
            else:
                product.description = {'description': description} if description else {}
        
        product.default_buying_price = float(buying_price) if buying_price else 0
        product.default_selling_price = float(selling_price) if selling_price else 0
        product.default_best_price = float(best_price) if best_price else None
        product.reorder_level = int(reorder_level) if reorder_level else 5
        product.warranty_months = int(warranty_months) if warranty_months else 12
        
        # ✅ ✅ ✅ Use the variables we defined
        product.is_active = is_active
        product.is_discontinued = is_discontinued
        
        product.last_modified_by = request.user
        product.save()

        # ✅ If branch changed, update BranchStock records
        if branch_id and old_branch and old_branch.id != int(branch_id):
            new_branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)

            old_stock = BranchStock.objects.filter(
                tenant=tenant,
                branch=old_branch,
                product=product
            ).first()
            if old_stock:
                old_stock.delete()

            BranchStock.objects.create(
                tenant=tenant,
                branch=new_branch,
                product=product,
                quantity=product.available_quantity
            )

        messages.success(request, f'Product "{product.name}" updated successfully!')
        return redirect('tronic_master:product_detail', product_id=product.id)

    context = {
        'product': product,
        'branches': branches,
        'categories': categories,
        'suppliers': suppliers,
        'tenant': tenant,
    }
    return render(request, 'tronic_master/edit_bulk_product.html', context)


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
        return redirect('tronic_master:product_detail', product_id=product.id)

    # Get branches for the form
    branches = Branch.objects.filter(tenant=tenant, is_active=True)

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 0))
        buying_price = request.POST.get('buying_price', product.default_buying_price)
        selling_price = request.POST.get('selling_price', product.default_selling_price)
        branch_id = request.POST.get('branch_id')
        notes = request.POST.get('notes', '')

        if quantity <= 0:
            messages.error(request, 'Please enter a valid quantity')
            return redirect('tronic_master:restock_product', product_id=product.id)

        # Get branch
        branch = None
        if branch_id:
            branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)
        else:
            branch = product.branch

        if not branch:
            messages.error(request, 'Please select a branch')
            return redirect('tronic_master:restock_product', product_id=product.id)

        # ✅ Only update total_quantity and available_quantity
        product.total_quantity += quantity
        product.available_quantity += quantity

        if float(buying_price) != product.default_buying_price:
            product.default_buying_price = float(buying_price)
        if float(selling_price) != product.default_selling_price:
            product.default_selling_price = float(selling_price)

        product.save()

        # ✅ UPDATE BranchStock record
        branch_stock, created = BranchStock.objects.get_or_create(
            tenant=tenant,
            branch=branch,
            product=product,
            defaults={'quantity': 0}
        )
        branch_stock.quantity += quantity
        branch_stock.save()

        # Create stock entry
        StockEntry.objects.create(
            tenant=tenant,
            product_sku=product,
            quantity=quantity,
            entry_type='purchase',
            unit_price=float(buying_price),
            total_amount=quantity * float(buying_price),
            branch=branch,
            notes=f"Restock: {notes}",
            created_by=request.user
        )

        messages.success(request, f'Successfully added {quantity} units to {product.name} at {branch.name}')
        return redirect('tronic_master:product_detail', product_id=product.id)

    context = {
        'product': product,
        'branches': branches,
        'tenant': tenant,
    }
    return render(request, 'tronic_master/restock_product.html', context)



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
            return redirect('tronic_master:edit_product', product_id=product.id)

        if not selling_price:
            messages.error(request, 'Selling price is required')
            return redirect('tronic_master:edit_product', product_id=product.id)

        # ✅ Track old values for sync
        old_data = {
            'name': product.name,
            'brand': product.brand,
            'model': product.model,
            'default_buying_price': float(product.default_buying_price),
            'default_selling_price': float(product.default_selling_price),
            'reorder_level': product.reorder_level,
            'is_active': product.is_active,
            'is_discontinued': product.is_discontinued,
        }

        # ✅ Update Product with CORRECT fields
        product.name = name
        product.brand = brand
        product.model = model
        product.default_buying_price = float(buying_price) if buying_price else 0  # ✅ FIXED
        product.default_selling_price = float(selling_price) if selling_price else 0  # ✅ FIXED
        product.reorder_level = int(reorder_level) if reorder_level else 5
        product.is_active = is_active
        product.is_discontinued = is_discontinued

        # ✅ Update relations
        if category_id:
            product.category_id = category_id
        if branch_id:
            product.branch_id = branch_id

        # ✅ If you want to store description, use the description field (not specifications)
        product.description = description  # ✅ FIXED - using the correct field

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
                        'default_buying_price': str(product.default_buying_price),
                        'default_selling_price': str(product.default_selling_price),
                        'reorder_level': product.reorder_level,
                        'is_active': product.is_active,
                        'is_discontinued': product.is_discontinued,
                        'description': product.description,
                        'previous_data': old_data,
                        'tenant_id': tenant.id,
                    },
                    priority=5
                )
                logger.debug(f"✅ Queued Product update sync: {product.sku_code}")
            except Exception as e:
                logger.error(f"Failed to queue Product sync: {e}")

        messages.success(request, 'Product updated successfully!')
        return redirect('tronic_master:product_detail', product_id=product.id)

    context = {
        'product': product,
        'branches': branches,
        'categories': categories,
        'tenant': tenant,
    }
    return render(request, 'tronic_master/edit_product.html', context)



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
    return redirect('tronic_master:product_list')


@login_required
def assign_products_to_agent(request):
    """Assign products to agents"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    # Get users with system role 'user'
    sales_agents = User.objects.filter(
        tenant=tenant,
        role='user',
        is_active=True
    ).order_by('username')

    # Also include users with custom role assignments
    from apps.shared.permissions.models import UserRoleAssignment

    users_with_custom_roles = UserRoleAssignment.objects.filter(
        is_active=True
    ).values_list('user_id', flat=True).distinct()

    custom_role_users = User.objects.filter(
        tenant=tenant,
        id__in=users_with_custom_roles,
        is_active=True
    ).exclude(id__in=sales_agents.values_list('id', flat=True))

    # Combine both querysets
    all_agents = list(sales_agents) + list(custom_role_users)

    # If no agents found, show all users as fallback
    if not all_agents:
        all_agents = User.objects.filter(
            tenant=tenant,
            is_active=True
        ).exclude(
            role='super_admin'
        ).order_by('username')

    # Get all unassigned product units
    products = ProductUnit.objects.filter(
        tenant=tenant,
        status='available',
        current_owner__isnull=True
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
            'model': unit.product.model,
            'imei': unit.imei_number or '',
            'serial': unit.serial_number or '',
            'selling_price': float(unit.unit_selling_price or unit.product.default_selling_price),
            'branch_name': unit.branch.name if unit.branch else 'Main Shop',
        })

    if request.method == 'POST':
        agent_id = request.POST.get('agent_id')
        product_ids = request.POST.getlist('product_ids')

        if not agent_id:
            messages.error(request, 'Please select a sales agent')
            return redirect('tronic_master:assign_products_to_agent')

        if not product_ids:
            messages.error(request, 'Please select at least one product to assign')
            return redirect('tronic_master:assign_products_to_agent')

        agent = get_object_or_404(User, id=agent_id, tenant=tenant)

        assigned_count = 0
        errors = []

        for product_id in product_ids:
            try:
                unit = ProductUnit.objects.get(
                    id=product_id,
                    tenant=tenant,
                    status='available',
                    current_owner__isnull=True
                )

                unit.current_owner = agent
                unit.assigned_date = timezone.now()
                unit.assigned_by = request.user
                unit.save()
                assigned_count += 1

            except ProductUnit.DoesNotExist:
                errors.append(f'Product unit {product_id} not found or already assigned')
            except Exception as e:
                errors.append(f'Error assigning product {product_id}: {str(e)}')

        if assigned_count > 0:
            messages.success(request, f'Successfully assigned {assigned_count} product(s) to {agent.get_full_name() or agent.username}')

        if errors:
            for error in errors[:5]:
                messages.warning(request, error)

        return redirect('tronic_master:move_product_ownership')

    context = {
        'tenant': tenant,
        'sales_agents': all_agents,
        'products': product_list,
        'active_tab': 'assign',
    }
    return render(request, 'tronic_master/assign_products.html', context)




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
        return redirect('tronic_master:product_detail', product_id=product.id)

    if request.method == 'POST':
        adjustment_type = request.POST.get('adjustment_type')
        quantity = int(request.POST.get('quantity', 0))
        reason = request.POST.get('reason', '')

        if quantity <= 0:
            messages.error(request, 'Please enter a valid quantity')
            return redirect('tronic_master:product_detail', product_id=product.id)

        if adjustment_type == 'add':
            # ✅ REMOVE bulk_quantity
            product.available_quantity += quantity

            StockEntry.objects.create(
                tenant=tenant,
                product_sku=product,
                quantity=quantity,
                entry_type='adjustment',
                unit_price=product.default_buying_price,
                total_amount=quantity * product.default_buying_price,
                notes=f"Stock addition: {reason}",
                created_by=request.user
            )
            messages.success(request, f'Added {quantity} units to {product.name}')

        elif adjustment_type == 'remove':
            # ✅ REMOVE bulk_quantity
            if quantity > product.total_quantity:
                return redirect('tronic_master:product_detail', product_id=product.id)

            product.total_quantity -= quantity
            product.available_quantity -= quantity

            StockEntry.objects.create(
                tenant=tenant,
                product_sku=product,
                quantity=-quantity,
                entry_type='adjustment',
                unit_price=product.default_buying_price,
                total_amount=-(quantity * product.default_buying_price),
                notes=f"Stock removal: {reason}",
                created_by=request.user
            )
            messages.success(request, f'Removed {quantity} units from {product.name}')

        elif adjustment_type == 'damage':
            # ✅ REMOVE bulk_quantity
            if quantity > product.total_quantity:
                messages.error(request, f'Cannot mark {quantity} units as damaged. Only {product.total_quantity} units in stock.')

            product.total_quantity -= quantity
            product.available_quantity -= quantity
            product.damaged_quantity += quantity

            StockEntry.objects.create(
                tenant=tenant,
                product_sku=product,
                quantity=-quantity,
                entry_type='damage',
                unit_price=product.default_buying_price,
                total_amount=-(quantity * product.default_buying_price),
                notes=f"Damaged/Loss: {reason}",
                created_by=request.user
            )
            messages.success(request, f'Marked {quantity} units as damaged/loss for {product.name}')

        product.save()
        return redirect('tronic_master:product_detail', product_id=product.id)

    return redirect('tronic_master:product_detail', product_id=product.id)


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
        buying_price = request.POST.get('buying_price', product.default_buying_price)
        selling_price = request.POST.get('selling_price', product.default_selling_price)
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
            return redirect('tronic_master:add_unit', product_id=product.id)

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

        return redirect('tronic_master:product_detail', product_id=product.id)

    context = {
        'product': product,
        'branches': branches,
        'tenant': tenant,
    }
    return render(request, 'tronic_master/add_unit.html', context)


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
            return redirect('tronic_master:edit_unit', unit_id=unit.id)

        # Check uniqueness
        if imei_number and ProductUnit.objects.filter(tenant=tenant, imei_number=imei_number).exclude(id=unit.id).exists():
            messages.error(request, f'IMEI "{imei_number}" already exists')
            return redirect('tronic_master:edit_unit', unit_id=unit.id)

        if serial_number and ProductUnit.objects.filter(tenant=tenant, serial_number=serial_number).exclude(id=unit.id).exists():
            messages.error(request, f'Serial number "{serial_number}" already exists')
            return redirect('tronic_master:edit_unit', unit_id=unit.id)

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
        return redirect('tronic_master:product_detail', product_id=product.id)

    context = {
        'unit': unit,
        'product': product,
        'branches': branches,
        'tenant': tenant,
    }
    return render(request, 'tronic_master/edit_unit.html', context)


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
    return redirect('tronic_master:product_detail', product_id=product.id)


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
    return render(request, 'tronic_master/low_stock_alert.html', context)


# ============================================
# PRODUCT TRANSFER VIEWS
# ============================================

@login_required
def move_product_ownership(request):
    """Move products between branches or users"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    # ✅ Handle POST request
    if request.method == 'POST':
        to_user_id = request.POST.get('to_user_id')
        product_ids = request.POST.getlist('product_ids')

        if not to_user_id:
            messages.error(request, 'Please select a destination user')
            return redirect('tronic_master:move_product_ownership')

        if not product_ids:
            messages.error(request, 'Please select at least one product to move')
            return redirect('tronic_master:move_product_ownership')

        # Get the destination user
        to_user = get_object_or_404(User, id=to_user_id, tenant=tenant)

        moved_count = 0
        errors = []

        for product_id in product_ids:
            try:
                unit = ProductUnit.objects.get(
                    id=product_id,
                    tenant=tenant,
                    status='available'
                )

                # Check if unit is already assigned to this user
                if unit.current_owner and unit.current_owner.id == to_user.id:
                    errors.append(f'Unit {unit.imei_number or unit.serial_number} is already assigned to {to_user.get_full_name()}')
                    continue

                # Move the unit
                unit.current_owner = to_user
                unit.assigned_date = timezone.now()
                unit.assigned_by = request.user
                unit.save()
                moved_count += 1

            except ProductUnit.DoesNotExist:
                errors.append(f'Product unit {product_id} not found or not available')
            except Exception as e:
                errors.append(f'Error moving unit {product_id}: {str(e)}')

        if moved_count > 0:
            messages.success(request, f'Successfully moved {moved_count} unit(s) to {to_user.get_full_name()}')

        if errors:
            for error in errors[:5]:
                messages.warning(request, error)

        return redirect('tronic_master:move_product_ownership')

    # ✅ GET request - show the form
    # Get all active users in the tenant (excluding super admins)
    # This includes users with 'admin', 'user' roles, and any project roles
    from apps.shared.permissions.models import UserRoleAssignment

    # Get users with any project role (manager, cashier, sales_agent, etc.)
    users_with_project_roles = UserRoleAssignment.objects.filter(
        is_active=True
    ).values_list('user_id', flat=True)

    # Get all active users in the tenant (excluding super_admin)
    users = User.objects.filter(
        tenant=tenant,
        is_active=True
    ).exclude(
        role='super_admin'
    ).order_by('first_name', 'last_name')

    # ✅ For each user, calculate the actual available stock count
    for user in users:
        # Count only available and reserved units (not sold)
        user.available_stock_count = ProductUnit.objects.filter(
            tenant=tenant,
            current_owner=user,
            status__in=['available', 'reserved']  # ✅ EXCLUDE sold units
        ).count()

        # Check if user has any project role
        user.has_project_role = user.id in users_with_project_roles

    # ✅ Get all product units that are available
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
        'users': users,  # Now includes all users (not just sales_agents)
        'products': product_units,
        'active_tab': 'transfer',
    }
    return render(request, 'tronic_master/move_product_ownership.html', context)


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
    return render(request, 'tronic_master/barcode_label.html', context)


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
    return render(request, 'tronic_master/barcode_label_list.html', context)


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
    return render(request, 'tronic_master/print_labels.html', context)


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
                price = unit.unit_selling_price or product.default_selling_price
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
                'identifier': product.sku_code or product.sku_code,
                'brand': product.brand,
                'model': product.model,
                'price': float(product.default_selling_price),
                'category': product.category.name if product.category else 'Uncategorized',
                'is_single': False,
            })

    context = {
        'tenant': tenant,
        'items': items,
        'active_tab': 'barcodes',
    }
    return render(request, 'tronic_master/bulk_print_labels.html', context)



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
            return redirect('tronic_master:import_products')

        if not file.name.endswith(('.xlsx', '.xls', '.csv')):
            messages.error(request, 'Please upload Excel or CSV file')
            return redirect('tronic_master:import_products')

        result = import_products_from_excel(file, tenant.id, import_type)

        if result.get('error'):
            messages.error(request, result['error'])
        else:
            msg = f"✅ Import complete! Created: {result['created']}, Updated: {result['updated']}"
            messages.success(request, msg)
            if result['errors']:
                for err in result['errors'][:5]:
                    messages.warning(request, err)

        return redirect('tronic_master:product_list')

    context = {'tenant': tenant}
    return render(request, 'tronic_master/import_products.html', context)


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
    total_stock_items = 0
    total_stock_value = Decimal('0.00')

    for branch in branches:
        # ============================================
        # GET BULK STOCK (BranchStock)
        # ============================================
        bulk_stocks = BranchStock.objects.filter(
            tenant=tenant,
            branch=branch
        ).select_related('product')

        bulk_quantity = bulk_stocks.aggregate(total=Sum('quantity'))['total'] or 0

        # Calculate bulk stock value
        bulk_value = Decimal('0.00')
        for stock in bulk_stocks:
            bulk_value += stock.quantity * stock.product.default_buying_price

        # ============================================
        # GET SINGLE ITEMS (ProductUnit)
        # ============================================
        single_units = ProductUnit.objects.filter(
            tenant=tenant,
            branch=branch,
            status='available'
        ).select_related('product')

        single_count = single_units.count()

        # Calculate single items value
        single_value = Decimal('0.00')
        for unit in single_units:
            price = unit.unit_buying_price or unit.product.default_buying_price
            single_value += price

        # ============================================
        # COMBINE TOTALS
        # ============================================
        total_quantity = bulk_quantity + single_count
        total_value = bulk_value + single_value

        # Get product count (distinct products with stock)
        product_ids = set()
        for stock in bulk_stocks:
            product_ids.add(stock.product_id)
        for unit in single_units:
            product_ids.add(unit.product_id)

        product_count = len(product_ids)

        # Get unit count (total units in branch - all statuses)
        unit_count = ProductUnit.objects.filter(
            tenant=tenant,
            branch=branch
        ).count()

        # Add to totals
        total_stock_items += total_quantity
        total_stock_value += total_value

        branch_stock_data.append({
            'branch': branch,
            'stock_count': total_quantity,  # This is the total stock quantity
            'product_count': product_count,
            'unit_count': unit_count,
            'stock_value': total_value,
            'bulk_quantity': bulk_quantity,
            'single_count': single_count,
            'bulk_value': bulk_value,
            'single_value': single_value,
        })

    context = {
        'tenant': tenant,
        'branch_stock_data': branch_stock_data,
        'total_stock_items': total_stock_items,
        'total_stock_value': total_stock_value,
        'active_tab': 'stock',
    }
    return render(request, 'tronic_master/branch_stock_list.html', context)


@login_required
def branch_stock_detail(request, branch_id):
    """View detailed stock for a specific branch"""
    tenant = request.user.tenant
    branch = get_object_or_404(Branch, id=branch_id, tenant=tenant)

    # ============================================
    # GET BULK STOCK (BranchStock)
    # ============================================
    bulk_stocks = BranchStock.objects.filter(
        tenant=tenant,
        branch=branch
    ).select_related('product', 'product__category')

    bulk_items = []
    bulk_total_value = Decimal('0.00')
    bulk_total_quantity = 0

    for stock in bulk_stocks:
        stock_value = stock.quantity * stock.product.default_buying_price
        bulk_total_value += stock_value
        bulk_total_quantity += stock.quantity

        bulk_items.append({
            'type': 'bulk',
            'product': stock.product,
            'quantity': stock.quantity,
            'unit_price': stock.product.default_buying_price,
            'selling_price': stock.product.default_selling_price,
            'total_value': stock_value,
            'category': stock.product.category.name if stock.product.category else None,
        })

    # ============================================
    # GET SINGLE ITEMS (ProductUnit)
    # ============================================
    single_units = ProductUnit.objects.filter(
        tenant=tenant,
        branch=branch,
        status='available'
    ).select_related('product', 'product__category')

    single_items = []
    single_total_value = Decimal('0.00')
    single_total_quantity = 0

    for unit in single_units:
        price = unit.unit_buying_price or unit.product.default_buying_price
        single_total_value += price
        single_total_quantity += 1

        single_items.append({
            'type': 'single',
            'product': unit.product,
            'unit': unit,
            'quantity': 1,
            'unit_price': price,
            'selling_price': unit.unit_selling_price or unit.product.default_selling_price,
            'total_value': price,
            'category': unit.product.category.name if unit.product.category else None,
            'identifier': unit.imei_number or unit.serial_number or 'No ID',
        })

    # Combine both lists
    all_items = bulk_items + single_items

    # Sort by product name
    all_items.sort(key=lambda x: x['product'].name)

    # Calculate totals
    total_value = bulk_total_value + single_total_value
    total_quantity = bulk_total_quantity + single_total_quantity

    context = {
        'tenant': tenant,
        'branch': branch,
        'all_items': all_items,
        'bulk_count': len(bulk_items),
        'single_count': len(single_items),
        'total_items': len(all_items),
        'total_value': total_value,
        'total_quantity': total_quantity,
        'bulk_total_value': bulk_total_value,
        'single_total_value': single_total_value,
        'bulk_total_quantity': bulk_total_quantity,
        'single_total_quantity': single_total_quantity,
        'active_tab': 'stock',
    }
    return render(request, 'tronic_master/branch_stock_detail.html', context)




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
            return redirect('tronic_master:transfer_stock')

        if from_branch_id == to_branch_id:
            messages.error(request, 'Source and destination branches cannot be the same')
            return redirect('tronic_master:transfer_stock')

        if quantity <= 0:
            messages.error(request, 'Quantity must be greater than 0')
            return redirect('tronic_master:transfer_stock')

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
                return redirect('tronic_master:transfer_stock')

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
            # ============================================
            # BULK PRODUCT - UPDATE BranchStock
            # ============================================
            # Get from branch stock
            from_stock, created = BranchStock.objects.get_or_create(
                tenant=tenant,
                branch=from_branch,
                product=product,
                defaults={'quantity': 0}
            )

            if from_stock.quantity < quantity:
                messages.error(request, f'Only {from_stock.quantity} units available in {from_branch.name}')
                return redirect('tronic_master:transfer_stock')

            # Remove from source
            from_stock.quantity -= quantity
            from_stock.save()

            # Add to destination
            to_stock, created = BranchStock.objects.get_or_create(
                tenant=tenant,
                branch=to_branch,
                product=product,
                defaults={'quantity': 0}
            )
            to_stock.quantity += quantity
            to_stock.save()

            # ✅ REMOVE bulk_quantity - it doesn't exist
            # ✅ Only update total_quantity and available_quantity
            product.total_quantity -= quantity
            product.available_quantity -= quantity

            # Create stock entry for tracking
            StockEntry.objects.create(
                tenant=tenant,
                product_sku=product,
                quantity=-quantity,
                entry_type='adjustment',
                unit_price=product.default_buying_price,
                total_amount=-(quantity * product.default_buying_price),
                branch=from_branch,
                notes=f"Transferred to {to_branch.name}: {reason}",
                created_by=request.user
            )

            # Create stock entry for destination
            StockEntry.objects.create(
                tenant=tenant,
                product_sku=product,
                quantity=quantity,
                entry_type='adjustment',
                unit_price=product.default_buying_price,
                total_amount=quantity * product.default_buying_price,
                branch=to_branch,
                notes=f"Received from {from_branch.name}: {reason}",
                created_by=request.user
            )

            messages.success(request, f'Transferred {quantity} units from {from_branch.name} to {to_branch.name}')

        return redirect('tronic_master:branch_stock_list')

    context = {
        'tenant': tenant,
        'branches': branches,
        'products': products,
        'active_tab': 'transfer',
    }
    return render(request, 'tronic_master/transfer_stock.html', context)


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

    # Base queryset
    stock_entries = StockEntry.objects.filter(tenant=tenant).select_related(
        'product_sku', 'product_unit', 'branch', 'created_by'
    ).order_by('-created_at')

    # Filter by product if provided
    if product_id:
        product = get_object_or_404(Product, id=product_id, tenant=tenant)
        stock_entries = stock_entries.filter(
            Q(product_sku=product) | Q(product_unit__product=product)
        )

    # Apply filters from GET parameters
    search_query = request.GET.get('q', '')
    entry_type = request.GET.get('entry_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if search_query:
        stock_entries = stock_entries.filter(
            Q(product_sku__name__icontains=search_query) |
            Q(product_sku__sku_code__icontains=search_query) |
            Q(product_unit__product__name__icontains=search_query) |
            Q(product_unit__product__sku_code__icontains=search_query) |
            Q(product_unit__imei_number__icontains=search_query) |
            Q(product_unit__serial_number__icontains=search_query)
        )

    if entry_type:
        stock_entries = stock_entries.filter(entry_type=entry_type)

    if date_from:
        stock_entries = stock_entries.filter(created_at__date__gte=date_from)

    if date_to:
        stock_entries = stock_entries.filter(created_at__date__lte=date_to)

    # Calculate statistics
    total_entries = stock_entries.count()
    total_in = stock_entries.filter(quantity__gt=0).aggregate(
        total=Sum('quantity')
    )['total'] or 0

    total_out = stock_entries.filter(quantity__lt=0).aggregate(
        total=Sum('quantity')
    )['total'] or 0

    net_movement = total_in + total_out  # total_out is negative

    # Pagination
    paginator = Paginator(stock_entries, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'tenant': tenant,
        'stock_entries': page_obj,
        'search_query': search_query,
        'entry_type': entry_type,
        'date_from': date_from,
        'date_to': date_to,
        'total_entries': total_entries,
        'total_in': total_in,
        'total_out': abs(total_out),  # Show as positive number
        'net_movement': net_movement,
        'active_tab': 'stock',
    }
    return render(request, 'tronic_master/stock_history.html', context)



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

    # Get all products with stock info and annotated stock value
    products = Product.objects.filter(
        tenant=tenant,
        is_active=True
    ).select_related('category', 'supplier', 'branch').annotate(
        stock_value_annotated=F('available_quantity') * F('default_buying_price')
    )

    # Total stock value
    total_value = products.aggregate(
        total=Sum('stock_value_annotated')
    )['total'] or Decimal('0.00')

    # Total quantity
    total_quantity = products.aggregate(
        total=Sum('available_quantity')
    )['total'] or 0

    # Products by category
    category_stats = products.values('category__name').annotate(
        count=Count('id'),
        total_stock=Sum('available_quantity'),
        total_value=Sum('stock_value_annotated')
    ).order_by('-total_value')

    # Low stock and out of stock counts
    low_stock_count = products.filter(
        available_quantity__lte=F('reorder_level'),
        available_quantity__gt=0
    ).count()

    out_of_stock_count = products.filter(available_quantity=0).count()

    # Get categories for filter
    categories = Category.objects.filter(tenant=tenant, is_active=True)

    # Pagination
    paginator = Paginator(products, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'tenant': tenant,
        'products': page_obj,
        'total_value': total_value,
        'total_quantity': total_quantity,
        'category_stats': category_stats,
        'total_products': products.count(),
        'categories': categories,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'active_tab': 'reports',
    }
    return render(request, 'tronic_master/stock_report.html', context)

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

    # Base queryset
    damaged_units = ProductUnit.objects.filter(
        tenant=tenant,
        status__in=['damaged', 'stolen', 'lost', 'writeoff']
    ).select_related('product', 'branch', 'supplier').order_by('-updated_at')

    # Apply filters
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    branch_filter = request.GET.get('branch', '')

    if search_query:
        damaged_units = damaged_units.filter(
            Q(product__name__icontains=search_query) |
            Q(product__sku_code__icontains=search_query) |
            Q(imei_number__icontains=search_query) |
            Q(serial_number__icontains=search_query)
        )

    if status_filter:
        damaged_units = damaged_units.filter(status=status_filter)

    if branch_filter:
        damaged_units = damaged_units.filter(branch_id=branch_filter)

    # Calculate total value lost
    total_value = Decimal('0.00')
    stolen_count = 0
    lost_count = 0

    for unit in damaged_units:
        price = unit.unit_buying_price or unit.product.default_buying_price
        total_value += price
        if unit.status == 'stolen':
            stolen_count += 1
        elif unit.status == 'lost':
            lost_count += 1

    # Get branches for filter
    branches = Branch.objects.filter(tenant=tenant, is_active=True)

    # Pagination
    paginator = Paginator(damaged_units, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'tenant': tenant,
        'damaged_units': page_obj,
        'branches': branches,
        'search_query': search_query,
        'status_filter': status_filter,
        'branch_filter': branch_filter,
        'total_damaged': damaged_units.count(),
        'total_value': total_value,
        'stolen_count': stolen_count,
        'lost_count': lost_count,
        'active_tab': 'reports',
    }
    return render(request, 'tronic_master/damaged_units_report.html', context)



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
    buying_price = data.get('buying_price', product.default_buying_price)
    selling_price = data.get('selling_price', product.default_selling_price)
    best_price = data.get('best_price', product.default_best_price)
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
                'selling_price': float(new_unit.unit_selling_price or product.default_selling_price),
                'buying_price': float(new_unit.unit_buying_price or product.default_buying_price)
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
        'buying_price': safe_float(unit.unit_buying_price) or safe_float(unit.product.default_buying_price),
        'selling_price': safe_float(unit.unit_selling_price) or safe_float(unit.product.default_selling_price),
        'best_price': safe_float(unit.best_price) or safe_float(unit.product.default_best_price),
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








# ============================================
# MY STOCK - LIST VIEW
# ============================================

@login_required
def my_stock(request):
    """
    View stock - Sales Agent sees assigned stock, Admin/Superadmin sees all stock
    """
    tenant = request.user.tenant
    user = request.user

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    # ✅ Check if user is admin or superadmin
    is_admin = is_admin_user(user)
    
    # ✅ DEBUG: Log the admin status
    logger.info(f"my_stock - User: {user.username}, Is Admin: {is_admin}")
    logger.info(f"my_stock - User role: {user.role if hasattr(user, 'role') else 'No role'}")
    
    # ✅ Get product units based on user role
    if is_admin:
        # Admin/Superadmin - See ALL product units (all branches)
        my_units = ProductUnit.objects.filter(
            tenant=tenant,
            status__in=['available', 'reserved']
        ).select_related(
            'product',
            'product__category',
            'branch',
            'current_owner'
        ).order_by('-created_at', 'product__name')
        
        logger.info(f"Admin view: Found {my_units.count()} units")
        
        # Get all sold units for stats
        sold_units = ProductUnit.objects.filter(
            tenant=tenant,
            status='sold'
        ).count()
        
        # Get all units for stats
        all_available_units = ProductUnit.objects.filter(
            tenant=tenant,
            status='available'
        ).count()
        all_reserved_units = ProductUnit.objects.filter(
            tenant=tenant,
            status='reserved'
        ).count()
        all_total_units = ProductUnit.objects.filter(
            tenant=tenant,
            status__in=['available', 'reserved']
        ).count()
        
        # Get damaged units for stats
        damaged_units = ProductUnit.objects.filter(
            tenant=tenant,
            status__in=['damaged', 'stolen', 'lost', 'writeoff']
        ).count()
        
        # Get unique products
        products = my_units.values('product').distinct()
        total_products = products.count()
        
        # Calculate total value of all stock
        total_value = 0
        for unit in my_units:
            price = unit.unit_selling_price or unit.product.default_selling_price
            total_value += float(price)
        
    else:
        # Regular Sales Agent - See only their assigned stock
        my_units = ProductUnit.objects.filter(
            tenant=tenant,
            current_owner=user,
            status__in=['available', 'reserved']
        ).select_related(
            'product',
            'product__category',
            'branch'
        ).order_by('-assigned_date', 'product__name')
        
        logger.info(f"Regular user view: Found {my_units.count()} units for user {user.username}")
        
        # Count statistics for sales agent
        all_available_units = my_units.filter(status='available').count()
        all_reserved_units = my_units.filter(status='reserved').count()
        all_total_units = my_units.count()
        
        sold_units = ProductUnit.objects.filter(
            tenant=tenant,
            current_owner=user,
            status='sold'
        ).count()
        
        damaged_units = ProductUnit.objects.filter(
            tenant=tenant,
            current_owner=user,
            status__in=['damaged', 'stolen', 'lost', 'writeoff']
        ).count()
        
        # Get unique products
        products = my_units.values('product').distinct()
        total_products = products.count()
        
        # Calculate total value of assigned stock
        total_value = 0
        for unit in my_units:
            price = unit.unit_selling_price or unit.product.default_selling_price
            total_value += float(price)

    # ✅ Apply search filter
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    if search_query:
        my_units = my_units.filter(
            Q(product__name__icontains=search_query) |
            Q(product__sku_code__icontains=search_query) |
            Q(product__brand__icontains=search_query) |
            Q(product__model__icontains=search_query) |
            Q(imei_number__icontains=search_query) |
            Q(serial_number__icontains=search_query)
        )

    if status_filter:
        my_units = my_units.filter(status=status_filter)

    # ✅ Group by product for better display
    grouped_stock = {}
    for unit in my_units:
        product_name = unit.product.name
        if product_name not in grouped_stock:
            grouped_stock[product_name] = {
                'product': unit.product,
                'units': [],
                'total_available': 0,
                'total_reserved': 0,
                'total_value': 0,
                'branch': unit.branch.name if unit.branch else 'Main Shop',
            }
        grouped_stock[product_name]['units'].append(unit)
        if unit.status == 'available':
            grouped_stock[product_name]['total_available'] += 1
        elif unit.status == 'reserved':
            grouped_stock[product_name]['total_reserved'] += 1
        price = unit.unit_selling_price or unit.product.default_selling_price
        grouped_stock[product_name]['total_value'] += float(price)

    # Pagination
    paginator = Paginator(my_units, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'tenant': tenant,
        'user': user,
        'my_units': page_obj,
        'is_admin': is_admin,
        'total_units': all_total_units,
        'available_units': all_available_units,
        'reserved_units': all_reserved_units,
        'sold_units': sold_units,
        'damaged_units': damaged_units,
        'total_products': total_products,
        'total_value': total_value,
        'grouped_stock': grouped_stock,
        'search_query': search_query,
        'status_filter': status_filter,
        'active_tab': 'my_stock',
    }
    return render(request, 'tronic_master/my_stock.html', context)


# ============================================
# MY STOCK - DETAIL VIEW
# ============================================

@login_required
def my_stock_detail(request, unit_id):
    """
    Sales Agent - View details of a specific stock unit
    """
    tenant = request.user.tenant
    user = request.user

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    # Check if user is admin
    is_admin = is_admin_user(user)

    # Get the unit
    if is_admin:
        # Admin can view any unit
        unit = get_object_or_404(
            ProductUnit,
            id=unit_id,
            tenant=tenant
        )
    else:
        # Regular user can only view their assigned units
        unit = get_object_or_404(
            ProductUnit,
            id=unit_id,
            tenant=tenant,
            current_owner=user
        )

    # Get sale history for this unit
    sale_items = SaleItem.objects.filter(
        product_unit=unit
    ).select_related('sale').order_by('-sale__created_at')

    context = {
        'tenant': tenant,
        'unit': unit,
        'sale_items': sale_items,
        'is_admin': is_admin,
        'active_tab': 'my_stock',
    }
    return render(request, 'tronic_master/my_stock_detail.html', context)


# ============================================
# MY STOCK - SELL VIEW
# ============================================

@login_required
def my_stock_sell(request, unit_id):
    """
    Sales Agent - Sell a unit from their stock
    """
    tenant = request.user.tenant
    user = request.user

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    # Check if user is admin
    is_admin = is_admin_user(user)

    # Get the unit with proper permissions
    try:
        if is_admin:
            unit = ProductUnit.objects.filter(
                id=unit_id,
                tenant=tenant,
                status='available'
            ).select_related('product', 'branch', 'current_owner').first()
        else:
            unit = ProductUnit.objects.filter(
                id=unit_id,
                tenant=tenant,
                current_owner=user,
                status='available'
            ).select_related('product', 'branch', 'current_owner').first()
        
        if not unit:
            messages.error(request, f'Unit with ID {unit_id} not found or not available.')
            return redirect('tronic_master:my_stock')
        
        # Check if user has permission to sell this unit (for admin, they can sell any)
        if not is_admin and unit.current_owner != user:
            messages.error(
                request, 
                f'You do not have permission to sell this unit. It is assigned to {unit.current_owner.get_full_name() or unit.current_owner.username if unit.current_owner else "another agent"}.'
            )
            return redirect('tronic_master:my_stock')
            
    except Exception as e:
        logger.error(f"Error fetching unit {unit_id}: {str(e)}")
        messages.error(request, 'An error occurred while processing your request.')
        return redirect('tronic_master:my_stock')

    if request.method == 'POST':
        # Get all fields from the form
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        customer_id_number = request.POST.get('customer_id_number', '').strip()
        next_of_kin_name = request.POST.get('next_of_kin_name', '').strip()
        next_of_kin_phone = request.POST.get('next_of_kin_phone', '').strip()
        next_of_kin_relationship = request.POST.get('next_of_kin_relationship', '').strip()
        selling_price = request.POST.get('selling_price', '').strip()
        payment_method = request.POST.get('payment_method', 'mpesa').strip()

        # Validate required fields
        if not customer_name:
            messages.error(request, 'Customer name is required')
            return redirect('tronic_master:my_stock_sell', unit_id=unit.id)

        if not customer_phone:
            messages.error(request, 'Customer phone number is required')
            return redirect('tronic_master:my_stock_sell', unit_id=unit.id)

        if not selling_price:
            messages.error(request, 'Selling price is required')
            return redirect('tronic_master:my_stock_sell', unit_id=unit.id)

        try:
            selling_price = Decimal(str(selling_price))
            if selling_price <= 0:
                messages.error(request, 'Selling price must be greater than 0')
                return redirect('tronic_master:my_stock_sell', unit_id=unit.id)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid selling price')
            return redirect('tronic_master:my_stock_sell', unit_id=unit.id)

        # Double-check if unit is still available (could have been sold in another tab)
        unit.refresh_from_db()
        if unit.status != 'available':
            messages.error(request, f'Unit is no longer available (Status: {unit.get_status_display()})')
            return redirect('tronic_master:my_stock')

        # Create or get customer
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

        # Update customer if exists and fields are provided
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

        # ✅ FIXED: Let the model generate the invoice number automatically
        # Do NOT manually generate invoice_no - Sale.save() handles it
        sale = Sale.objects.create(
            tenant=tenant,
            customer=customer,
            cashier=user,
            customer_name=customer_name,
            customer_phone=customer_phone,
            # invoice_no is AUTO-GENERATED by Sale.save()
            subtotal=selling_price,
            total=selling_price,
            payment_method=payment_method,
            status='completed',
            tax_inclusive=True,
            branch=unit.branch,
            source='agent'  # ✅ Mark as agent sale
        )

        # Create sale item
        sale_item = SaleItem.objects.create(
            sale=sale,
            product=unit.product,
            product_unit=unit,
            quantity=1,
            price=selling_price,
            subtotal=selling_price
        )

        # ✅ Mark unit as sold and CLEAR the owner
        unit.status = 'sold'
        unit.sold_at_price = selling_price
        unit.sold_date = timezone.now()
        unit.sold_by = user
        unit.current_owner = None  # ✅ IMPORTANT: Clear the owner
        unit.save()

        # Update product quantities
        unit.product.update_quantities()

        # Update customer total spent
        customer.total_spent = (customer.total_spent or Decimal('0')) + selling_price
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
                        'invoice_no': sale.invoice_no,  # ✅ Use the auto-generated one
                        'customer_id': customer.id if customer else None,
                        'customer_name': customer_name,
                        'customer_phone': customer_phone,
                        'branch_id': unit.branch_id if unit.branch else None,
                        'subtotal': str(sale.subtotal),
                        'total': str(sale.total),
                        'payment_method': payment_method,
                        'status': 'completed',
                        'source': 'agent',
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
                        'current_owner_id': None,  # ✅ Sync the cleared owner
                        'tenant_id': tenant.id,
                    },
                    priority=8
                )
                logger.debug(f"✅ Queued Sale sync: {sale.invoice_no}")
            except Exception as e:
                logger.error(f"Failed to queue Sale sync: {e}")

        messages.success(request, f'Sale completed successfully! {unit.product.name} sold for KES {selling_price:.2f}')
        
        # Redirect to receipt page
        return redirect('tronic_master:receipt', sale_id=sale.id)

    context = {
        'tenant': tenant,
        'unit': unit,
        'is_admin': is_admin,
        'active_tab': 'my_stock',
    }
    return render(request, 'tronic_master/my_stock_sell.html', context)


# ============================================
# SALES AGENT - LOAN CREATION
# ============================================

@login_required
def agent_sale(request):
    """Sales Agent - Create a new sale from assigned stock (Admin sees all stock)"""
    tenant = request.user.tenant
    user = request.user

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    # ✅ Check if user is admin or superadmin
    from apps.shared.portal.helpers import is_admin_user
    
    is_admin = is_admin_user(user)

    # ✅ Get available units based on user role
    if is_admin:
        # Admin/Superadmin - See ALL available units across all branches
        products = ProductUnit.objects.filter(
            tenant=tenant,
            status='available'
        ).select_related('product', 'branch', 'current_owner').order_by('product__name')
        
        # Get all available units for stats
        total_available = products.count()
    else:
        # Regular Sales Agent - See only their assigned stock
        products = ProductUnit.objects.filter(
            tenant=tenant,
            current_owner=user,
            status='available'
        ).select_related('product', 'branch').order_by('product__name')
        
        # Count statistics for sales agent
        total_available = products.count()

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
        payment_method = request.POST.get('payment_method', 'mpesa').strip()

        # Validate
        if not customer_name:
            messages.error(request, 'Customer name is required')
            return redirect('tronic_master:agent_sale')

        if not customer_phone:
            messages.error(request, 'Customer phone number is required')
            return redirect('tronic_master:agent_sale')

        if not imei:
            messages.error(request, 'Please select a product by IMEI/Serial number')
            return redirect('tronic_master:agent_sale')

        if not selling_price:
            messages.error(request, 'Selling price is required')
            return redirect('tronic_master:agent_sale')

        try:
            selling_price = Decimal(str(selling_price))
            if selling_price <= 0:
                messages.error(request, 'Selling price must be greater than 0')
                return redirect('tronic_master:agent_sale')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid selling price')
            return redirect('tronic_master:agent_sale')

        # ✅ Find the unit by IMEI or Serial with proper permissions
        if is_admin:
            # Admin can sell any available unit
            unit = ProductUnit.objects.filter(
                tenant=tenant,
                status='available'
            ).filter(
                Q(imei_number=imei) | Q(serial_number=imei)
            ).first()
        else:
            # Agent can only sell their assigned units
            unit = ProductUnit.objects.filter(
                tenant=tenant,
                current_owner=user,
                status='available'
            ).filter(
                Q(imei_number=imei) | Q(serial_number=imei)
            ).first()

        if not unit:
            messages.error(request, 'Product not found in available stock')
            return redirect('tronic_master:agent_sale')

        # ✅ Check if unit is still available (double-check)
        unit.refresh_from_db()
        if unit.status != 'available':
            messages.error(request, f'Unit {imei} is no longer available (Status: {unit.get_status_display()})')
            return redirect('tronic_master:agent_sale')

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

        # ✅ FIXED: Let the model generate the invoice number automatically
        # Do NOT manually generate invoice_no - Sale.save() handles it
        sale = Sale.objects.create(
            tenant=tenant,
            customer=customer,
            customer_name=customer_name,
            customer_phone=customer_phone,
            cashier=user,
            # invoice_no is AUTO-GENERATED by Sale.save()
            subtotal=selling_price,
            total=selling_price,
            payment_method=payment_method,
            status='completed',
            tax_inclusive=True,
            branch=unit.branch,
            source='agent'  # ✅ Mark as agent sale
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

        # ✅ Mark unit as sold and CLEAR the owner
        unit.status = 'sold'
        unit.sold_at_price = selling_price
        unit.sold_date = timezone.now()
        unit.sold_by = user
        unit.current_owner = None  # ✅ IMPORTANT: Clear the owner
        unit.save()

        # ✅ Update product quantities
        unit.product.update_quantities()

        # ✅ Update customer total spent
        customer.total_spent = (customer.total_spent or Decimal('0')) + selling_price
        customer.save()

        # ✅ Queue sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                from apps.shared.tenants.models import SyncQueue
                
                SyncQueue.objects.create(
                    tenant_id=tenant.id,
                    model_name='Sale',
                    object_id=str(sale.id),
                    operation='CREATE',
                    data={
                        'id': sale.id,
                        'invoice_no': sale.invoice_no,  # ✅ Use the auto-generated one
                        'customer_id': customer.id if customer else None,
                        'customer_name': customer_name,
                        'customer_phone': customer_phone,
                        'branch_id': unit.branch_id if unit.branch else None,
                        'subtotal': str(sale.subtotal),
                        'total': str(sale.total),
                        'payment_method': payment_method,
                        'status': 'completed',
                        'source': 'agent',
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
                        'current_owner_id': None,  # ✅ Sync the cleared owner
                        'tenant_id': tenant.id,
                    },
                    priority=8
                )
                logger.debug(f"✅ Queued Sale sync: {sale.invoice_no}")
            except Exception as e:
                logger.error(f"Failed to queue Sale sync: {e}")

        messages.success(request, f'Sale completed successfully! {unit.product.name} sold for KES {selling_price:.2f}')

        # ✅ REDIRECT TO RECEIPT PAGE
        return redirect('tronic_master:receipt', sale_id=sale.id)

    # ✅ GET request - show the form
    product_list = []
    for unit in products:
        product_list.append({
            'id': unit.id,
            'name': unit.product.name,
            'brand': unit.product.brand,
            'model': unit.product.model,
            'sku': unit.product.sku_code,
            'imei': unit.imei_number or '',
            'serial': unit.serial_number or '',
            'selling_price': float(unit.unit_selling_price or unit.product.default_selling_price),
            'buying_price': float(unit.unit_buying_price or unit.product.default_buying_price),
            'branch': unit.branch.name if unit.branch else 'Main Shop',
            'owner': unit.current_owner.get_full_name() or unit.current_owner.username if unit.current_owner else 'Unassigned' if is_admin else None,
            'condition': unit.get_condition_display() if hasattr(unit, 'get_condition_display') else 'New',
        })

    context = {
        'tenant': tenant,
        'products': product_list,
        'total_available': total_available,
        'is_admin': is_admin,
        'active_tab': 'sales',
    }
    return render(request, 'tronic_master/agent_sale.html', context)


# ============================================
# MY STOCK - RESERVE VIEW
# ============================================

@login_required
def my_stock_reserve(request, unit_id):
    """
    Sales Agent - Reserve a unit from their stock
    """
    tenant = request.user.tenant
    user = request.user

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    # Check if user is admin
    is_admin = is_admin_user(user)

    # Get the unit
    if is_admin:
        unit = get_object_or_404(
            ProductUnit,
            id=unit_id,
            tenant=tenant,
            status='available'
        )
    else:
        unit = get_object_or_404(
            ProductUnit,
            id=unit_id,
            tenant=tenant,
            current_owner=user,
            status='available'
        )

    # Reserve the unit
    unit.status = 'reserved'
    unit.save()

    messages.success(request, f'Unit {unit.imei_number or unit.serial_number or unit.id} reserved successfully!')
    return redirect('tronic_master:my_stock')


# ============================================
# MY STOCK - UNRESERVE VIEW
# ============================================

@login_required
def my_stock_unreserve(request, unit_id):
    """
    Sales Agent - Unreserve a unit (Reserved -> Available)
    """
    tenant = request.user.tenant
    user = request.user

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    # Check if user is admin
    is_admin = is_admin_user(user)

    # Get the unit
    if is_admin:
        unit = get_object_or_404(
            ProductUnit,
            id=unit_id,
            tenant=tenant,
            status='reserved'
        )
    else:
        unit = get_object_or_404(
            ProductUnit,
            id=unit_id,
            tenant=tenant,
            current_owner=user,
            status='reserved'
        )

    # Unreserve the unit
    unit.status = 'available'
    unit.save()

    messages.success(request, f'Unit {unit.imei_number or unit.serial_number or unit.id} is now available again.')
    return redirect('tronic_master:my_stock')


# ============================================
# MY STOCK - TRANSFER VIEW (Admin only)
# ============================================

@login_required
def my_stock_transfer(request, unit_id):
    """
    Admin - Transfer a unit to another agent
    """
    tenant = request.user.tenant
    user = request.user

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    # Check if user is admin
    is_admin = is_admin_user(user)
    
    if not is_admin:
        messages.error(request, 'You do not have permission to transfer units.')
        return redirect('tronic_master:my_stock')

    # Get the unit
    unit = get_object_or_404(
        ProductUnit,
        id=unit_id,
        tenant=tenant,
        status__in=['available', 'reserved']
    )

    if request.method == 'POST':
        agent_id = request.POST.get('agent_id')
        
        if not agent_id:
            messages.error(request, 'Please select an agent to transfer to.')
            return redirect('tronic_master:my_stock_transfer', unit_id=unit.id)
        
        try:
            agent = User.objects.get(id=agent_id, tenant=tenant, is_active=True)
        except User.DoesNotExist:
            messages.error(request, 'Agent not found.')
            return redirect('tronic_master:my_stock_transfer', unit_id=unit.id)
        
        # Transfer the unit
        old_owner = unit.current_owner
        unit.current_owner = agent
        unit.assigned_date = timezone.now()
        unit.assigned_by = user
        unit.save()
        
        messages.success(
            request, 
            f'Unit {unit.imei_number or unit.serial_number or unit.id} transferred to {agent.get_full_name() or agent.username} successfully!'
        )
        return redirect('tronic_master:my_stock')

    # Get all active agents for the dropdown
    agents = User.objects.filter(
        tenant=tenant,
        is_active=True
    ).exclude(
        id=user.id
    ).exclude(
        role='super_admin'
    ).order_by('first_name', 'last_name')

    context = {
        'tenant': tenant,
        'unit': unit,
        'agents': agents,
        'active_tab': 'my_stock',
    }
    return render(request, 'tronic_master/my_stock_transfer.html', context)

@login_required
def stock_take(request):
    """Stock take - count physical inventory"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    branch_id = request.GET.get('branch_id')
    category_id = request.GET.get('category_id')

    products = Product.objects.filter(tenant=tenant, is_active=True)

    if branch_id:
        products = products.filter(branch_id=branch_id)
    if category_id:
        products = products.filter(category_id=category_id)

    if request.method == 'POST':
        # Process stock take
        updated_count = 0
        for key, value in request.POST.items():
            if key.startswith('count_'):
                product_id = key.replace('count_', '')
                try:
                    product = Product.objects.get(id=product_id, tenant=tenant)
                    new_count = int(value)

                    # Create stock adjustment entry
                    difference = new_count - product.available_quantity

                    if difference != 0:
                        StockEntry.objects.create(
                            tenant=tenant,
                            product_sku=product,
                            quantity=difference,
                            entry_type='adjustment',
                            unit_price=product.default_buying_price,
                            total_amount=difference * product.default_buying_price,
                            notes=f"Stock take adjustment - physical count: {new_count}, system: {product.available_quantity}",
                            created_by=request.user
                        )

                        product.available_quantity = new_count
                        product.total_quantity = new_count
                        product.save()
                        updated_count += 1

                except (Product.DoesNotExist, ValueError):
                    continue

        messages.success(request, f'Stock take completed! {updated_count} products updated.')
        return redirect('tronic_master:stock_take')

    branches = Branch.objects.filter(tenant=tenant, is_active=True)
    categories = Category.objects.filter(tenant=tenant, is_active=True)

    context = {
        'tenant': tenant,
        'products': products,
        'branches': branches,
        'categories': categories,
        'selected_branch': branch_id,
        'selected_category': category_id,
        'active_tab': 'inventory',
    }
    return render(request, 'tronic_master/stock_take.html', context)

@login_required
def manage_stock(request):
    """Manage stock for all products - view, adjust, transfer"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    # Base queryset
    products = Product.objects.filter(tenant=tenant, is_active=True).select_related('category', 'branch')

    # Filters
    search_query = request.GET.get('q', '').strip()
    stock_filter = request.GET.get('stock', '')
    category_id = request.GET.get('category', '')
    branch_id = request.GET.get('branch', '')

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(sku_code__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(model__icontains=search_query)
        )

    if stock_filter == 'low':
        products = products.filter(
            available_quantity__lte=F('reorder_level'),
            available_quantity__gt=0
        )
    elif stock_filter == 'out':
        products = products.filter(available_quantity=0)
    elif stock_filter == 'in':
        products = products.filter(available_quantity__gt=0)

    if category_id:
        products = products.filter(category_id=category_id)

    if branch_id:
        products = products.filter(branch_id=branch_id)

    # Get categories and branches for filters
    categories = Category.objects.filter(tenant=tenant, is_active=True)
    branches = Branch.objects.filter(tenant=tenant, is_active=True)

    # Statistics
    total_products = products.count()
    total_stock_value = products.aggregate(
        total=Sum(F('available_quantity') * F('default_buying_price'))
    )['total'] or Decimal('0.00')

    total_quantity = products.aggregate(
        total=Sum('available_quantity')
    )['total'] or 0

    low_stock_count = products.filter(
        available_quantity__lte=F('reorder_level'),
        available_quantity__gt=0
    ).count()

    out_of_stock_count = products.filter(available_quantity=0).count()
    in_stock_count = products.filter(available_quantity__gt=0).count()

    # Pagination
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'tenant': tenant,
        'products': page_obj,
        'categories': categories,
        'branches': branches,
        'search_query': search_query,
        'stock_filter': stock_filter,
        'selected_category': category_id,
        'selected_branch': branch_id,
        'total_products': total_products,
        'total_stock_value': total_stock_value,
        'total_quantity': total_quantity,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'in_stock_count': in_stock_count,
        'active_tab': 'inventory',
    }
    return render(request, 'tronic_master/manage_stock.html', context)

@login_required
def stock_management(request):
    """Stock management dashboard for admin/superadmin"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    # Check if user is admin
    from apps.shared.portal.helpers import is_admin_user
    if not is_admin_user(request.user):
        messages.error(request, 'You do not have permission to access stock management')
        return redirect('tronic_master:dashboard')
    
    context = {
        'tenant': tenant,
        'active_tab': 'stock_management',
    }
    return render(request, 'tronic_master/stock_management.html', context)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def transfer_unit(request):
    """
    Transfer a unit to a different agent (Admin only)
    """
    try:
        data = json.loads(request.body)
        unit_id = data.get('unit_id')
        agent_id = data.get('agent_id')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    # Check if user is admin
    if not is_admin_user(request.user):
        return JsonResponse({'error': 'Permission denied. Admin access required.'}, status=403)
    
    # Get the unit
    try:
        unit = ProductUnit.objects.get(id=unit_id, tenant=tenant)
    except ProductUnit.DoesNotExist:
        return JsonResponse({'error': 'Unit not found'}, status=404)
    
    # Check if unit is available for transfer
    if unit.status not in ['available', 'reserved']:
        return JsonResponse({
            'error': f'Cannot transfer unit with status "{unit.status}". Only available or reserved units can be transferred.'
        }, status=400)
    
    # Get the agent
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        agent = User.objects.get(id=agent_id, tenant=tenant, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Agent not found'}, status=404)
    
    # Transfer the unit
    old_owner = unit.current_owner
    unit.current_owner = agent
    unit.assigned_date = timezone.now()
    unit.assigned_by = request.user
    unit.save()
    
    # Log the transfer
    logger.info(
        f"Unit {unit.id} ({unit.imei_number or unit.serial_number}) transferred "
        f"from {old_owner.username if old_owner else 'Unassigned'} "
        f"to {agent.username} by {request.user.username}"
    )
    
    return JsonResponse({
        'success': True,
        'message': f'Unit transferred successfully to {agent.get_full_name() or agent.username}',
        'unit': {
            'id': unit.id,
            'identifier': unit.imei_number or unit.serial_number,
            'product_name': unit.product.name,
            'new_owner': agent.get_full_name() or agent.username,
            'new_owner_id': agent.id,
            'status': unit.status,
        }
    })

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def reserve_unit(request, unit_id):
    """
    Reserve a unit (Available -> Reserved)
    """
    tenant = request.user.tenant
    
    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)
    
    try:
        unit = ProductUnit.objects.get(id=unit_id, tenant=tenant)
    except ProductUnit.DoesNotExist:
        return JsonResponse({'error': 'Unit not found'}, status=404)
    
    # Check if user owns this unit (or is admin)
    if not is_admin_user(request.user) and unit.current_owner != request.user:
        return JsonResponse({
            'error': 'You do not have permission to reserve this unit'
        }, status=403)
    
    # Check if unit is available
    if unit.status != 'available':
        return JsonResponse({
            'error': f'Cannot reserve unit with status "{unit.status}". Only available units can be reserved.'
        }, status=400)
    
    # Reserve the unit
    unit.status = 'reserved'
    unit.save()
    
    # Log the reservation
    logger.info(
        f"Unit {unit.id} ({unit.imei_number or unit.serial_number}) "
        f"reserved by {request.user.username}"
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Unit reserved successfully',
        'unit': {
            'id': unit.id,
            'identifier': unit.imei_number or unit.serial_number,
            'product_name': unit.product.name,
            'status': unit.status,
        }
    })



# ============================================
# SALES AGENT - MY SALES
# ============================================

@login_required
def my_sales(request):
    """View sales - Regular users see only their sales, Admins see all sales"""
    tenant = request.user.tenant
    user = request.user

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    from apps.shared.portal.helpers import is_admin_user
    is_admin = is_admin_user(user)

    # ✅ Base query - exclude POS sales
    if is_admin:
        # ✅ Admin/Superadmin sees ALL sales (except POS) across all users
        sales = Sale.objects.filter(
            tenant=tenant,
            status='completed'
        ).exclude(
            source='pos'  # Exclude POS sales
        ).select_related(
            'customer', 'cashier', 'branch'
        ).prefetch_related('items').order_by('-created_at')
    else:
        # ✅ Regular user sees ONLY their own sales (except POS)
        sales = Sale.objects.filter(
            tenant=tenant,
            cashier=user,  # Only this user's sales
            status='completed'
        ).exclude(
            source='pos'  # Exclude POS sales
        ).select_related(
            'customer', 'branch'
        ).prefetch_related('items').order_by('-created_at')

    # ✅ Apply search and filters
    search_query = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if search_query:
        sales = sales.filter(
            Q(invoice_no__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(customer_phone__icontains=search_query) |
            Q(items__product__name__icontains=search_query)
        ).distinct()

    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)

    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)

    # ✅ Calculate stats
    total_count = sales.count()
    total_value = sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    today_count = sales.filter(created_at__date=timezone.now().date()).count()
    
    # ✅ For admin, count unique agents
    if is_admin:
        agent_count = sales.values('cashier').distinct().count()
    else:
        agent_count = 0

    # ✅ Pagination
    paginator = Paginator(sales, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'tenant': tenant,
        'user': user,
        'sales': page_obj,
        'is_admin': is_admin,
        'total_count': total_count,
        'total_value': total_value,
        'today_count': today_count,
        'agent_count': agent_count,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'active_tab': 'my_sales',
    }
    return render(request, 'tronic_master/my_sales.html', context)


@login_required
def refund_sale(request, sale_id):
    """Admin/Superadmin - Refund a completed sale"""
    tenant = request.user.tenant
    user = request.user

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    # ✅ Check if user is admin
    from apps.shared.portal.helpers import is_admin_user
    if not is_admin_user(user):
        messages.error(request, 'You do not have permission to refund sales')
        return redirect('tronic_master:my_sales')

    # Get the sale
    sale = get_object_or_404(
        Sale,
        id=sale_id,
        tenant=tenant,
        status='completed'
    )

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        
        if not reason:
            messages.error(request, 'Please provide a reason for the refund')
            return redirect('tronic_master:refund_sale', sale_id=sale.id)

        # ✅ Process the refund
        try:
            # Mark sale as refunded
            sale.status = 'refunded'
            sale.save()

            # Restore stock for each item
            for item in sale.items.all():
                if item.product_unit:
                    unit = item.product_unit
                    unit.status = 'available'
                    unit.sold_at_price = None
                    unit.sold_date = None
                    unit.sold_by = None
                    unit.save()
                    unit.product.update_quantities()

            # Create refund record (optional)
            # You might want to create a Refund model here

            messages.success(
                request, 
                f'Sale {sale.invoice_no} has been refunded successfully. '
                f'Stock has been restored.'
            )
            return redirect('tronic_master:my_sales')

        except Exception as e:
            logger.error(f"Error processing refund for sale {sale.id}: {str(e)}")
            messages.error(request, f'Error processing refund: {str(e)}')
            return redirect('tronic_master:my_sales')

    context = {
        'tenant': tenant,
        'sale': sale,
        'active_tab': 'my_sales',
    }
    return render(request, 'tronic_master/refund_sale.html', context)

    
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
                    return redirect('tronic_master:sale_detail', sale_id=sale_result.id)

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
                        return redirect('tronic_master:sale_detail', sale_id=sale_result.id)
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
    return render(request, 'tronic_master/sales_search.html', context)

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
    source = request.GET.get('source', '')  
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if search:
        sales = sales.filter(
            Q(invoice_no__icontains=search) |
            Q(customer_name__icontains=search)
        )
    if status:
        sales = sales.filter(status=status)
    if source:  # ✅ Apply source filter
        sales = sales.filter(source=source)
    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)

    # Statistics
    total_sales = sales.aggregate(total=Sum('total'))['total'] or Decimal('0')
    total_count = sales.count()
    today = timezone.now().date()
    today_count = sales.filter(created_at__date=today).count()
    today_revenue = sales.filter(created_at__date=today).aggregate(total=Sum('total'))['total'] or Decimal('0')

    # Pagination
    paginator = Paginator(sales, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'tenant': tenant,
        'sales': page_obj,
        'total_sales': total_sales,
        'total_count': total_count,
        'today_count': today_count,
        'today_revenue': today_revenue,
        'today': today,
        'search': search,
        'status_filter': status,
        'source_filter': source, 
        'date_from': date_from,
        'date_to': date_to,
        'active_tab': 'sales',
    }
    return render(request, 'tronic_master/sales_history.html', context)


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
    return render(request, 'tronic_master/sale_detail.html', context)


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
    sale_items = SaleItem.objects.filter(sale=sale).select_related('product', 'product_unit')

    # Calculate subtotal (sum of all items before tax)
    subtotal = sum(item.subtotal for item in sale_items)

    context = {
        'sale': sale,
        'sale_items': sale_items,
        'subtotal': subtotal,
        'tenant': tenant,
        'receipt_settings': tenant.receipt_settings if hasattr(tenant, 'receipt_settings') else None,
        'company_settings': tenant.company_settings if hasattr(tenant, 'company_settings') else None,
    }
    return render(request, 'tronic_master/receipt.html', context)

# ============================================
# RECEIPT SEARCH VIEW
# ============================================

@login_required
def receipt_search(request):
    """Search and view receipts by invoice number or customer"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    search_query = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    # ✅ Use select_related and prefetch_related for better performance
    sales = Sale.objects.filter(tenant=tenant).select_related('customer').prefetch_related('items').order_by('-created_at')

    if search_query:
        sales = sales.filter(
            Q(invoice_no__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(customer_phone__icontains=search_query)
        )

    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)

    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)

    # ✅ Calculate totals using the items_count property
    from django.db.models import Sum
    
    total_sales = sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    # ✅ Calculate total items by iterating through sales
    # This avoids the N+1 query problem by using prefetched items
    total_items = 0
    for sale in sales:
        total_items += sale.items.count()  # This uses the prefetched items
    
    unique_customers = sales.values('customer_id').distinct().count()

    # Pagination
    paginator = Paginator(sales, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'tenant': tenant,
        'sales': page_obj,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'total_sales': total_sales,
        'total_items': total_items,
        'unique_customers': unique_customers,
        'active_tab': 'sales',
    }
    return render(request, 'tronic_master/receipt_search.html', context)

# ============================================
#  PRICE LOOKUP
# ============================================

@login_required
def price_check(request):
    """
    Price check view - Search product by identifier (IMEI, Serial, SKU, Barcode)
    Displays selling price and best price only
    """
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    context = {
        'tenant': tenant,
        'active_tab': 'price_check',
    }
    return render(request, 'tronic_master/price_check.html', context)


@login_required
def price_check_ajax(request):
    """
    AJAX endpoint for price check - Search product by identifier
    Returns: product details with selling_price, best_price, status, and quantity
    """
    tenant = request.user.tenant

    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)

    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse({'error': 'Please enter a search term'}, status=400)

    try:
        # Search by IMEI (ProductUnit)
        product_unit = ProductUnit.objects.filter(
            tenant=tenant,
            imei_number=query,
            status='available'
        ).select_related('product', 'branch').first()

        if product_unit:
            product = product_unit.product
            return JsonResponse({
                'success': True,
                'found': True,
                'type': 'unit',
                'data': {
                    'id': product.id,
                    'sku_code': product.sku_code,
                    'name': product.name,
                    'brand': product.brand,
                    'model': product.model,
                    'imei': product_unit.imei_number,
                    'serial': product_unit.serial_number,
                    'selling_price': float(product_unit.effective_selling_price or product.default_selling_price),
                    'best_price': float(product_unit.best_price or product.default_best_price or product.default_selling_price),
                    'buying_price': float(product_unit.effective_buying_price or product.default_buying_price),
                    'condition': product_unit.get_condition_display(),
                    'status': product_unit.get_status_display(),
                    'status_code': product_unit.status,
                    'unit_id': product_unit.id,
                    'branch': product_unit.branch.name if product_unit.branch else 'Main Shop',
                    'quantity': 1,  # Unit always 1
                    'total_quantity': ProductUnit.objects.filter(
                        tenant=tenant,
                        product=product,
                        status='available'
                    ).count(),  # Total available units
                }
            })

        # Search by Serial Number (ProductUnit)
        product_unit = ProductUnit.objects.filter(
            tenant=tenant,
            serial_number=query,
            status='available'
        ).select_related('product', 'branch').first()

        if product_unit:
            product = product_unit.product
            return JsonResponse({
                'success': True,
                'found': True,
                'type': 'unit',
                'data': {
                    'id': product.id,
                    'sku_code': product.sku_code,
                    'name': product.name,
                    'brand': product.brand,
                    'model': product.model,
                    'imei': product_unit.imei_number,
                    'serial': product_unit.serial_number,
                    'selling_price': float(product_unit.effective_selling_price or product.default_selling_price),
                    'best_price': float(product_unit.best_price or product.default_best_price or product.default_selling_price),
                    'buying_price': float(product_unit.effective_buying_price or product.default_buying_price),
                    'condition': product_unit.get_condition_display(),
                    'status': product_unit.get_status_display(),
                    'status_code': product_unit.status,
                    'unit_id': product_unit.id,
                    'branch': product_unit.branch.name if product_unit.branch else 'Main Shop',
                    'quantity': 1,
                    'total_quantity': ProductUnit.objects.filter(
                        tenant=tenant,
                        product=product,
                        status='available'
                    ).count(),
                }
            })

        # Search by SKU Code (Product)
        product = Product.objects.filter(
            tenant=tenant,
            sku_code=query,
            is_active=True
        ).first()

        if product:
            return JsonResponse({
                'success': True,
                'found': True,
                'type': 'product',
                'data': {
                    'id': product.id,
                    'sku_code': product.sku_code,
                    'name': product.name,
                    'brand': product.brand,
                    'model': product.model,
                    'barcode': product.sku_code,
                    'selling_price': float(product.default_selling_price),
                    'best_price': float(product.default_best_price or product.default_selling_price),
                    'buying_price': float(product.default_buying_price),
                    'available_quantity': product.available_quantity,
                    'total_quantity': product.total_quantity,
                    'reserved_quantity': product.reserved_quantity,
                    'damaged_quantity': product.damaged_quantity,
                    'category': product.category.name if product.category else None,
                    'condition': 'N/A',  # Bulk product doesn't have condition
                    'status': 'In Stock' if product.available_quantity > 0 else 'Out of Stock',
                    'status_code': 'in_stock' if product.available_quantity > 0 else 'out_of_stock',
                    'branch': product.branch.name if product.branch else 'Main Shop',
                    'is_low_stock': product.is_low_stock,
                    'is_out_of_stock': product.is_out_of_stock,
                    'reorder_level': product.reorder_level,
                }
            })

        # Search by Barcode (Product)
        product = Product.objects.filter(
            tenant=tenant,
            is_active=True
        ).first()

        if product:
            return JsonResponse({
                'success': True,
                'found': True,
                'type': 'product',
                'data': {
                    'id': product.id,
                    'sku_code': product.sku_code,
                    'name': product.name,
                    'brand': product.brand,
                    'model': product.model,
                    'barcode': product.sku_code,
                    'selling_price': float(product.default_selling_price),
                    'best_price': float(product.default_best_price or product.default_selling_price),
                    'buying_price': float(product.default_buying_price),
                    'available_quantity': product.available_quantity,
                    'total_quantity': product.total_quantity,
                    'reserved_quantity': product.reserved_quantity,
                    'damaged_quantity': product.damaged_quantity,
                    'category': product.category.name if product.category else None,
                    'condition': 'N/A',
                    'status': 'In Stock' if product.available_quantity > 0 else 'Out of Stock',
                    'status_code': 'in_stock' if product.available_quantity > 0 else 'out_of_stock',
                    'branch': product.branch.name if product.branch else 'Main Shop',
                    'is_low_stock': product.is_low_stock,
                    'is_out_of_stock': product.is_out_of_stock,
                    'reorder_level': product.reorder_level,
                }
            })

        # Search by Product Name (partial match)
        products = Product.objects.filter(
            tenant=tenant,
            name__icontains=query,
            is_active=True
        )[:5]

        if products.exists():
            results = []
            for product in products:
                results.append({
                    'id': product.id,
                    'sku_code': product.sku_code,
                    'name': product.name,
                    'brand': product.brand,
                    'model': product.model,
                    'selling_price': float(product.default_selling_price),
                    'best_price': float(product.default_best_price or product.default_selling_price),
                    'buying_price': float(product.default_buying_price),
                    'available_quantity': product.available_quantity,
                    'status': 'In Stock' if product.available_quantity > 0 else 'Out of Stock',
                    'status_code': 'in_stock' if product.available_quantity > 0 else 'out_of_stock',
                    'is_low_stock': product.is_low_stock,
                })

            return JsonResponse({
                'success': True,
                'found': True,
                'type': 'list',
                'data': results,
                'count': len(results),
                'message': f'Found {len(results)} products matching "{query}"'
            })

        # No results found
        return JsonResponse({
            'success': True,
            'found': False,
            'message': f'No product found for "{query}"'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



# ============================================
# REVERSE SALE (REFUND/REVERSE)
# ============================================

@login_required
def reverse_sale(request, sale_id):
    """Reverse a sale (refund/return)"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    sale = get_object_or_404(Sale, id=sale_id, tenant=tenant)

    # ✅ Check if sale can be reversed (only completed sales)
    if sale.status != 'completed':
        messages.warning(request, 'Only completed sales can be reversed.')
        return redirect('tronic_master:sale_detail', sale_id=sale.id)

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        confirm = request.POST.get('confirm', '')

        if not reason:
            messages.error(request, 'Please provide a reason for reversing this sale.')
            # ✅ FIX: Use the correct URL name
            return redirect('tronic_master:sale_reverse', sale_id=sale.id)

        if confirm != 'YES':
            messages.error(request, 'Please type "YES" to confirm reversal.')
            # ✅ FIX: Use the correct URL name
            return redirect('tronic_master:sale_reverse', sale_id=sale.id)

        try:
            from django.db import transaction

            with transaction.atomic():
                # Reverse sale items and restore stock
                for item in sale.items.all():
                    product_unit = item.product_unit

                    if product_unit:
                        # Restore unit to available
                        product_unit.status = 'available'
                        product_unit.sold_at_price = None
                        product_unit.sold_date = None
                        product_unit.sold_by = None
                        product_unit.save()

                        # Update product quantities
                        product_unit.product.update_quantities()

                    # Create return record
                    Return.objects.create(
                        tenant=tenant,
                        sale=sale,
                        product=item.product,
                        quantity=item.quantity,
                        amount=item.subtotal,
                        reason=f"Sale reversed: {reason}",
                        status='completed',
                        created_by=request.user,
                        approved_by=request.user,
                        approved_at=timezone.now()
                    )

                # Mark sale as reversed
                sale.status = 'reversed'
                sale.save()

                # Queue sync if offline
                if getattr(settings, 'OFFLINE_MODE', False):
                    try:
                        SyncQueue.objects.create(
                            tenant_id=tenant.id,
                            model_name='Sale',
                            object_id=str(sale.id),
                            operation='UPDATE',
                            data={
                                'id': sale.id,
                                'status': 'reversed',
                                'tenant_id': tenant.id,
                            },
                            priority=7
                        )
                    except Exception as e:
                        logger.error(f"Failed to queue Sale reverse sync: {e}")

                messages.success(request, f'Sale {sale.invoice_no} has been reversed successfully!')
                return redirect('tronic_master:sale_detail', sale_id=sale.id)

        except Exception as e:
            logger.error(f"Error reversing sale: {e}")
            messages.error(request, f'Error reversing sale: {str(e)}')
            # ✅ FIX: Use the correct URL name
            return redirect('tronic_master:sale_reverse', sale_id=sale.id)

    # GET request - show confirmation form
    context = {
        'tenant': tenant,
        'sale': sale,
        'items': sale.items.all().select_related('product', 'product_unit'),
        'active_tab': 'sales',
    }
    return render(request, 'tronic_master/reverse_sale.html', context)


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
            return redirect('tronic_master:create_return', sale_id=sale.id)

        product = get_object_or_404(Product, id=product_id, tenant=tenant)

        # Check if return already exists for this product
        existing_return = Return.objects.filter(
            sale=sale,
            product=product,
            status__in=['pending', 'approved']
        ).first()

        if existing_return:
            messages.error(request, f'Return already exists for {product.name}')
            return redirect('tronic_master:create_return', sale_id=sale.id)

        # Calculate return amount
        sale_item = sale.items.filter(product=product).first()
        if sale_item:
            amount = sale_item.price * quantity
        else:
            amount = product.default_selling_price * quantity

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
        return redirect('tronic_master:return_detail', return_id=return_obj.id)

    # Get sale items for selection
    items = sale.items.all().select_related('product')

    context = {
        'tenant': tenant,
        'sale': sale,
        'items': items,
        'active_tab': 'sales',
    }
    return render(request, 'tronic_master/create_return.html', context)


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
    return render(request, 'tronic_master/return_list.html', context)


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
    return render(request, 'tronic_master/return_detail.html', context)


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
        return redirect('tronic_master:return_detail', return_id=return_obj.id)

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
    return redirect('tronic_master:return_detail', return_id=return_obj.id)


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
        return redirect('tronic_master:return_detail', return_id=return_obj.id)

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
    return redirect('tronic_master:return_detail', return_id=return_obj.id)






# ============================================
# CASHIER DRAWER VIEW
# ============================================

@login_required
def open_drawer(request):
    """Open cash drawer for cashier"""
    # Get tenant from session or user profile
    tenant_id = request.session.get('tenant_id')

    if not tenant_id and hasattr(request.user, 'tenant'):
        tenant_id = request.user.tenant.id
    elif not tenant_id and hasattr(request.user, 'client_profile') and request.user.client_profile:
        tenant_id = request.user.client_profile.tenant.id

    # If still no tenant, get the first one
    if not tenant_id:
        tenant = Tenant.objects.first()
        if tenant:
            tenant_id = tenant.id
            request.session['tenant_id'] = tenant_id

    tenant = Tenant.objects.get(id=tenant_id) if tenant_id else None

    if not tenant:
        messages.error(request, 'No tenant found. Please contact administrator.')
        return redirect('portal_dashboard')

    # Check if cashier already has an open drawer
    active_drawer = CashDrawer.objects.filter(cashier=request.user, is_open=True).first()
    if active_drawer:
        messages.warning(request, 'You already have an open cash drawer')
        return redirect('drawer_detail', drawer_id=active_drawer.id)

    if request.method == 'POST':
        opening_amount = request.POST.get('opening_amount', 0)

        drawer = CashDrawer.objects.create(
            tenant=tenant,
            cashier=request.user,
            opening_amount=opening_amount,
            notes=request.POST.get('notes', '')
        )

        messages.success(request, f'Cash drawer opened with KES {opening_amount}')
        return redirect('drawer_detail', drawer_id=drawer.id)

    return render(request, 'cashier/open_drawer.html', {'tenant': tenant})

@login_required
def close_drawer(request, drawer_id):
    """Close cash drawer"""
    drawer = get_object_or_404(CashDrawer, id=drawer_id, cashier=request.user, is_open=True)

    if request.method == 'POST':
        drawer.closing_amount = request.POST.get('closing_amount')
        drawer.closed_at = timezone.now()
        drawer.is_open = False
        drawer.save()

        expected = drawer.expected_amount()
        closing_amount = float(drawer.closing_amount or 0)
        expected_amount = float(expected or 0)
        difference = closing_amount - expected_amount

        messages.success(
            request,
            f'Drawer closed! Expected: KES {expected:.2f}, Actual: KES {drawer.closing_amount}, Difference: KES {difference:.2f}'
        )
        return redirect('drawer_history')

    context = {
        'drawer': drawer,
        'expected_amount': drawer.expected_amount(),
        'total_sales': drawer.total_sales(),
    }
    return render(request, 'cashier/close_drawer.html', context)

@login_required
def drawer_detail(request, drawer_id):
    """View drawer details"""
    drawer = get_object_or_404(CashDrawer, id=drawer_id, cashier=request.user)
    transactions = drawer.transactions.all()

    context = {
        'drawer': drawer,
        'transactions': transactions,
        'total_sales': drawer.total_sales(),
        'expected_amount': drawer.expected_amount(),
    }
    return render(request, 'cashier/drawer_detail.html', context)

@login_required
def drawer_history(request):
    """View cash drawer history"""
    # Get tenant from session
    tenant_id = request.session.get('tenant_id')
    if not tenant_id and hasattr(request.user, 'tenant'):
        tenant_id = request.user.tenant.id

    tenant = Tenant.objects.get(id=tenant_id) if tenant_id else None

    drawers = CashDrawer.objects.filter(
        cashier=request.user
    ).order_by('-opened_at')

    if tenant:
        drawers = drawers.filter(tenant=tenant)

    context = {
        'drawers': drawers,
        'tenant': tenant,
    }
    return render(request, 'cashier/drawer_history.html', context)

@login_required
def add_transaction(request, drawer_id):
    """Add cash transaction (deposit/withdrawal)"""
    drawer = get_object_or_404(CashDrawer, id=drawer_id, cashier=request.user, is_open=True)

    if request.method == 'POST':
        amount = request.POST.get('amount')
        transaction_type = request.POST.get('transaction_type')
        reason = request.POST.get('reason')

        CashTransaction.objects.create(
            drawer=drawer,
            amount=amount,
            transaction_type=transaction_type,
            reason=reason,
            created_by=request.user
        )

        messages.success(request, f'{transaction_type.capitalize()} of KES {amount} recorded')
        return redirect('drawer_detail', drawer_id=drawer.id)

    context = {'drawer': drawer}
    return render(request, 'cashier/add_transaction.html', context)



# ============================================
# EXPENSE CATEGORY VIEWS (if missing)
# ============================================

@login_required
def expense_category_list(request):
    """List expense categories"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    categories = ExpenseCategory.objects.filter(tenant=tenant, is_active=True)

    context = {
        'tenant': tenant,
        'categories': categories,
        'active_tab': 'expenses',
    }
    return render(request, 'tronic_master/expense_category_list.html', context)


@login_required
def add_expense_category(request):
    """Add expense category"""
    tenant = request.user.tenant

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'

        if not name:
            messages.error(request, 'Category name is required')
            return redirect('tronic_master:add_expense_category')

        category, created = ExpenseCategory.objects.get_or_create(
            tenant=tenant,
            name=name,
            defaults={'description': description, 'is_active': is_active}
        )

        if created:
            messages.success(request, f'Category "{name}" created successfully!')
        else:
            messages.warning(request, f'Category "{name}" already exists.')

        return redirect('tronic_master:expense_category_list')

    context = {
        'tenant': tenant,
        'active_tab': 'expenses',
    }
    return render(request, 'tronic_master/add_expense_category.html', context)


@login_required
def edit_expense_category(request, category_id):
    """Edit expense category"""
    tenant = request.user.tenant
    category = get_object_or_404(ExpenseCategory, id=category_id, tenant=tenant)

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'

        if not name:
            messages.error(request, 'Category name is required')
            return redirect('tronic_master:edit_expense_category', category_id=category.id)

        category.name = name
        category.description = description
        category.is_active = is_active
        category.save()

        messages.success(request, f'Category "{name}" updated successfully!')
        return redirect('tronic_master:expense_category_list')

    context = {
        'tenant': tenant,
        'category': category,
        'active_tab': 'expenses',
    }
    return render(request, 'tronic_master/edit_expense_category.html', context)


@login_required
def delete_expense_category(request, category_id):
    """Delete expense category"""
    tenant = request.user.tenant
    category = get_object_or_404(ExpenseCategory, id=category_id, tenant=tenant)

    if request.method == 'POST':
        category_name = category.name
        category.delete()
        messages.success(request, f'Category "{category_name}" deleted successfully!')
        return redirect('tronic_master:expense_category_list')

    context = {
        'tenant': tenant,
        'category': category,
    }
    return render(request, 'tronic_master/delete_expense_category.html', context)


# ============================================
# EXPENSE LIST VIEW
# ============================================

@login_required
def expense_list(request):
    """Expense List for Tech Master"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    # Get date range
    today = timezone.now().date()
    start_date_str = request.GET.get('start_date', (today - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date_str = request.GET.get('end_date', today.strftime('%Y-%m-%d'))
    category_id = request.GET.get('category')
    status_filter = request.GET.get('status')

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except ValueError:
        start_date = today - timedelta(days=30)
        start_date_str = start_date.strftime('%Y-%m-%d')

    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        end_date = today
        end_date_str = end_date.strftime('%Y-%m-%d')

    # Query the shared Expense model
    from apps.shared.expenses.models import Expense, ExpenseCategory
    from django.db.models import Sum

    expenses_query = Expense.objects.filter(
        tenant=tenant,
        date__gte=start_date,
        date__lte=end_date
    ).select_related('category', 'created_by').order_by('-date')

    # Apply category filter
    if category_id:
        expenses_query = expenses_query.filter(category_id=category_id)

    # Apply status filter
    if status_filter:
        expenses_query = expenses_query.filter(status=status_filter)

    # Calculate totals
    total_expenses = expenses_query.aggregate(total=Sum('amount'))['total'] or 0
    pending_expenses = expenses_query.filter(status='pending').aggregate(total=Sum('amount'))['total'] or 0
    approved_expenses = expenses_query.filter(status__in=['approved', 'paid']).aggregate(total=Sum('amount'))['total'] or 0

    # Get categories for filter
    categories = ExpenseCategory.objects.filter(tenant=tenant, is_active=True)

    # Format expenses for display
    expenses = []
    for exp in expenses_query:
        expenses.append({
            'id': exp.id,
            'category': exp.category.name if exp.category else 'Uncategorized',
            'description': exp.description or exp.category.name if exp.category else 'Expense',
            'amount': float(exp.amount),
            'date': exp.date.strftime('%Y-%m-%d'),
            'status': exp.status or 'pending',
            'paid_by': exp.created_by.get_full_name() if exp.created_by else 'System',
        })

    # Expenses by category for chart
    expenses_by_category = []
    if expenses_query.exists():
        category_totals = expenses_query.values('category__name').annotate(
            total=Sum('amount')
        ).order_by('-total')

        for item in category_totals:
            expenses_by_category.append({
                'category_name': item['category__name'] or 'Uncategorized',
                'total': float(item['total']),
                'percentage': (float(item['total']) / float(total_expenses) * 100) if total_expenses > 0 else 0
            })

    context = {
        'tenant': tenant,
        'active_tab': 'reports',
        'start_date': start_date_str,
        'end_date': end_date_str,
        'expenses': expenses,
        'total_expenses': total_expenses,
        'pending_expenses': pending_expenses,
        'approved_expenses': approved_expenses,
        'categories': categories,
        'category_id': category_id,
        'status_filter': status_filter,
        'expenses_by_category': expenses_by_category,
    }

    return render(request, 'tronic_master/expense_list.html', context)


# ============================================
# ADD EXPENSE VIEW
# ============================================

@login_required
def add_expense(request):
    """Add new expense"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    if request.method == 'POST':
        title = request.POST.get('title')
        category_id = request.POST.get('category')
        amount = request.POST.get('amount')
        date = request.POST.get('date')
        description = request.POST.get('description', '')
        payment_method = request.POST.get('payment_method', 'cash')

        if not title or not amount or not date:
            messages.error(request, 'Please fill all required fields')
            return redirect('tronic_master:add_expense')

        category = None
        if category_id:
            category = get_object_or_404(ExpenseCategory, id=category_id, tenant=tenant)

        expense = Expense.objects.create(
            tenant=tenant,
            title=title,
            category=category,
            amount=Decimal(amount),
            date=date,
            description=description,
            payment_method=payment_method,
            created_by=request.user,
            status='pending'
        )

        messages.success(request, f'Expense "{title}" added successfully')
        return redirect('tronic_master:expense_detail', expense_id=expense.id)

    categories = ExpenseCategory.objects.filter(tenant=tenant, is_active=True)

    context = {
        'tenant': tenant,
        'categories': categories,
    }
    return render(request, 'tronic_master/expenses/add.html', context)


# ============================================
# EXPENSE DETAIL VIEW
# ============================================

@login_required
def expense_detail(request, expense_id):
    """View expense details"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    expense = get_object_or_404(Expense, id=expense_id, tenant=tenant)

    context = {
        'tenant': tenant,
        'expense': expense,
    }
    return render(request, 'tronic_master/expenses/detail.html', context)


# ============================================
# APPROVE EXPENSE VIEW
# ============================================

@login_required
def approve_expense(request, expense_id):
    """Approve an expense (admin/manager only)"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    expense = get_object_or_404(Expense, id=expense_id, tenant=tenant)

    # Check permission - only admin or manager can approve
    if request.user.role not in ['admin', 'manager', 'tenant_admin']:
        messages.error(request, 'You do not have permission to approve expenses')
        return redirect('tronic_master:expense_list')

    # Check if already approved
    if expense.status == 'approved':
        messages.warning(request, f'Expense "{expense.title}" is already approved')
        return redirect('tronic_master:expense_detail', expense_id=expense.id)

    expense.approve(request.user)
    messages.success(request, f'Expense "{expense.title}" approved successfully')
    return redirect('tronic_master:expense_detail', expense_id=expense.id)


# ============================================
# REJECT EXPENSE VIEW
# ============================================

@login_required
def reject_expense(request, expense_id):
    """Reject an expense (admin/manager only)"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    expense = get_object_or_404(Expense, id=expense_id, tenant=tenant)

    # Check permission
    if request.user.role not in ['admin', 'manager', 'tenant_admin']:
        messages.error(request, 'You do not have permission to reject expenses')
        return redirect('tronic_master:expense_list')

    # Check if already rejected
    if expense.status == 'rejected':
        messages.warning(request, f'Expense "{expense.title}" is already rejected')
        return redirect('tronic_master:expense_detail', expense_id=expense.id)

    expense.reject(request.user)
    messages.success(request, f'Expense "{expense.title}" rejected')
    return redirect('tronic_master:expense_detail', expense_id=expense.id)


# ============================================
# MARK EXPENSE AS PAID VIEW
# ============================================

@login_required
def mark_expense_paid(request, expense_id):
    """Mark expense as paid (admin/manager only)"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    expense = get_object_or_404(Expense, id=expense_id, tenant=tenant)

    # Check permission
    if request.user.role not in ['admin', 'manager', 'tenant_admin']:
        messages.error(request, 'You do not have permission to mark expenses as paid')
        return redirect('tronic_master:expense_list')

    # Check if already paid
    if expense.status == 'paid':
        messages.warning(request, f'Expense "{expense.title}" is already marked as paid')
        return redirect('tronic_master:expense_detail', expense_id=expense.id)

    expense.mark_paid()
    messages.success(request, f'Expense "{expense.title}" marked as paid')
    return redirect('tronic_master:expense_detail', expense_id=expense.id)


# ============================================
# EXPENSE REPORT VIEW
# ============================================

@login_required
def expense_report(request):
    """Expense report with charts and analytics"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    period = request.GET.get('period', 'month')
    today = timezone.now().date()

    # Date range based on period
    if period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        period_label = 'This Week'
    elif period == 'month':
        start_date = today.replace(day=1)
        end_date = today
        period_label = 'This Month'
    elif period == 'quarter':
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        start_date = today.replace(month=quarter_month, day=1)
        end_date = today
        period_label = 'This Quarter'
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today
        period_label = 'This Year'
    else:
        # Custom period - default to last 30 days
        start_date = today - timedelta(days=30)
        end_date = today
        period_label = 'Last 30 Days'

    # Get expenses for this period
    expenses = Expense.objects.filter(
        tenant=tenant,
        date__gte=start_date,
        date__lte=end_date
    )

    # Total expenses
    total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Expenses by category
    category_data = []
    categories = ExpenseCategory.objects.filter(tenant=tenant, is_active=True)
    for category in categories:
        cat_total = expenses.filter(category=category).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        if cat_total > 0:
            category_data.append({
                'name': category.name,
                'total': float(cat_total),
                'percentage': float((cat_total / total * 100) if total > 0 else 0)
            })

    # Sort by total descending
    category_data.sort(key=lambda x: x['total'], reverse=True)

    # Daily expenses for chart
    daily_expenses = []
    date_range = (end_date - start_date).days + 1
    for i in range(date_range):
        date = start_date + timedelta(days=i)
        day_total = Expense.objects.filter(
            tenant=tenant,
            date=date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        daily_expenses.append({
            'date': date.strftime('%b %d'),
            'total': float(day_total)
        })

    # Status breakdown
    status_counts = {
        'pending': expenses.filter(status='pending').count(),
        'approved': expenses.filter(status='approved').count(),
        'paid': expenses.filter(status='paid').count(),
        'rejected': expenses.filter(status='rejected').count(),
    }

    # Payment method breakdown
    payment_methods = {}
    for method in Expense.PAYMENT_METHODS:
        method_code = method[0]
        method_total = expenses.filter(payment_method=method_code).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        if method_total > 0:
            payment_methods[method[1]] = float(method_total)

    # Recent expenses (last 10)
    recent_expenses = expenses.order_by('-created_at')[:10]

    context = {
        'tenant': tenant,
        'total': total,
        'category_data': category_data,
        'daily_expenses': daily_expenses,
        'period': period,
        'period_label': period_label,
        'expense_count': expenses.count(),
        'status_counts': status_counts,
        'payment_methods': payment_methods,
        'recent_expenses': recent_expenses,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'tronic_master/expenses_report.html', context)



@login_required
def report_dashboard(request):
    """Reports dashboard with comprehensive analytics"""
    tenant = request.user.tenant

    if not tenant:
        return render(request, 'tronic_master/reports/dashboard.html', {
            'error': 'No tenant assigned to your account'
        })

    # ============================================
    # DATE RANGES
    # ============================================
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=7)
    last_month = today - timedelta(days=30)

    # ============================================
    # SALES REPORTS
    # ============================================
    # Total sales (all time)
    total_sales = Sale.objects.filter(
        tenant=tenant,
        status='completed'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    # Today's sales
    today_sales = Sale.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__date=today
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    # Yesterday's sales
    yesterday_sales = Sale.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__date=yesterday
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    # This week's sales
    week_sales = Sale.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__date__gte=week_start,
        created_at__date__lte=today
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    # This month's sales
    month_sales = Sale.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__date__gte=month_start,
        created_at__date__lte=today
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    # Last month's sales
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_month_end = today.replace(day=1) - timedelta(days=1)
    last_month_sales = Sale.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__date__gte=last_month_start,
        created_at__date__lte=last_month_end
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    # Sales count
    total_sales_count = Sale.objects.filter(
        tenant=tenant,
        status='completed'
    ).count()

    today_sales_count = Sale.objects.filter(
        tenant=tenant,
        status='completed',
        created_at__date=today
    ).count()

    # ============================================
    # EXPENSE REPORTS
    # ============================================
    total_expenses = Expense.objects.filter(
        tenant=tenant,
        status__in=['approved', 'paid']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    today_expenses = Expense.objects.filter(
        tenant=tenant,
        status__in=['approved', 'paid'],
        date=today
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    month_expenses = Expense.objects.filter(
        tenant=tenant,
        status__in=['approved', 'paid'],
        date__gte=month_start,
        date__lte=today
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    pending_expenses = Expense.objects.filter(
        tenant=tenant,
        status='pending'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # ============================================
    # PROFIT CALCULATIONS
    # ============================================
    gross_profit = total_sales - total_expenses
    today_profit = today_sales - today_expenses
    month_profit = month_sales - month_expenses

    # Profit margin
    profit_margin = (gross_profit / total_sales * 100) if total_sales > 0 else 0

    # ============================================
    # PRODUCT STATS
    # ============================================
    total_products = Product.objects.filter(
        tenant=tenant,
        is_active=True
    ).count()

    total_product_categories = Category.objects.filter(
        tenant=tenant,
        is_active=True
    ).count()

    total_suppliers = Supplier.objects.filter(
        tenant=tenant,
        is_active=True
    ).count()

    # Low stock products - FIXED: removed models.F, using F directly
    low_stock_products = Product.objects.filter(
        tenant=tenant,
        is_active=True,
        is_discontinued=False,
        available_quantity__lte=F('reorder_level')
    ).count()

    out_of_stock_products = Product.objects.filter(
        tenant=tenant,
        is_active=True,
        is_discontinued=False,
        available_quantity=0
    ).count()

    # Total stock value
    total_stock_value = Product.objects.filter(
        tenant=tenant,
        is_active=True
    ).aggregate(
        total=Sum('available_quantity') * F('default_buying_price')
    )['total'] or Decimal('0.00')

    # ============================================
    # CUSTOMER STATS
    # ============================================
    total_customers = Customer.objects.filter(
        tenant=tenant
    ).count()

    new_customers_month = Customer.objects.filter(
        tenant=tenant,
        created_at__date__gte=month_start
    ).count()

    # ============================================
    # USER STATS
    # ============================================
    total_users = User.objects.filter(
        tenant=tenant,
        is_active=True
    ).count()

    # Staff breakdown by role
    role_counts = User.objects.filter(
        tenant=tenant,
        is_active=True
    ).values('role').annotate(count=Count('id'))

    # ============================================
    # TOP PERFORMING PRODUCTS
    # ============================================
    top_products = SaleItem.objects.filter(
        sale__tenant=tenant,
        sale__status='completed'
    ).values(
        'product__id',
        'product__name',
        'product__sku_code',
        'product__brand',
        'product__model'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('subtotal')
    ).order_by('-total_revenue')[:10]

    # ============================================
    # RECENT ACTIVITY (Last 10 sales)
    # ============================================
    recent_sales = Sale.objects.filter(
        tenant=tenant,
        status='completed'
    ).select_related('customer', 'cashier').order_by('-created_at')[:10]

    # ============================================
    # DAILY SALES CHART DATA (Last 30 days)
    # ============================================
    daily_sales_data = []
    for i in range(30):
        date = today - timedelta(days=i)
        day_total = Sale.objects.filter(
            tenant=tenant,
            status='completed',
            created_at__date=date
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        daily_sales_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'day': date.strftime('%b %d'),
            'total': float(day_total)
        })
    daily_sales_data.reverse()

    # ============================================
    # EXPENSES BY CATEGORY
    # ============================================
    expenses_by_category = Expense.objects.filter(
        tenant=tenant,
        status__in=['approved', 'paid']
    ).values(
        'category__name'
    ).annotate(
        total=Sum('amount')
    ).order_by('-total')[:10]

    # ============================================
    # CONTEXT
    # ============================================
    context = {
        'tenant': tenant,

        # Sales data
        'total_sales': total_sales,
        'today_sales': today_sales,
        'yesterday_sales': yesterday_sales,
        'week_sales': week_sales,
        'month_sales': month_sales,
        'last_month_sales': last_month_sales,
        'total_sales_count': total_sales_count,
        'today_sales_count': today_sales_count,

        # Expense data
        'total_expenses': total_expenses,
        'today_expenses': today_expenses,
        'month_expenses': month_expenses,
        'pending_expenses': pending_expenses,

        # Profit data
        'gross_profit': gross_profit,
        'today_profit': today_profit,
        'month_profit': month_profit,
        'profit_margin': profit_margin,

        # Product data
        'total_products': total_products,
        'total_product_categories': total_product_categories,
        'total_suppliers': total_suppliers,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'total_stock_value': total_stock_value,

        # Customer data
        'total_customers': total_customers,
        'new_customers_month': new_customers_month,

        # User data
        'total_users': total_users,
        'role_counts': role_counts,

        # Top products
        'top_products': top_products,

        # Recent activity
        'recent_sales': recent_sales,

        # Chart data
        'daily_sales_data': daily_sales_data,
        'expenses_by_category': expenses_by_category,

        # Active tab
        'active_tab': 'reports',
    }

    return render(request, 'tronic_master/report_dashboard.html', context)


# ============================================
# INVENTORY REPORT VIEW
# ============================================

@login_required
def inventory_report(request):
    """Detailed inventory report"""
    tenant = request.user.tenant

    if not tenant:
        return render(request, 'tronic_master/reports/inventory_report.html', {
            'error': 'No tenant assigned'
        })

    # Get all products with stock info
    products = Product.objects.filter(
        tenant=tenant,
        is_active=True
    ).select_related('category', 'supplier', 'branch')

    # Summary stats
    total_products = products.count()
    total_value = products.aggregate(
        total=Sum('available_quantity') * F('default_buying_price')
    )['total'] or Decimal('0.00')

    # Products by category
    products_by_category = products.values(
        'category__name'
    ).annotate(
        count=Count('id'),
        total_value=Sum('available_quantity') * F('default_buying_price')
    ).order_by('-count')

    context = {
        'tenant': tenant,
        'products': products,
        'total_products': total_products,
        'total_value': total_value,
        'products_by_category': products_by_category,
        'active_tab': 'reports',
    }
    return render(request, 'tronic_master/inventory_report.html', context)


# ============================================
# SALES REPORT VIEW
# ============================================

@login_required
def sales_report(request):
    """Detailed sales report with filters"""
    tenant = request.user.tenant

    if not tenant:
        return render(request, 'tronic_master/reports/sales_report.html', {
            'error': 'No tenant assigned'
        })

    # Get filter parameters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    cashier_id = request.GET.get('cashier')

    # Base queryset
    sales = Sale.objects.filter(
        tenant=tenant,
        status='completed'
    ).select_related('customer', 'cashier', 'branch')

    # Apply filters
    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)
    if cashier_id:
        sales = sales.filter(cashier_id=cashier_id)

    # Summary
    total_sales = sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    total_count = sales.count()
    average_sale = total_sales / total_count if total_count > 0 else 0

    # Sales by payment method
    sales_by_payment = sales.values('payment_method').annotate(
        count=Count('id'),
        total=Sum('total')
    )

    context = {
        'tenant': tenant,
        'sales': sales,
        'total_sales': total_sales,
        'total_count': total_count,
        'average_sale': average_sale,
        'sales_by_payment': sales_by_payment,
        'active_tab': 'reports',
    }
    return render(request, 'tronic_master/sales_report.html', context)




# ============================================
# EXPORT REPORTS VIEW
# ============================================

@login_required
def export_reports(request):
    """Export reports in various formats (CSV, Excel, PDF)"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    report_type = request.GET.get('type', 'sales')
    format_type = request.GET.get('format', 'csv')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if request.method == 'POST':
        report_type = request.POST.get('report_type', 'sales')
        format_type = request.POST.get('format', 'csv')
        date_from = request.POST.get('date_from', '')
        date_to = request.POST.get('date_to', '')

        # Prepare data based on report type
        if report_type == 'sales':
            return export_sales_report(request, tenant, format_type, date_from, date_to)
        elif report_type == 'inventory':
            return export_inventory_report(request, tenant, format_type)
        elif report_type == 'stock':
            return export_stock_report(request, tenant, format_type)
        elif report_type == 'expenses':
            return export_expenses_report(request, tenant, format_type, date_from, date_to)
        else:
            messages.error(request, 'Invalid report type')
            return redirect('tronic_master:export_reports')

    context = {
        'tenant': tenant,
        'active_tab': 'reports',
        'request': request,  # Add request to context if needed in template
    }
    return render(request, 'tronic_master/export_reports.html', context)


def export_sales_report(request, tenant, format_type, date_from, date_to):
    """Export sales report"""
    import csv

    sales = Sale.objects.filter(
        tenant=tenant,
        status='completed'
    )

    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)

    sales = sales.select_related('customer', 'cashier', 'branch')

    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="sales_report.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Invoice No', 'Date', 'Customer', 'Phone', 'Branch',
            'Cashier', 'Subtotal', 'Discount', 'Tax', 'Total', 'Payment Method'
        ])

        for sale in sales:
            writer.writerow([
                sale.invoice_no,
                sale.created_at.strftime('%Y-%m-%d %H:%M'),
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

    elif format_type == 'excel':
        try:
            import pandas as pd
            from io import BytesIO

            data = []
            for sale in sales:
                data.append({
                    'Invoice No': sale.invoice_no,
                    'Date': sale.created_at.strftime('%Y-%m-%d %H:%M'),
                    'Customer': sale.customer_name or 'Walk-in',
                    'Phone': sale.customer_phone or '',
                    'Branch': sale.branch.name if sale.branch else '',
                    'Cashier': sale.cashier.get_full_name() if sale.cashier else '',
                    'Subtotal': float(sale.subtotal),
                    'Discount': float(sale.discount),
                    'Tax': float(sale.tax),
                    'Total': float(sale.total),
                    'Payment Method': sale.get_payment_method_display()
                })

            df = pd.DataFrame(data)

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Sales Report', index=False)

            output.seek(0)
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="sales_report.xlsx"'
            return response
        except ImportError:
            messages.error(request, 'pandas library is not installed. Please install pandas and openpyxl.')
            return redirect('tronic_master:export_reports')

    messages.error(request, 'Unsupported format')
    return redirect('tronic_master:export_reports')


def export_inventory_report(request, tenant, format_type):
    """Export inventory report"""
    import csv

    products = Product.objects.filter(
        tenant=tenant,
        is_active=True
    ).select_related('category', 'supplier', 'branch')

    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="inventory_report.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'SKU', 'Name', 'Brand', 'Model', 'Category', 'Branch',
            'Buying Price', 'Selling Price', 'Best Price',
            'Total Stock', 'Available', 'Reserved', 'Damaged',
            'Reorder Level', 'Stock Value'
        ])

        for product in products:
            stock_value = product.available_quantity * product.default_buying_price
            writer.writerow([
                product.sku_code,
                product.name,
                product.brand,
                product.model,
                product.category.name if product.category else '',
                product.branch.name if product.branch else '',
                float(product.default_buying_price),
                float(product.default_selling_price),
                float(product.default_best_price) if product.default_best_price else '',
                product.total_quantity,
                product.available_quantity,
                product.reserved_quantity,
                product.damaged_quantity,
                product.reorder_level,
                float(stock_value)
            ])

        return response

    elif format_type == 'excel':
        try:
            import pandas as pd
            from io import BytesIO

            data = []
            for product in products:
                stock_value = product.available_quantity * product.default_buying_price
                data.append({
                    'SKU': product.sku_code,
                    'Name': product.name,
                    'Brand': product.brand,
                    'Model': product.model,
                    'Category': product.category.name if product.category else '',
                    'Branch': product.branch.name if product.branch else '',
                    'Buying Price': float(product.default_buying_price),
                    'Selling Price': float(product.default_selling_price),
                    'Best Price': float(product.default_best_price) if product.default_best_price else '',
                    'Total Stock': product.total_quantity,
                    'Available': product.available_quantity,
                    'Reserved': product.reserved_quantity,
                    'Damaged': product.damaged_quantity,
                    'Reorder Level': product.reorder_level,
                    'Stock Value': float(stock_value)
                })

            df = pd.DataFrame(data)

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Inventory Report', index=False)

            output.seek(0)
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="inventory_report.xlsx"'
            return response
        except ImportError:
            messages.error(request, 'pandas library is not installed. Please install pandas and openpyxl.')
            return redirect('tronic_master:export_reports')

    messages.error(request, 'Unsupported format')
    return redirect('tronic_master:export_reports')


def export_stock_report(request, tenant, format_type):
    """Export stock report (product units)"""
    import csv

    units = ProductUnit.objects.filter(
        tenant=tenant
    ).select_related('product', 'branch', 'current_owner', 'supplier')

    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="stock_report.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Product', 'SKU', 'IMEI', 'Serial', 'Branch',
            'Status', 'Condition', 'Owner', 'Buying Price', 'Selling Price',
            'Purchase Date', 'Warranty End'
        ])

        for unit in units:
            writer.writerow([
                unit.product.name,
                unit.product.sku_code,
                unit.imei_number or '',
                unit.serial_number or '',
                unit.branch.name if unit.branch else '',
                unit.get_status_display(),
                unit.get_condition_display(),
                unit.current_owner.get_full_name() if unit.current_owner else '',
                float(unit.unit_buying_price or unit.product.default_buying_price),
                float(unit.unit_selling_price or unit.product.default_selling_price),
                unit.purchase_date.strftime('%Y-%m-%d') if unit.purchase_date else '',
                unit.warranty_end.strftime('%Y-%m-%d') if unit.warranty_end else '',
            ])

        return response

    elif format_type == 'excel':
        try:
            import pandas as pd
            from io import BytesIO

            data = []
            for unit in units:
                data.append({
                    'Product': unit.product.name,
                    'SKU': unit.product.sku_code,
                    'IMEI': unit.imei_number or '',
                    'Serial': unit.serial_number or '',
                    'Branch': unit.branch.name if unit.branch else '',
                    'Status': unit.get_status_display(),
                    'Condition': unit.get_condition_display(),
                    'Owner': unit.current_owner.get_full_name() if unit.current_owner else '',
                    'Buying Price': float(unit.unit_buying_price or unit.product.default_buying_price),
                    'Selling Price': float(unit.unit_selling_price or unit.product.default_selling_price),
                    'Purchase Date': unit.purchase_date.strftime('%Y-%m-%d') if unit.purchase_date else '',
                    'Warranty End': unit.warranty_end.strftime('%Y-%m-%d') if unit.warranty_end else '',
                })

            df = pd.DataFrame(data)

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Stock Report', index=False)

            output.seek(0)
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="stock_report.xlsx"'
            return response
        except ImportError:
            messages.error(request, 'pandas library is not installed. Please install pandas and openpyxl.')
            return redirect('tronic_master:export_reports')

    messages.error(request, 'Unsupported format')
    return redirect('tronic_master:export_reports')


def export_expenses_report(request, tenant, format_type, date_from, date_to):
    """Export expenses report"""
    import csv

    expenses = Expense.objects.filter(
        tenant=tenant
    ).select_related('category', 'created_by')

    if date_from:
        expenses = expenses.filter(date__gte=date_from)
    if date_to:
        expenses = expenses.filter(date__lte=date_to)

    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="expenses_report.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Title', 'Category', 'Amount', 'Date', 'Status',
            'Payment Method', 'Description', 'Created By'
        ])

        for expense in expenses:
            writer.writerow([
                expense.title,
                expense.category.name if expense.category else '',
                float(expense.amount),
                expense.date.strftime('%Y-%m-%d'),
                expense.get_status_display() if hasattr(expense, 'get_status_display') else expense.status,
                expense.get_payment_method_display() if hasattr(expense, 'get_payment_method_display') else expense.payment_method,
                expense.description or '',
                expense.created_by.get_full_name() if expense.created_by else ''
            ])

        return response

    elif format_type == 'excel':
        try:
            import pandas as pd
            from io import BytesIO

            data = []
            for expense in expenses:
                data.append({
                    'Title': expense.title,
                    'Category': expense.category.name if expense.category else '',
                    'Amount': float(expense.amount),
                    'Date': expense.date.strftime('%Y-%m-%d'),
                    'Status': expense.get_status_display() if hasattr(expense, 'get_status_display') else expense.status,
                    'Payment Method': expense.get_payment_method_display() if hasattr(expense, 'get_payment_method_display') else expense.payment_method,
                    'Description': expense.description or '',
                    'Created By': expense.created_by.get_full_name() if expense.created_by else ''
                })

            df = pd.DataFrame(data)

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Expenses Report', index=False)

            output.seek(0)
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="expenses_report.xlsx"'
            return response
        except ImportError:
            messages.error(request, 'pandas library is not installed. Please install pandas and openpyxl.')
            return redirect('tronic_master:export_reports')

    messages.error(request, 'Unsupported format')
    return redirect('tronic_master:export_reports')





# ============================================
# STAFF ATTENDANCE VIEWS (Using Users)
# ============================================

@login_required
def staff_attendance(request):
    """View staff attendance for users"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    # Get all users (staff) for this tenant
    users = User.objects.filter(tenant=tenant, is_active=True).order_by('username')

    # Get attendance records (if you have an attendance model for users)
    # If you don't have attendance records, create a placeholder
    attendances = []

    today = datetime.now().date()
    for user in users[:10]:  # Show last 10 users with attendance
        # Create sample attendance data
        attendance = {
            'user': user,
            'date': today,
            'status': 'present',  # You can calculate this from actual data
            'check_in_time': '09:00',
            'check_out_time': '17:00',
            'hours_worked': 8.0,
            'branch': user.branch if hasattr(user, 'branch') else None,
        }
        attendances.append(attendance)

    # Filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    user_id = request.GET.get('user')
    status = request.GET.get('status')

    # Apply filters if you have actual attendance data
    if date_from:
        attendances = [a for a in attendances if a['date'] >= datetime.strptime(date_from, '%Y-%m-%d').date()]
    if date_to:
        attendances = [a for a in attendances if a['date'] <= datetime.strptime(date_to, '%Y-%m-%d').date()]
    if user_id:
        attendances = [a for a in attendances if a['user'].id == int(user_id)]
    if status:
        attendances = [a for a in attendances if a['status'] == status]

    # Pagination
    paginator = Paginator(attendances, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'attendances': page_obj,
        'staff_members': users,  # Users as staff
        'statuses': [
            ('present', 'Present'),
            ('absent', 'Absent'),
            ('late', 'Late'),
            ('half_day', 'Half Day'),
            ('leave', 'On Leave'),
            ('holiday', 'Holiday'),
        ],
        'tenant': tenant,
        'active_tab': 'staff',
    }
    return render(request, 'tronic_master/staff_attendance.html', context)


@login_required
def staff_attendance_detail(request, staff_id):
    """View attendance for a specific user"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    user = get_object_or_404(User, id=staff_id, tenant=tenant)

    # Get attendance records for this user
    attendances = []

    # If you have an attendance model, query it here
    # For now, create sample data
    from datetime import datetime, timedelta

    today = datetime.now().date()
    for i in range(30):
        date = today - timedelta(days=i)
        status = 'present' if i % 5 != 0 else 'absent'
        attendances.append({
            'date': date,
            'status': status,
            'check_in_time': '09:00' if status == 'present' else None,
            'check_out_time': '17:00' if status == 'present' else None,
            'hours_worked': 8.0 if status == 'present' else 0,
            'user': user,
        })

    paginator = Paginator(attendances, 30)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'staff': user,  # User object
        'attendances': page_obj,
        'tenant': tenant,
        'active_tab': 'staff',
    }
    return render(request, 'tronic_master/staff_attendance_detail.html', context)


# ============================================
# STAFF LEAVE VIEWS (Using Users)
# ============================================

@login_required
def staff_leave_list(request):
    """View staff leave requests for users"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    # Get all users
    users = User.objects.filter(tenant=tenant, is_active=True)

    # Get leave requests (if you have a Leave model)
    # For now, create placeholder data with proper IDs
    leaves_list = []

    from datetime import datetime, timedelta

    today = datetime.now().date()

    # Create placeholder leaves with proper IDs
    for idx, user in enumerate(users[:5]):  # Show 5 users with leave requests
        leave = {
            'id': idx + 1,
            'user': user,
            'staff': user,  # Add staff key for template compatibility
            'staff_name': user.get_full_name() or user.username,
            'leave_type': 'annual',
            'start_date': today,
            'end_date': today + timedelta(days=3),
            'days': 3,
            'reason': 'Annual vacation',
            'status': 'pending',
            'created_at': datetime.now(),
        }
        leaves_list.append(leave)

    # Also add some approved and rejected ones
    if len(users) > 2:
        leave = {
            'id': len(users) + 1,
            'user': users[2],
            'staff': users[2],
            'staff_name': users[2].get_full_name() or users[2].username,
            'leave_type': 'sick',
            'start_date': today - timedelta(days=10),
            'end_date': today - timedelta(days=8),
            'days': 2,
            'reason': 'Sick leave',
            'status': 'approved',
            'created_at': datetime.now(),
        }
        leaves_list.append(leave)

    if len(users) > 3:
        leave = {
            'id': len(users) + 2,
            'user': users[3],
            'staff': users[3],
            'staff_name': users[3].get_full_name() or users[3].username,
            'leave_type': 'compassionate',
            'start_date': today - timedelta(days=5),
            'end_date': today - timedelta(days=4),
            'days': 1,
            'reason': 'Compassionate leave',
            'status': 'rejected',
            'created_at': datetime.now(),
        }
        leaves_list.append(leave)

    # Apply filters
    status = request.GET.get('status')
    leave_type = request.GET.get('type')
    user_id = request.GET.get('user')

    if status:
        leaves_list = [l for l in leaves_list if l['status'] == status]
    if leave_type:
        leaves_list = [l for l in leaves_list if l['leave_type'] == leave_type]
    if user_id:
        leaves_list = [l for l in leaves_list if l['user'].id == int(user_id)]

    paginator = Paginator(leaves_list, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Convert to objects with proper attributes for template
    # Create a simple class or use SimpleNamespace
    from types import SimpleNamespace

    leaves = []
    for leave_dict in page_obj:
        # Create a SimpleNamespace object with all the attributes
        leave_obj = SimpleNamespace(**leave_dict)
        # Add the staff attribute
        leave_obj.staff = leave_dict['user']
        leave_obj.staff_name = leave_dict['staff_name']
        # Add get_status_display method
        def get_status_display(self):
            return self.status.title()
        leave_obj.get_status_display = get_status_display.__get__(leave_obj)
        # Add get_leave_type_display method
        def get_leave_type_display(self):
            return self.leave_type.title().replace('_', ' ')
        leave_obj.get_leave_type_display = get_leave_type_display.__get__(leave_obj)
        leaves.append(leave_obj)

    context = {
        'leaves': leaves,
        'staff_members': users,
        'statuses': [
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        'leave_types': [
            ('annual', 'Annual Leave'),
            ('sick', 'Sick Leave'),
            ('maternity', 'Maternity Leave'),
            ('paternity', 'Paternity Leave'),
            ('compassionate', 'Compassionate Leave'),
            ('study', 'Study Leave'),
            ('other', 'Other'),
        ],
        'tenant': tenant,
        'active_tab': 'staff',
    }
    return render(request, 'tronic_master/staff_leave_list.html', context)


@login_required
def staff_leave_create(request):
    """Create a leave request for a user"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    if request.method == 'POST':
        user_id = request.POST.get('staff')
        leave_type = request.POST.get('leave_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')

        # Validate inputs
        if not user_id:
            messages.error(request, 'Please select a staff member')
            return redirect('tronic_master:staff_leave_create')

        if not leave_type:
            messages.error(request, 'Please select a leave type')
            return redirect('tronic_master:staff_leave_create')

        if not start_date or not end_date:
            messages.error(request, 'Please select start and end dates')
            return redirect('tronic_master:staff_leave_create')

        if not reason:
            messages.error(request, 'Please provide a reason for the leave')
            return redirect('tronic_master:staff_leave_create')

        # Get the user
        user = get_object_or_404(User, id=user_id, tenant=tenant)

        # Create leave record (if you have a Leave model)
        # For now, just show a success message
        from datetime import datetime
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end - start).days + 1

        messages.success(
            request,
            f'Leave request created for {user.get_full_name() or user.username}! '
            f'({days} days, {leave_type})'
        )
        return redirect('tronic_master:staff_leave_list')

    # GET request - show the form
    staff_members = User.objects.filter(tenant=tenant, is_active=True).order_by('first_name', 'last_name')

    context = {
        'staff_members': staff_members,
        'leave_types': [
            ('annual', 'Annual Leave'),
            ('sick', 'Sick Leave'),
            ('maternity', 'Maternity Leave'),
            ('paternity', 'Paternity Leave'),
            ('compassionate', 'Compassionate Leave'),
            ('study', 'Study Leave'),
            ('other', 'Other'),
        ],
        'tenant': tenant,
        'active_tab': 'staff',
    }
    return render(request, 'tronic_master/staff_leave_form.html', context)


@login_required
def staff_leave_approve(request, leave_id):
    """Approve a leave request"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    # If you have a Leave model, get it and approve
    # For now, just show a success message
    messages.success(request, 'Leave approved successfully!')
    return redirect('tronic_master:staff_leave_list')


@login_required
def staff_leave_reject(request, leave_id):
    """Reject a leave request"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('portal:dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    # If you have a Leave model, get it and reject
    # For now, just show a success message
    messages.success(request, 'Leave rejected successfully!')
    return redirect('tronic_master:staff_leave_list')


# ============================================
# MANAGE STAFF VIEW
# ============================================

@login_required
def manage_staff(request):
    """Manage all staff - list, edit, delete in one place"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    # Get all users for this tenant
    users = User.objects.filter(tenant=tenant).order_by('username')

    # Filters
    search_query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '')
    custom_role_filter = request.GET.get('custom_role', '')
    status_filter = request.GET.get('status', '')
    branch_filter = request.GET.get('branch', '')

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )

    if role_filter:
        users = users.filter(role=role_filter)

    # Filter by custom role
    from apps.shared.permissions.models import UserRoleAssignment, Role
    if custom_role_filter:
        user_ids_with_custom_role = UserRoleAssignment.objects.filter(
            role_id=custom_role_filter,
            is_active=True
        ).values_list('user_id', flat=True)
        users = users.filter(id__in=user_ids_with_custom_role)

    if status_filter:
        users = users.filter(is_active=(status_filter == 'active'))

    # Get branches for filter
    branches = Branch.objects.filter(tenant=tenant, is_active=True)

    # Get custom roles for filter
    custom_roles = Role.objects.filter(is_active=True).order_by('name')

    # Statistics
    total_staff = users.count()
    active_staff = users.filter(is_active=True).count()
    inactive_staff = users.filter(is_active=False).count()

    # Get system roles for filter
    system_roles = [
        ('admin', 'Admin'),
        ('user', 'User'),
        ('manager', 'Manager'),
    ]

    if request.method == 'POST':
        action = request.POST.get('action')
        staff_ids = request.POST.getlist('staff_ids')

        if action == 'delete':
            for staff_id in staff_ids:
                try:
                    user = User.objects.get(id=staff_id, tenant=tenant)
                    # Don't delete super admins or tenant admins
                    if user.is_super_admin or user.is_tenant_admin:
                        messages.warning(request, f'Cannot delete admin user: {user.username}')
                        continue
                    user.delete()
                except User.DoesNotExist:
                    pass
            messages.success(request, 'Selected users deleted successfully!')
        elif action == 'activate':
            User.objects.filter(id__in=staff_ids, tenant=tenant).update(is_active=True)
            messages.success(request, 'Selected users activated!')
        elif action == 'deactivate':
            User.objects.filter(id__in=staff_ids, tenant=tenant).update(is_active=False)
            messages.success(request, 'Selected users deactivated!')

        return redirect('tronic_master:manage_staff')

    # Pagination
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'tenant': tenant,
        'staff_members': page_obj,
        'branches': branches,
        'custom_roles': custom_roles,
        'roles': system_roles,
        'search_query': search_query,
        'role_filter': role_filter,
        'custom_role_filter': custom_role_filter,
        'status_filter': status_filter,
        'branch_filter': branch_filter,
        'total_staff': total_staff,
        'active_staff': active_staff,
        'inactive_staff': inactive_staff,
        'active_tab': 'staff',
    }
    return render(request, 'tronic_master/manage_staff.html', context)



# ============================================
# STAFF LIST VIEW
# ============================================

@login_required
def staff_list(request):
    """List all staff (users) with their roles"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')

    # Check permission
    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    # Get all users for this tenant
    users = User.objects.filter(tenant=tenant).order_by('username')

    # Prefetch roles for all users
    for user in users:
        # Get Tech Master roles for this user
        user.tech_roles = ProjectRole.objects.filter(
            users=user,
            tenant=tenant,
            project_type='tronic_master',
            is_active=True
        )
        # Get role names as string
        user.role_names = ', '.join([r.name for r in user.tech_roles])

    # Filters
    search = request.GET.get('search', '')
    role = request.GET.get('role', '')
    custom_role_id = request.GET.get('custom_role', '')
    branch_id = request.GET.get('branch', '')
    status = request.GET.get('status', '')

    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone_number__icontains=search)
        )

    if role:
        users = users.filter(role=role)

    # Filter by custom role
    if custom_role_id:
        user_ids_with_role = ProjectRole.objects.filter(
            id=custom_role_id,
            tenant=tenant,
            project_type='tronic_master',
            is_active=True
        ).values_list('users', flat=True)
        users = users.filter(id__in=user_ids_with_role)

    if status:
        users = users.filter(is_active=(status == 'active'))

    # Get all custom roles for filter dropdown
    custom_roles = ProjectRole.objects.filter(
        tenant=tenant,
        project_type='tronic_master',
        is_active=True
    ).order_by('name')

    # Get branches for filter
    branches = Branch.objects.filter(tenant=tenant, is_active=True)

    # System roles for filter
    system_roles = [
        ('admin', 'Admin'),
        ('user', 'User'),
    ]

    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'tenant': tenant,
        'staff_members': page_obj,
        'branches': branches,
        'custom_roles': custom_roles,
        'roles': system_roles,
        'search': search,
        'role_filter': role,
        'custom_role_filter': custom_role_id,
        'branch_filter': branch_id,
        'status_filter': status,
        'active_tab': 'staff',
    }
    return render(request, 'tronic_master/staff_list.html', context)


# ============================================
# STAFF CREATE/EDIT VIEW
# ============================================

@login_required
@check_user_limit
def staff_create(request):
    """Create a new staff user with system and custom roles"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    # System roles (EXCLUDE super_admin)
    system_roles = [
        ('admin', 'Admin'),
        ('user', 'User'),
    ]

    # Custom roles for Tech Master (ProjectRole)
    custom_roles = ProjectRole.objects.filter(
        tenant=tenant,
        project_type='tronic_master',
        is_active=True
    ).order_by('name')

    # Get branches for the form
    branches = Branch.objects.filter(tenant=tenant, is_active=True).order_by('name')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        system_role = request.POST.get('system_role')
        custom_role_id = request.POST.get('custom_role')
        branch_id = request.POST.get('branch')
        hire_date = request.POST.get('hire_date')
        pin = request.POST.get('pin', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        # Debug
        print(f"📝 Creating staff - Username: {username}, Custom Role ID: {custom_role_id}")

        # Validate required fields
        if not username:
            messages.error(request, 'Username is required')
            return redirect('tronic_master:staff_create')

        if not password:
            messages.error(request, 'Password is required')
            return redirect('tronic_master:staff_create')

        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters')
            return redirect('tronic_master:staff_create')

        if not first_name or not last_name:
            messages.error(request, 'First name and last name are required')
            return redirect('tronic_master:staff_create')

        if not email:
            messages.error(request, 'Email is required')
            return redirect('tronic_master:staff_create')

        if not system_role:
            messages.error(request, 'System role is required')
            return redirect('tronic_master:staff_create')

        # Validate system role (prevent super_admin)
        if system_role == 'super_admin':
            messages.error(request, 'Cannot create super admin users')
            return redirect('tronic_master:staff_create')

        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists')
            return redirect('tronic_master:staff_create')

        # Check if email exists
        if User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" already exists')
            return redirect('tronic_master:staff_create')

        # ✅ Create user - is_staff=False (no admin panel access)
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            role=system_role,  # System role (admin or user)
            tenant=tenant,
            is_active=is_active,
            is_staff=False  # No admin panel access
        )

        # ✅ Assign branch if provided
        if branch_id:
            try:
                branch = Branch.objects.get(id=branch_id, tenant=tenant)
                if hasattr(user, 'branch'):
                    user.branch = branch
                    user.save()
            except Branch.DoesNotExist:
                messages.warning(request, 'Selected branch not found')

        # ✅ Set hire date if provided
        if hire_date:
            try:
                from datetime import datetime
                user.hire_date = datetime.strptime(hire_date, '%Y-%m-%d').date()
                user.save()
            except (ValueError, TypeError):
                pass

        # Set PIN if provided
        if pin and len(pin) >= 4 and pin.isdigit():
            user.pin_code = pin
            user.save()

        # ✅ **FIXED: Use Role model for UserRoleAssignment**
        from apps.shared.permissions.models import Role, UserRoleAssignment

        role_name = 'Staff'  # Default role name
        project_role = None

        if custom_role_id:
            try:
                # Get the ProjectRole
                project_role = get_object_or_404(ProjectRole, id=custom_role_id, tenant=tenant)
                role_name = project_role.name

                # ✅ Add user to ProjectRole's many-to-many
                project_role.users.add(user)
                project_role.save()

            except ProjectRole.DoesNotExist:
                messages.warning(request, 'Selected custom role not found')

        # ✅ Create or get a Role with the same name
        role, created = Role.objects.get_or_create(
            name=role_name,
            defaults={
                'codename': role_name.lower().replace(' ', '_'),
                'is_active': True
            }
        )

        # ✅ Create UserRoleAssignment with the Role
        assignment = UserRoleAssignment.objects.create(
            user=user,
            role=role,  # ✅ Now using Role, not ProjectRole
            is_active=True,
            assigned_by=request.user
        )

        messages.success(request, f'Role "{role_name}" assigned to {username}')
        messages.success(request, f'User "{username}" created successfully!')
        return redirect('tronic_master:staff_detail', staff_id=user.id)

    context = {
        'system_roles': system_roles,
        'custom_roles': custom_roles,
        'branches': branches,
        'tenant': tenant,
        'active_tab': 'staff',
        'staff': None,
        'staff_custom_role': None,
    }
    return render(request, 'tronic_master/staff_form.html', context)


@login_required
def staff_edit(request, staff_id):
    """Edit staff user with system and custom roles"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    user = get_object_or_404(User, id=staff_id, tenant=tenant)

    # Prevent editing super_admin users
    if user.role == 'super_admin':
        messages.error(request, 'Cannot edit super admin users')
        return redirect('tronic_master:staff_list')

    # System roles (EXCLUDE super_admin)
    system_roles = [
        ('admin', 'Admin'),
        ('user', 'User'),
    ]

    # Custom roles for Tech Master
    custom_roles = ProjectRole.objects.filter(
        tenant=tenant,
        project_type='tronic_master',
        is_active=True
    ).order_by('name')

    # Get branches for the form
    branches = Branch.objects.filter(tenant=tenant, is_active=True).order_by('name')

    # Get user's current custom roles
    user_custom_roles = ProjectRole.objects.filter(
        users=user,
        tenant=tenant,
        project_type='tronic_master',
        is_active=True
    )
    user_custom_role = user_custom_roles.first()
    user_custom_role_ids = [r.id for r in user_custom_roles]

    # Get user's current branch
    user_branch_id = None
    if hasattr(user, 'branch') and user.branch:
        user_branch_id = user.branch.id
    elif hasattr(user, 'tech_staff_profile') and user.tech_staff_profile:
        user_branch_id = user.tech_staff_profile.branch.id

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        system_role = request.POST.get('system_role')
        custom_role_id = request.POST.get('custom_role')
        branch_id = request.POST.get('branch')
        hire_date = request.POST.get('hire_date')
        pin = request.POST.get('pin', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        # Debug
        print(f"📝 Editing staff - Username: {username}, Custom Role ID: {custom_role_id}")

        # Validate
        if not username:
            messages.error(request, 'Username is required')
            return redirect('tronic_master:staff_edit', staff_id=user.id)

        if not first_name or not last_name:
            messages.error(request, 'First name and last name are required')
            return redirect('tronic_master:staff_edit', staff_id=user.id)

        if not email:
            messages.error(request, 'Email is required')
            return redirect('tronic_master:staff_edit', staff_id=user.id)

        if not system_role:
            messages.error(request, 'System role is required')
            return redirect('tronic_master:staff_edit', staff_id=user.id)

        # Check if username exists (excluding current user)
        if User.objects.filter(username=username).exclude(id=user.id).exists():
            messages.error(request, f'Username "{username}" already exists')
            return redirect('tronic_master:staff_edit', staff_id=user.id)

        # Check if email exists (excluding current user)
        if User.objects.filter(email=email).exclude(id=user.id).exists():
            messages.error(request, f'Email "{email}" already exists')
            return redirect('tronic_master:staff_edit', staff_id=user.id)

        # ✅ Update user
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.phone_number = phone_number
        user.role = system_role
        user.is_active = is_active
        user.is_staff = False  # Keep no admin panel access

        # Update password if provided
        if password:
            if len(password) < 8:
                messages.error(request, 'Password must be at least 8 characters')
                return redirect('tronic_master:staff_edit', staff_id=user.id)
            user.set_password(password)

        # Update PIN if provided
        if pin and len(pin) >= 4 and pin.isdigit():
            user.pin_code = pin
        elif pin:
            messages.error(request, 'PIN must be exactly 4 digits')
            return redirect('tronic_master:staff_edit', staff_id=user.id)

        user.save()

        # ✅ Update branch
        if branch_id:
            try:
                branch = Branch.objects.get(id=branch_id, tenant=tenant)
                if hasattr(user, 'branch'):
                    user.branch = branch
                    user.save()
            except Branch.DoesNotExist:
                pass

        # ✅ Update custom role
        from apps.shared.permissions.models import Role, UserRoleAssignment

        # ✅ Remove existing ProjectRole assignments
        existing_roles = ProjectRole.objects.filter(users=user, tenant=tenant)
        for role in existing_roles:
            role.users.remove(user)

        # ✅ Remove existing UserRoleAssignments
        UserRoleAssignment.objects.filter(user=user).delete()

        # ✅ Get the role name
        role_name = 'Staff'  # Default
        project_role = None

        if custom_role_id:
            try:
                # Get the ProjectRole
                project_role = get_object_or_404(ProjectRole, id=custom_role_id, tenant=tenant)
                role_name = project_role.name

                # ✅ Add user to ProjectRole's many-to-many
                project_role.users.add(user)
                project_role.save()

            except ProjectRole.DoesNotExist:
                messages.warning(request, 'Selected custom role not found')

        # ✅ Create or get a Role with the same name
        role, created = Role.objects.get_or_create(
            name=role_name,
            defaults={
                'codename': role_name.lower().replace(' ', '_'),
                'is_active': True
            }
        )

        # ✅ Create UserRoleAssignment with the Role
        assignment = UserRoleAssignment.objects.create(
            user=user,
            role=role,
            is_active=True,
            assigned_by=request.user
        )

        messages.success(request, f'Role "{role_name}" assigned to {username}')
        messages.success(request, f'Staff "{username}" updated successfully!')
        return redirect('tronic_master:staff_detail', staff_id=user.id)

    context = {
        'staff': user,
        'system_roles': system_roles,
        'custom_roles': custom_roles,
        'user_custom_role_ids': user_custom_role_ids,
        'staff_custom_role': user_custom_role,
        'branches': branches,
        'user_branch_id': user_branch_id,
        'tenant': tenant,
        'active_tab': 'staff',
    }
    return render(request, 'tronic_master/staff_form.html', context)





# ============================================
# STAFF DETAIL VIEW
# ===========================================

@login_required
def staff_detail(request, staff_id):
    """View staff (user) details"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    # ✅ Get the User object
    user = get_object_or_404(User, id=staff_id, tenant=tenant)

    # ✅ Get user's custom roles
    user_custom_roles = ProjectRole.objects.filter(
        users=user,
        tenant=tenant,
        project_type='tronic_master',
        is_active=True
    )

    # ✅ Get user's branch
    user_branch = None
    if hasattr(user, 'branch') and user.branch:
        user_branch = user.branch
    elif hasattr(user, 'tech_staff_profile') and user.tech_staff_profile:
        user_branch = user.tech_staff_profile.branch

    context = {
        'staff': user,  # User object
        'user_custom_roles': user_custom_roles,
        'user_branch': user_branch,
        'tenant': tenant,
        'active_tab': 'staff',
    }
    return render(request, 'tronic_master/staff_detail.html', context)



# ============================================
# STAFF DELETE VIEW
# ============================================

@login_required
def staff_delete(request, staff_id):
    """Delete staff user"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    user = get_object_or_404(User, id=staff_id, tenant=tenant)

    # Prevent deleting self
    if user.id == request.user.id:
        messages.error(request, 'You cannot delete your own account!')
        return redirect('tronic_master:staff_list')

    # Prevent deleting super admins
    if user.is_super_admin:
        messages.error(request, 'Cannot delete a super admin user!')
        return redirect('tronic_master:staff_list')

    if request.method == 'POST':
        username = user.username
        # Remove from all roles first
        roles = ProjectRole.objects.filter(users=user, tenant=tenant)
        for role in roles:
            role.users.remove(user)
        user.delete()
        messages.success(request, f'User "{username}" deleted successfully!')
        return redirect('tronic_master:staff_list')

    context = {
        'staff': user,
        'tenant': tenant,
        'active_tab': 'staff',
    }
    return render(request, 'tronic_master/staff_confirm_delete.html', context)


# ============================================
# STAFF TOGGLE STATUS VIEW
# ============================================

@login_required
def staff_toggle_status(request, staff_id):
    """Toggle staff user active status"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    user = get_object_or_404(User, id=staff_id, tenant=tenant)

    # Prevent toggling self
    if user.id == request.user.id:
        messages.error(request, 'You cannot change your own status!')
        return redirect('tronic_master:staff_list')

    user.is_active = not user.is_active
    user.save()

    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User "{user.username}" {status}!')
    return redirect('tronic_master:staff_list')


# ============================================
# ROLE LIST VIEW
# ============================================

@login_required
def role_list(request):
    """List all roles for Tech Master"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    # Get all Tech Master roles for this tenant
    roles = ProjectRole.objects.filter(
        tenant=tenant,
        project_type='tronic_master',
        is_active=True
    ).order_by('name')

    # Get user count for each role
    for role in roles:
        role.user_count = role.users.count()
        role.permission_count = len(role.permissions)

    context = {
        'tenant': tenant,
        'roles': roles,
        'active_tab': 'roles',
    }
    return render(request, 'tronic_master/role_list.html', context)


# ============================================
# ROLE CREATE VIEW
# ============================================y

@login_required
def role_create(request):
    """Create a new role with permissions"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    # Get all available Tech Master permissions
    from apps.tronic_master.permissions import TRONIC_MASTER_PERMISSIONS

    # Group permissions by category
    permission_groups = {}
    for codename, name in TRONIC_MASTER_PERMISSIONS.items():
        # Extract category from codename
        category = 'Other'
        if 'product' in codename:
            category = 'Products'
        elif 'category' in codename:
            category = 'Categories'
        elif 'branch' in codename:
            category = 'Branches'
        elif 'stock' in codename:
            category = 'Stock'
        elif 'sale' in codename:
            category = 'Sales'
        elif 'staff' in codename:
            category = 'Staff'
        elif 'report' in codename:
            category = 'Reports'
        elif 'setting' in codename:
            category = 'Settings'
        elif 'dashboard' in codename:
            category = 'Dashboard'

        if category not in permission_groups:
            permission_groups[category] = []

        # Store as dict with codename as identifier
        permission_groups[category].append({
            'codename': codename,
            'name': name,
            'id': codename  # Use codename as ID
        })

    if request.method == 'POST':
        role_name = request.POST.get('role_name')
        description = request.POST.get('description', '')
        permission_list = request.POST.getlist('permissions')
        is_system_role = request.POST.get('is_system_role') == 'on'

        if not role_name:
            messages.error(request, 'Please enter a role name.')
            return render(request, 'tronic_master/role_form.html', {
                'tenant': tenant,
                'permissions_by_model': permission_groups,  # <-- Use this variable name
                'role_permissions': [],
                'active_tab': 'roles',
            })

        # Check if role already exists
        if ProjectRole.objects.filter(tenant=tenant, project_type='tronic_master', name=role_name).exists():
            messages.error(request, f'A role named "{role_name}" already exists.')
            return render(request, 'tronic_master/role_form.html', {
                'tenant': tenant,
                'permissions_by_model': permission_groups,  # <-- Use this variable name
                'role_permissions': [],
                'active_tab': 'roles',
            })

        # Create the role
        role = ProjectRole.objects.create(
            tenant=tenant,
            project_type='tronic_master',
            name=role_name,
            description=description,
            permissions=permission_list,
            is_system_role=is_system_role,
            created_by=request.user
        )

        messages.success(request, f'Role "{role_name}" created successfully!')
        return redirect('tronic_master:role_list')

    context = {
        'tenant': tenant,
        'permissions_by_model': permission_groups,  # <-- Use this variable name
        'role_permissions': [],
        'active_tab': 'roles',
    }
    return render(request, 'tronic_master/role_form.html', context)


# ============================================
# ROLE EDIT VIEW
# ============================================

@login_required
def role_edit(request, role_id):
    """Edit a role and its permissions"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    role = get_object_or_404(ProjectRole, id=role_id, tenant=tenant, project_type='tronic_master')

    # Get all available Tech Master permissions
    from apps.tronic_master.permissions import TRONIC_MASTER_PERMISSIONS

    # Group permissions by category
    permission_groups = {}
    for codename, name in TRONIC_MASTER_PERMISSIONS.items():
        # Extract category from codename
        category = 'Other'
        if 'product' in codename:
            category = 'Products'
        elif 'category' in codename:
            category = 'Categories'
        elif 'branch' in codename:
            category = 'Branches'
        elif 'stock' in codename:
            category = 'Stock'
        elif 'sale' in codename:
            category = 'Sales'
        elif 'staff' in codename:
            category = 'Staff'
        elif 'report' in codename:
            category = 'Reports'
        elif 'setting' in codename:
            category = 'Settings'
        elif 'dashboard' in codename:
            category = 'Dashboard'

        if category not in permission_groups:
            permission_groups[category] = []

        permission_groups[category].append({
            'codename': codename,
            'name': name,
            'id': codename  # Use codename as ID
        })

    if request.method == 'POST':
        role_name = request.POST.get('role_name')
        description = request.POST.get('description', '')
        permission_list = request.POST.getlist('permissions')
        is_active = request.POST.get('is_active') == 'on'

        if not role_name:
            messages.error(request, 'Please enter a role name.')
            return render(request, 'tronic_master/role_form.html', {
                'tenant': tenant,
                'role': role,
                'permissions_by_model': permission_groups,  # <-- Use this variable name
                'role_permissions': role.permissions,
                'active_tab': 'roles',
            })

        # Check if name conflicts (excluding current role)
        if ProjectRole.objects.filter(tenant=tenant, project_type='tronic_master', name=role_name).exclude(id=role.id).exists():
            messages.error(request, f'A role named "{role_name}" already exists.')
            return render(request, 'tronic_master/role_form.html', {
                'tenant': tenant,
                'role': role,
                'permissions_by_model': permission_groups,  # <-- Use this variable name
                'role_permissions': role.permissions,
                'active_tab': 'roles',
            })

        # Update the role
        role.name = role_name
        role.description = description
        role.permissions = permission_list
        role.is_active = is_active
        role.save()

        messages.success(request, f'Role "{role_name}" updated successfully!')
        return redirect('tronic_master:role_list')

    context = {
        'tenant': tenant,
        'role': role,
        'permissions_by_model': permission_groups,  # <-- Use this variable name
        'role_permissions': role.permissions,
        'active_tab': 'roles',
    }
    return render(request, 'tronic_master/role_form.html', context)


# ============================================
# ROLE DELETE VIEW
# ============================================

@login_required
def role_delete(request, role_id):
    """Delete a role"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    role = get_object_or_404(ProjectRole, id=role_id, tenant=tenant, project_type='tronic_master')

    if request.method == 'POST':
        # Check if system role
        if role.is_system_role:
            messages.error(request, 'Cannot delete system roles.')
            return redirect('tronic_master:role_list')

        # Check if role has users
        if role.users.count() > 0:
            messages.error(request, f'Cannot delete "{role.name}" because it has {role.users.count()} users assigned.')
            return redirect('tronic_master:role_list')

        role_name = role.name
        role.delete()
        messages.success(request, f'Role "{role_name}" deleted successfully!')
        return redirect('tronic_master:role_list')

    context = {
        'tenant': tenant,
        'role': role,
        'active_tab': 'roles',
    }
    return render(request, 'tronic_master/role_confirm_delete.html', context)


# ============================================
# ROLE ASSIGN VIEW
# ============================================

@login_required
def role_user_list(request, role_id):
    """Get users with a specific role (AJAX)"""
    tenant = request.user.tenant

    if not tenant:
        return JsonResponse({'error': 'No tenant assigned'}, status=400)

    from apps.shared.roles.models import ProjectRole

    try:
        role = get_object_or_404(
            ProjectRole,
            id=role_id,
            tenant=tenant,
            project_type='tronic_master'
        )

        # ✅ Simple ManyToMany - get users directly
        users = role.users.filter(is_active=True).order_by('first_name', 'last_name')

        user_list = []
        for user in users:
            user_list.append({
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name() or user.username,
                'email': user.email or '',
                'assigned_at': role.created_at.strftime('%Y-%m-%d %H:%M'),
            })

        return JsonResponse({
            'success': True,
            'role_name': role.name,
            'users': user_list,
            'count': len(user_list)
        })

    except ProjectRole.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Role not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def role_assign(request):
    """Assign a role to a user"""
    tenant = request.user.tenant

    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')

    if not request.user.is_super_admin and not request.user.is_tenant_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('tronic_master:dashboard')

    from apps.shared.roles.models import ProjectRole

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role_id = request.POST.get('role_id')
        action = request.POST.get('action', 'assign')

        if not user_id or not role_id:
            messages.error(request, 'Please select both user and role.')
            return redirect('tronic_master:role_assign')

        try:
            user = get_object_or_404(User, id=user_id, tenant=tenant)
            role = get_object_or_404(
                ProjectRole,
                id=role_id,
                tenant=tenant,
                project_type='tronic_master'
            )

            if action == 'assign':
                # ✅ Simple ManyToMany - add user to role
                if role.users.filter(id=user.id).exists():
                    messages.info(request, f'User already has role "{role.name}"')
                else:
                    role.users.add(user)
                    messages.success(request, f'Role "{role.name}" assigned to {user.username}!')

            elif action == 'remove':
                # ✅ Simple ManyToMany - remove user from role
                if role.users.filter(id=user.id).exists():
                    role.users.remove(user)
                    messages.success(request, f'Role "{role.name}" removed from {user.username}!')
                else:
                    messages.warning(request, f'User does not have role "{role.name}"')

        except (User.DoesNotExist, ProjectRole.DoesNotExist) as e:
            messages.error(request, f'Error: {str(e)}')

        return redirect('tronic_master:role_assign')

    # GET request - show the form
    users = User.objects.filter(tenant=tenant, is_active=True).order_by('username')
    roles = ProjectRole.objects.filter(
        tenant=tenant,
        project_type='tronic_master',
        is_active=True
    ).order_by('name')

    # ✅ Get current assignments - check membership directly
    assignment_data = []
    for role in roles:
        for user in role.users.filter(is_active=True):
            assignment_data.append({
                'user': user,
                'role': role,
                'assignment_id': f"{role.id}_{user.id}",
            })

    context = {
        'tenant': tenant,
        'users': users,
        'roles': roles,
        'assignments': assignment_data,
        'active_tab': 'roles',
    }
    return render(request, 'tronic_master/role_assign.html', context)


@login_required
def role_remove_user(request, assignment_id):
    """Remove a role assignment from a user"""
    if request.method == 'POST':
        try:
            assignment = get_object_or_404(UserRoleAssignment, id=assignment_id)
            assignment.delete()
            messages.success(request, 'Role removed from user successfully!')
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})
