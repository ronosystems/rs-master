from django.contrib import admin
from .models import (
    HardwareCategory, HardwareProduct, HardwareSupplier,
    HardwareSale, HardwareSaleItem, HardwareStockEntry
)

@admin.register(HardwareCategory)
class HardwareCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'is_active', 'product_count']
    list_filter = ['tenant', 'is_active']
    search_fields = ['name', 'description']

@admin.register(HardwareProduct)
class HardwareProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'quantity', 'unit_price', 'is_low_stock']
    list_filter = ['tenant', 'category', 'is_active', 'unit']
    search_fields = ['name', 'sku', 'description']

@admin.register(HardwareSupplier)
class HardwareSupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_person', 'phone', 'email', 'is_active']
    list_filter = ['tenant', 'is_active']
    search_fields = ['name', 'contact_person', 'phone']

@admin.register(HardwareSale)
class HardwareSaleAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'customer_name', 'net_amount', 'status', 'created_at']
    list_filter = ['tenant', 'status', 'payment_method']
    search_fields = ['invoice_number', 'customer_name', 'customer_phone']

@admin.register(HardwareSaleItem)
class HardwareSaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'product', 'quantity', 'unit_price', 'total_price']

@admin.register(HardwareStockEntry)
class HardwareStockEntryAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity', 'entry_type', 'created_at', 'created_by']
    list_filter = ['entry_type', 'created_at']
    search_fields = ['product__name', 'notes']