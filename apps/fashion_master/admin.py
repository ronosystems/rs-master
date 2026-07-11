# apps/fashion_master/admin.py

from django.contrib import admin
from .models import (
    FashionCategory, FashionProduct, FashionVariant,
    FashionSale,  FashionInventoryMovement,
    FashionReturn, FashionStoreSettings, FashionCollection
)


@admin.register(FashionCategory)
class FashionCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'gender', 'size_type', 'is_active', 'product_count']
    list_filter = ['tenant', 'category_type', 'gender', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(FashionProduct)
class FashionProductAdmin(admin.ModelAdmin):
    list_display = ['sku_code', 'name', 'category', 'size', 'color', 'selling_price', 'available_quantity', 'is_active']
    list_filter = ['tenant', 'category', 'size', 'color', 'is_active', 'is_featured', 'is_new_arrival']
    search_fields = ['sku_code', 'name', 'brand', 'barcode']
    readonly_fields = ['created_at', 'updated_at', 'available_quantity']


@admin.register(FashionVariant)
class FashionVariantAdmin(admin.ModelAdmin):
    list_display = ['sku', 'product', 'size', 'color', 'quantity', 'selling_price']
    list_filter = ['tenant', 'product', 'size', 'color']
    search_fields = ['sku', 'barcode']


@admin.register(FashionSale)
class FashionSaleAdmin(admin.ModelAdmin):
    list_display = ['invoice_no', 'customer_name', 'total', 'payment_method', 'status', 'sale_date']
    list_filter = ['tenant', 'status', 'payment_method', 'sale_date']
    search_fields = ['invoice_no', 'customer_name', 'customer_phone']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(FashionReturn)
class FashionReturnAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'quantity', 'amount', 'status', 'created_at']
    list_filter = ['tenant', 'status', 'condition']
    search_fields = ['reason', 'product__name']


@admin.register(FashionInventoryMovement)
class FashionInventoryMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'movement_type', 'quantity', 'unit_price', 'created_at']
    list_filter = ['tenant', 'movement_type']
    search_fields = ['reference', 'notes']


@admin.register(FashionCollection)
class FashionCollectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'season', 'year', 'is_active']
    list_filter = ['tenant', 'season', 'year', 'is_active']
    search_fields = ['name', 'description']


@admin.register(FashionStoreSettings)
class FashionStoreSettingsAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'store_name', 'tax_rate', 'enable_loyalty']
    readonly_fields = ['created_at', 'updated_at']