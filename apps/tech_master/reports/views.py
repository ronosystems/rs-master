# apps/tech_master/reports/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F  
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from apps.tech_master.inventory.models import Product, Category, Supplier
from apps.tech_master.sales.models import Sale, SaleItem
from apps.tech_master.expenses.models import Expense
from apps.shared.users.models import User
from apps.shared.customers.models import Customer


@login_required
def report_dashboard(request):
    """Reports dashboard with comprehensive analytics"""
    tenant = request.user.tenant
    
    if not tenant:
        return render(request, 'tech_master/reports/dashboard.html', {
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
        total=Sum('available_quantity') * F('buying_price')
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
    
    return render(request, 'tech_master/reports/dashboard.html', context)


# ============================================
# INVENTORY REPORT VIEW
# ============================================

@login_required
def inventory_report(request):
    """Detailed inventory report"""
    tenant = request.user.tenant
    
    if not tenant:
        return render(request, 'tech_master/reports/inventory_report.html', {
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
        total=Sum('available_quantity') * F('buying_price')
    )['total'] or Decimal('0.00')
    
    # Products by category
    products_by_category = products.values(
        'category__name'
    ).annotate(
        count=Count('id'),
        total_value=Sum('available_quantity') * F('buying_price')
    ).order_by('-count')
    
    context = {
        'tenant': tenant,
        'products': products,
        'total_products': total_products,
        'total_value': total_value,
        'products_by_category': products_by_category,
        'active_tab': 'reports',
    }
    return render(request, 'tech_master/reports/inventory_report.html', context)


# ============================================
# SALES REPORT VIEW
# ============================================

@login_required
def sales_report(request):
    """Detailed sales report with filters"""
    tenant = request.user.tenant
    
    if not tenant:
        return render(request, 'tech_master/reports/sales_report.html', {
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
    return render(request, 'tech_master/reports/sales_report.html', context)