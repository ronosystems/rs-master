
from django.urls import path
from . import views


urlpatterns = [
    # Branch Managements
    path('branches/', views.branch_list, name='branch_list'),
    path('branches/add/', views.add_branch, name='add_branch'),
    path('branches/<int:branch_id>/edit/', views.edit_branch, name='edit_branch'),
    path('branches/<int:branch_id>/delete/', views.delete_branch, name='delete_branch'),

    # Product Category Management
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.add_category, name='add_category'),
    path('categories/edit/<int:category_id>/', views.edit_category, name='edit_category'),
    path('categories/delete/<int:category_id>/', views.delete_category, name='delete_category'),

    # Product Management CRUD
    path('', views.product_list, name='product_list'),
    path('add/', views.add_product, name='add_product'),
    path('add/selection/', views.add_product_selection, name='add_product_selection'),
    path('add/single/', views.add_single_product, name='add_single_product'),
    path('add/bulk/', views.add_bulk_product, name='add_bulk_product'),
    path('products/bulk/<int:product_id>/edit/', views.edit_bulk_product, name='edit_bulk_product'),
    path('<int:product_id>/', views.product_detail, name='product_detail'),
    path('<int:product_id>/edit/', views.edit_product, name='edit_product'),
    path('<int:product_id>/delete/', views.delete_product, name='delete_product'),
    
    # Unit management (direct edit/delete pages)
    # Unit URLs
    path('units/add/<int:product_id>/', views.add_unit, name='add_unit'),
    path('units/<int:unit_id>/edit/', views.edit_unit, name='edit_unit'),
    path('units/<int:unit_id>/delete/', views.delete_unit, name='delete_unit'),
    
    # Unit API endpoints
    path('api/unit/<int:unit_id>/', views.get_unit_api, name='get_unit_api'), 
    path('api/add-units/<int:product_id>/', views.api_add_units, name='api_add_units'),
    path('api/update-unit/<int:item_id>/', views.api_update_unit, name='api_update_unit'),
    path('api/delete-unit/<int:item_id>/', views.api_delete_unit, name='api_delete_unit'),
    path('api/move-unit/<int:item_id>/', views.api_move_unit, name='api_move_unit'),
    path('api/bulk-assign-units/', views.api_bulk_assign_units, name='api_bulk_assign_units'),
    path('api/assign-unit-owner/<int:unit_id>/', views.api_assign_unit_owner, name='api_assign_unit_owner'),
    
    # Other API endpoints
    path('api/inventory-item/<int:item_id>/', views.get_inventory_item_api, name='inventory_item_api'),
    path('inventory-item/<int:item_id>/update/', views.update_inventory_item, name='update_inventory_item'),
    path('inventory-item/<int:item_id>/delete/', views.delete_inventory_item, name='delete_inventory_item'),
    path('inventory-item/<int:item_id>/move/', views.move_inventory_item, name='move_inventory_item'),
    
    # Barcode URLs
    path('barcode/<int:product_id>/', views.barcode_label, name='barcode_label'),
    path('print-labels/', views.print_labels, name='print_labels'),
    path('bulk-print-labels/', views.bulk_print_labels, name='bulk_print_labels'),
    path('generate-label-pdf/', views.generate_label_pdf, name='generate_label_pdf'),
    path('barcode/labels/', views.barcode_labels_list, name='barcode_labels_list'),
    
    # Import/Export
    path('restock/<int:product_id>/', views.restock_product, name='restock_product'),
    path('import/', views.import_products, name='import_products'),
    path('download-imei-template/', views.download_imei_template, name='download_imei_template'),
    path('download-template/', views.download_product_template, name='download_product_template'),
    path('transfer/<int:product_id>/', views.transfer_product, name='transfer_product'),
    path('stock/adjustment/<int:product_id>/', views.stock_adjustment, name='stock_adjustment'),
]

# ============================================
# SYNC API ENDPOINTS (Added separately)
# ============================================

from rest_framework.routers import DefaultRouter
from .views import InventorySyncViewSet

router = DefaultRouter()
router.register(r'api/sync', InventorySyncViewSet, basename='sync')

urlpatterns += router.urls