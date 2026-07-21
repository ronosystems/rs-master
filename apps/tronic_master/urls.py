# apps/tronic_master/urls.py - Add these missing URL patterns

from django.urls import path
from . import views
from apps.shared.portal import views as portal_views
from apps.tronic_master import views as inventory_views
from apps.tronic_master import views as sales_views
from apps.shared.portal import api_views as pos_api_views

app_name = 'tronic_master'

urlpatterns = [
    # ============================================
    # DASHBOARD (Uses portal view)
    # ============================================
    path('', portal_views.tech_dashboard, name='dashboard'),
    
    # ============================================
    # POS (Uses portal view)
    # ============================================
    path('pos/', portal_views.tech_pos, name='pos'),
    path('pos/verify-pin/', portal_views.verify_pin, name='verify_pin'),
    path('pos/verify-pin-ajax/', portal_views.verify_pin_ajax, name='verify_pin_ajax'),
    path('pos/clear-pin/', portal_views.clear_pin_verification, name='clear_pin'),
    
    # ============================================
    # POS API
    # ============================================
    path('api/search-product/', pos_api_views.search_product, name='api_search_product'),
    path('api/get-cart/', pos_api_views.get_cart, name='api_get_cart'),
    path('api/add-to-cart/', pos_api_views.add_to_cart, name='api_add_to_cart'),
    path('api/update-cart/', pos_api_views.update_cart, name='api_update_cart'),
    path('api/update-cart-price/', pos_api_views.update_cart_price, name='api_update_cart_price'),
    path('api/remove-from-cart/', pos_api_views.remove_from_cart, name='api_remove_from_cart'),
    path('api/clear-cart/', pos_api_views.clear_cart, name='api_clear_cart'),
    path('api/search-customer/', pos_api_views.search_customer, name='api_search_customer'),
    path('api/add-customer/', pos_api_views.add_customer, name='api_add_customer'),
    path('api/process-payment/', pos_api_views.process_payment, name='api_process_payment'),
    path('api/get-product-units/', pos_api_views.get_product_units, name='api_get_product_units'),
    
    # ============================================
    # INVENTORY
    # ============================================
    # Product CRUD
    path('inventory/', inventory_views.product_list, name='product_list'),
    path('inventory/add/', inventory_views.add_product_selection, name='add_product_selection'),
    path('inventory/add-single/', inventory_views.add_single_product, name='add_single_product'),
    path('edit_single_product/<int:product_id>/', views.edit_single_product, name='edit_single_product'),
    path('inventory/add-bulk/', inventory_views.add_bulk_product, name='add_bulk_product'),
    path('inventory/<int:product_id>/edit-bulk/', inventory_views.edit_bulk_product, name='edit_bulk_product'),
    path('inventory/<int:product_id>/', inventory_views.product_detail, name='product_detail'),
    path('inventory/<int:product_id>/edit/', inventory_views.edit_product, name='edit_product'),
    path('inventory/<int:product_id>/delete/', inventory_views.delete_product, name='delete_product'),
    path('inventory/manage/', inventory_views.manage_products, name='manage_products'),
    
    # Product Units
    path('inventory/<int:product_id>/add-unit/', inventory_views.add_unit, name='add_unit'),
    path('inventory/unit/<int:unit_id>/edit/', inventory_views.edit_unit, name='edit_unit'),
    path('inventory/unit/<int:unit_id>/delete/', inventory_views.delete_unit, name='delete_unit'),
    
    # Product Restock & Adjustment
    path('inventory/<int:product_id>/restock/', inventory_views.restock_product, name='restock_product'),
    path('inventory/<int:product_id>/adjust/', inventory_views.stock_adjustment, name='stock_adjustment'),
    
    # Categories
    path('categories/', inventory_views.category_list, name='category_list'),
    path('categories/add/', inventory_views.add_category, name='add_category'),
    path('categories/<int:category_id>/edit/', inventory_views.edit_category, name='edit_category'),
    path('categories/<int:category_id>/delete/', inventory_views.delete_category, name='delete_category'),
    path('categories/manage/', inventory_views.manage_categories, name='manage_categories'),
    
    # Branches
    path('branches/', inventory_views.branch_list, name='branch_list'),
    path('branches/add/', inventory_views.add_branch, name='add_branch'),
    path('branches/<int:branch_id>/edit/', inventory_views.edit_branch, name='edit_branch'),
    path('branches/<int:branch_id>/delete/', inventory_views.delete_branch, name='delete_branch'),
    path('branches/assign-manager/', inventory_views.assign_branch_manager, name='assign_branch_manager'),
    
    # Suppliers
    path('suppliers/', inventory_views.supplier_list, name='supplier_list'),
    path('suppliers/add/', inventory_views.add_supplier, name='add_supplier'),
    path('suppliers/<int:supplier_id>/edit/', inventory_views.edit_supplier, name='edit_supplier'),
    path('suppliers/<int:supplier_id>/delete/', inventory_views.delete_supplier, name='delete_supplier'),
    path('suppliers/manage/', inventory_views.manage_suppliers, name='manage_suppliers'), 
    
    # Import/Export
    path('import/', inventory_views.import_products, name='import_products'),
    path('export/template/', inventory_views.download_product_template, name='download_product_template'),
    path('export/imei-template/', inventory_views.download_imei_template, name='download_imei_template'),
    
    # Barcodes
    path('barcodes/', inventory_views.barcode_labels_list, name='barcode_labels_list'),
    path('barcodes/print/', inventory_views.print_labels, name='print_labels'),
    path('barcodes/bulk-print/', inventory_views.bulk_print_labels, name='bulk_print_labels'),
    path('barcodes/<int:product_id>/label/', inventory_views.barcode_label, name='barcode_label'),
    
    # Low Stock Alert
    path('low-stock/', inventory_views.low_stock_alert, name='low_stock_alert'),
    
    # Product Transfer
    path('transfer/', inventory_views.move_product_ownership, name='move_product_ownership'),
    path('assign/', inventory_views.assign_products_to_agent, name='assign_products_to_agent'),
    
    # Branch Stock
    path('branch-stock/', inventory_views.branch_stock_list, name='branch_stock_list'),
    path('branch-stock/<int:branch_id>/', inventory_views.branch_stock_detail, name='branch_stock_detail'),
    
    # Stock Transfer
    path('transfer-stock/', inventory_views.transfer_stock, name='transfer_stock'),
    
    # Stock History & Report
    path('stock-report/', inventory_views.stock_report, name='stock_report'),
    path('stock-history/', inventory_views.stock_history, name='stock_history'),
    path('damaged-report/', inventory_views.damaged_units_report, name='damaged_units_report'),
    path('stock-history/<int:product_id>/', inventory_views.stock_history, name='stock_history_product'),
    path('stock/manage/', inventory_views.manage_stock, name='manage_stock'),
    path('stock/take/', inventory_views.stock_take, name='stock_take'),  
    path('stock/adjust/<int:product_id>/', inventory_views.stock_adjustment, name='stock_adjustment'),

    # Stock Management
    path('stock-management/', views.stock_management, name='stock_management'),
    
    # API Endpoints
    path('api/transfer-unit/', views.transfer_unit, name='transfer_unit_api'),
    path('api/reserve-unit/<int:unit_id>/', views.reserve_unit, name='reserve_unit_api'),

    
    # ============================================
    # SALES
    # ============================================
    # Sales Agent
    path('my-sales/', sales_views.my_sales, name='my_sales'),
    path('my-stock/', sales_views.my_stock, name='my_stock'),
    path('agent-sale/', sales_views.agent_sale, name='agent_sale'),
    path('my-stock/<int:unit_id>/sell/', sales_views.my_stock_sell, name='my_stock_sell'),
    path('my-stock/<int:unit_id>/', sales_views.my_stock_detail, name='my_stock_detail'),
    path('sales-search/', sales_views.sales_search, name='sales_search'),
    path('api/sales-search/', sales_views.sales_search_ajax, name='sales_search_ajax'),
    
    # Sales Management
    path('sales/', sales_views.sales_history, name='sales_history'),
    path('sales/<int:sale_id>/', sales_views.sale_detail, name='sale_detail'),
    path('sales/<int:sale_id>/receipt/', sales_views.receipt, name='receipt'),
    path('sales/<int:sale_id>/reverse/', sales_views.reverse_sale, name='sale_reverse'),
    path('sales/<int:sale_id>/return/', sales_views.create_return, name='create_return'),
    
    # Receipt Search
    path('receipt-search/', sales_views.receipt_search, name='receipt_search'),
    
    # ============================================
    # PRICE CHECK
    # ============================================
    path('price-check/', sales_views.price_check, name='price_check'),
    path('api/price-check/', sales_views.price_check_ajax, name='price_check_ajax'),
    
    # Product Search (for quick lookup)
    path('product-search/', sales_views.product_search, name='product_search'),
    path('api/product-search/', sales_views.product_search_ajax, name='product_search_ajax'),
    
    # Returns
    path('returns/', sales_views.return_list, name='return_list'),
    path('returns/<int:return_id>/', sales_views.return_detail, name='return_detail'),

    # Refund
    path('refund/<int:sale_id>/', views.refund_sale, name='refund_sale'),

    # ============================================
    # EXPENSES
    # ============================================
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/report/', views.expense_report, name='expense_report'),
    path('expenses/add/', views.add_expense, name='add_expense'),
    path('expenses/<int:expense_id>/', views.expense_detail, name='expense_detail'),
    path('expenses/<int:expense_id>/approve/', views.approve_expense, name='approve_expense'),
    path('expenses/<int:expense_id>/reject/', views.reject_expense, name='reject_expense'),
    path('expenses/<int:expense_id>/pay/', views.mark_expense_paid, name='mark_expense_paid'),
    
    # Expense Categories
    path('expenses/categories/', views.category_list, name='expense_category_list'),
    path('expenses/categories/add/', views.add_category, name='add_expense_category'),
    path('expenses/categories/<int:category_id>/edit/', views.edit_category, name='edit_expense_category'),
    path('expenses/categories/<int:category_id>/delete/', views.delete_category, name='delete_expense_category'),

    # ============================================
    # ROLE & PERMISSION MANAGEMENT
    # ============================================
    path('roles/', views.role_list, name='role_list'),
    path('roles/create/', views.role_create, name='role_create'),
    path('roles/<int:role_id>/edit/', views.role_edit, name='role_edit'),
    path('roles/<int:role_id>/delete/', views.role_delete, name='role_delete'),
    path('roles/assign/', views.role_assign, name='role_assign'),
    path('roles/remove/<int:assignment_id>/', views.role_remove_user, name='role_remove_user'),
    path('roles/<int:role_id>/users/', views.role_user_list, name='role_user_list'),

    # ============================================
    # STAFF MANAGEMENT
    # ============================================
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.staff_create, name='staff_create'),
    path('staff/<int:staff_id>/', views.staff_detail, name='staff_detail'),
    path('staff/<int:staff_id>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<int:staff_id>/delete/', views.staff_delete, name='staff_delete'),
    path('staff/<int:staff_id>/toggle-status/', views.staff_toggle_status, name='staff_toggle_status'),
    path('staff/attendance/', views.staff_attendance, name='staff_attendance'),
    path('staff/attendance/<int:staff_id>/', views.staff_attendance_detail, name='staff_attendance_detail'),
    path('staff/leave/', views.staff_leave_list, name='staff_leave_list'),
    path('staff/leave/create/', views.staff_leave_create, name='staff_leave_create'),
    path('staff/leave/<int:leave_id>/approve/', views.staff_leave_approve, name='staff_leave_approve'),
    path('staff/leave/<int:leave_id>/reject/', views.staff_leave_reject, name='staff_leave_reject'),
    path('staff/manage/', views.manage_staff, name='manage_staff'),

    # ============================================
    # REPORTS
    # ============================================
    path('reports/dashboard/', views.report_dashboard, name='report_dashboard'),
    path('reports/sales/', views.sales_report, name='sales_report'),
    path('reports/inventory/', views.inventory_report, name='inventory_report'),
    path('reports/export/', views.export_reports, name='export_reports'),
]