# apps/fashion_master/urls.py

from django.urls import path
from . import views
from . import views_staff

app_name = 'fashion_master'

urlpatterns = [

    # Branches
    path('branches/', views.branch_list, name='branch_list'),
    path('branches/add/', views.add_branch, name='add_branch'),
    path('branches/<int:branch_id>/edit/', views.edit_branch, name='edit_branch'),
    path('branches/<int:branch_id>/delete/', views.delete_branch, name='delete_branch'),
    path('branches/stock/<int:branch_id>/', views.branch_stock_detail, name='branch_stock_detail'),
    path('branches/assign-manager/', views.assign_branch_manager, name='assign_branch_manager'),
    path('branches/stock/', views.branch_stock_list, name='branch_stock_list'),
    path('branches/transfer/', views.transfer_stock, name='transfer_stock'),


    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    
    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('products/<int:pk>/add-variant/', views.add_variant, name='add_variant'),
    
    # Variants
    path('variants/<int:pk>/edit/', views.variant_edit, name='variant_edit'),
    path('variants/<int:pk>/delete/', views.variant_delete, name='variant_delete'),
    
    # Sales
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/add/', views.sale_create, name='sale_create'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('sales/<int:pk>/receipt/', views.sale_receipt, name='sale_receipt'),
    path('sales/search/', views.search_sale, name='search_sale'),
    path('sales/search-ajax/', views.search_sale_ajax, name='search_sale_ajax'),
    
    # Returns
    path('returns/', views.return_list, name='return_list'),
    path('returns/<int:pk>/', views.return_detail, name='return_detail'),
    path('returns/<int:pk>/approve/', views.return_approve, name='return_approve'),
    path('returns/<int:pk>/reject/', views.return_reject, name='return_reject'),
    
    # Inventory
    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/movements/', views.inventory_movements, name='inventory_movements'),
    
    # Reports
    path('reports/', views.reports, name='reports'),
    # REPORTS
    path('reports/', views.reports_dashboard, name='reports'),
    path('reports/sales/', views.sales_report, name='sales_report'),
    path('reports/inventory/', views.inventory_report, name='inventory_report'),
    path('reports/expenses/', views.expense_report, name='expense_report'),
    path('reports/export/', views.export_report, name='export_report'),
    

    # STAFF MANAGEMENT
    # ============================================
    path('staff/', views_staff.staff_list, name='staff_list'),
    path('staff/add/', views_staff.staff_create, name='staff_create'),  # ADD THIS
    path('staff/<int:staff_id>/', views_staff.staff_detail, name='staff_detail'),
    path('staff/<int:staff_id>/edit/', views_staff.staff_edit, name='staff_edit'),  # ADD THIS
    path('staff/<int:staff_id>/delete/', views_staff.staff_delete, name='staff_delete'),  # ADD THIS
    path('staff/<int:staff_id>/toggle-status/', views_staff.staff_toggle_status, name='staff_toggle_status'),  # ADD THIS
    path('staff/attendance/', views_staff.staff_attendance, name='staff_attendance'),
    path('staff/attendance/<int:staff_id>/', views_staff.staff_attendance_detail, name='staff_attendance_detail'),  # ADD THIS
    path('staff/leave/', views_staff.staff_leave_list, name='staff_leave_list'),
    path('staff/leave/create/', views_staff.staff_leave_create, name='staff_leave_create'),  # ADD THIS
    path('staff/leave/<int:leave_id>/approve/', views_staff.staff_leave_approve, name='staff_leave_approve'),  # ADD THIS
    path('staff/leave/<int:leave_id>/reject/', views_staff.staff_leave_reject, name='staff_leave_reject'),  # ADD THIS
    
    # Roles
    path('roles/', views_staff.role_list, name='role_list'),
    path('roles/create/', views_staff.role_create, name='role_create'),
    path('roles/<int:role_id>/edit/', views_staff.role_edit, name='role_edit'),  # ADD THIS
    path('roles/<int:role_id>/delete/', views_staff.role_delete, name='role_delete'),  # ADD THIS
    path('roles/assign/', views_staff.role_assign, name='role_assign'),
    path('roles/remove/<int:assignment_id>/', views_staff.role_remove_user, name='role_remove_user'),  # ADD THIS

    # ============================================
    # API ENDPOINTS
    # ============================================
    path('api/search-products/', views.api_search_products, name='api_search_products'),
    path('api/process-sale/', views.api_process_sale, name='api_process_sale'),
    path('api/returns/<int:return_id>/approve/', views.api_approve_return, name='api_approve_return'),
    path('api/returns/<int:return_id>/reject/', views.api_reject_return, name='api_reject_return'),


    # ============================================
    # PRICE CHECK & PRODUCT SEARCH
    # ============================================
    path('price-check/', views.price_check, name='price_check'),
    path('price-check/search/', views.price_check_search, name='price_check_search'),
    path('product-search/', views.product_search, name='product_search'),
    path('product-search/search/', views.product_search_ajax, name='product_search_ajax'),
]