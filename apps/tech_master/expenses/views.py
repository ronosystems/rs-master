# apps/tech_master/expenses/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import Expense, ExpenseCategory

# ============================================
# EXPENSE LIST VIEW
# ============================================

@login_required
def expense_list(request):
    """List all expenses"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned to your account')
        return redirect('dashboard')
    
    expenses = Expense.objects.filter(tenant=tenant)
    
    # Filters
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    date_filter = request.GET.get('date', '')
    search = request.GET.get('search', '')
    
    if status_filter:
        expenses = expenses.filter(status=status_filter)
    if category_filter:
        expenses = expenses.filter(category_id=category_filter)
    if search:
        expenses = expenses.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search)
        )
    
    today = timezone.now().date()
    if date_filter == 'today':
        expenses = expenses.filter(date=today)
    elif date_filter == 'week':
        start = today - timedelta(days=today.weekday())
        expenses = expenses.filter(date__gte=start)
    elif date_filter == 'month':
        expenses = expenses.filter(date__year=today.year, date__month=today.month)
    
    # Statistics
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    pending_count = expenses.filter(status='pending').count()
    approved_count = expenses.filter(status='approved').count()
    paid_count = expenses.filter(status='paid').count()
    rejected_count = expenses.filter(status='rejected').count()
    
    categories = ExpenseCategory.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'expenses': expenses,
        'total_expenses': total_expenses,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'paid_count': paid_count,
        'rejected_count': rejected_count,
        'categories': categories,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'date_filter': date_filter,
        'search': search,
    }
    return render(request, 'tech_master/expenses/list.html', context)


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
            return redirect('tech_master:add_expense')
        
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
        return redirect('tech_master:expense_detail', expense_id=expense.id)
    
    categories = ExpenseCategory.objects.filter(tenant=tenant, is_active=True)
    
    context = {
        'tenant': tenant,
        'categories': categories,
    }
    return render(request, 'tech_master/expenses/add.html', context)


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
    return render(request, 'tech_master/expenses/detail.html', context)


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
        return redirect('tech_master:expense_list')
    
    # Check if already approved
    if expense.status == 'approved':
        messages.warning(request, f'Expense "{expense.title}" is already approved')
        return redirect('tech_master:expense_detail', expense_id=expense.id)
    
    expense.approve(request.user)
    messages.success(request, f'Expense "{expense.title}" approved successfully')
    return redirect('tech_master:expense_detail', expense_id=expense.id)


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
        return redirect('tech_master:expense_list')
    
    # Check if already rejected
    if expense.status == 'rejected':
        messages.warning(request, f'Expense "{expense.title}" is already rejected')
        return redirect('tech_master:expense_detail', expense_id=expense.id)
    
    expense.reject(request.user)
    messages.success(request, f'Expense "{expense.title}" rejected')
    return redirect('tech_master:expense_detail', expense_id=expense.id)


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
        return redirect('tech_master:expense_list')
    
    # Check if already paid
    if expense.status == 'paid':
        messages.warning(request, f'Expense "{expense.title}" is already marked as paid')
        return redirect('tech_master:expense_detail', expense_id=expense.id)
    
    expense.mark_paid()
    messages.success(request, f'Expense "{expense.title}" marked as paid')
    return redirect('tech_master:expense_detail', expense_id=expense.id)


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
    return render(request, 'tech_master/expenses/report.html', context)


# ============================================
# CATEGORY MANAGEMENT (OPTIONAL)
# ============================================

@login_required
def category_list(request):
    """List all expense categories"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    categories = ExpenseCategory.objects.filter(tenant=tenant).order_by('name')
    
    context = {
        'tenant': tenant,
        'categories': categories,
    }
    return render(request, 'tech_master/expenses/category_list.html', context)


@login_required
def add_category(request):
    """Add expense category"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name:
            messages.error(request, 'Category name is required')
            return redirect('tech_master:add_expense_category')
        
        if ExpenseCategory.objects.filter(tenant=tenant, name__iexact=name).exists():
            messages.error(request, f'Category "{name}" already exists')
            return redirect('tech_master:add_expense_category')
        
        category = ExpenseCategory.objects.create(
            tenant=tenant,
            name=name,
            description=description,
            is_active=is_active
        )
        
        messages.success(request, f'Category "{category.name}" created successfully!')
        return redirect('tech_master:expense_category_list')
    
    return render(request, 'tech_master/expenses/add_category.html', {'tenant': tenant})


@login_required
def edit_category(request, category_id):
    """Edit expense category"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    category = get_object_or_404(ExpenseCategory, id=category_id, tenant=tenant)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        
        if not name:
            messages.error(request, 'Category name is required')
            return redirect('tech_master:edit_expense_category', category_id=category.id)
        
        if ExpenseCategory.objects.filter(tenant=tenant, name__iexact=name).exclude(id=category.id).exists():
            messages.error(request, f'Category "{name}" already exists')
            return redirect('tech_master:edit_expense_category', category_id=category.id)
        
        category.name = name
        category.description = description
        category.is_active = is_active
        category.save()
        
        messages.success(request, f'Category "{category.name}" updated successfully!')
        return redirect('tech_master:expense_category_list')
    
    context = {
        'tenant': tenant,
        'category': category,
    }
    return render(request, 'tech_master/expenses/edit_category.html', context)


@login_required
def delete_category(request, category_id):
    """Delete expense category"""
    tenant = request.user.tenant
    
    if not tenant:
        messages.error(request, 'No tenant assigned')
        return redirect('dashboard')
    
    category = get_object_or_404(ExpenseCategory, id=category_id, tenant=tenant)
    
    if category.expenses.exists():
        messages.error(request, f'Cannot delete "{category.name}" because it has expenses associated with it.')
        return redirect('tech_master:expense_category_list')
    
    category_name = category.name
    category.delete()
    messages.success(request, f'Category "{category_name}" deleted successfully!')
    return redirect('tech_master:expense_category_list')