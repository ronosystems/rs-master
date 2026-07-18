from django.contrib import admin
from .models import LiquorCategory, LiquorProduct, LiquorSale

@admin.register(LiquorCategory)
class LiquorCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'is_active']
    list_filter = ['tenant', 'is_active']
    search_fields = ['name']

@admin.register(LiquorProduct)
class LiquorProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'brand', 'sku', 'price', 'quantity', 'is_active']
    list_filter = ['tenant', 'category', 'is_active']
    search_fields = ['name', 'brand', 'sku']

@admin.register(LiquorSale)
class LiquorSaleAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'customer_name', 'total_amount', 'payment_method', 'created_at']
    list_filter = ['tenant', 'payment_method', 'status']
    search_fields = ['invoice_number', 'customer_name']