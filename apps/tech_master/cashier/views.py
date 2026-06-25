
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import CashDrawer, CashTransaction
from apps.shared.tenants.models import Tenant

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
        difference = float(drawer.closing_amount) - float(expected)
        
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