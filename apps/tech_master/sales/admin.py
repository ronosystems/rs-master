from django.contrib import admin
from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['invoice_no', 'tenant', 'branch', 'cashier', 'total', 'payment_method', 'status', 'created_at']
    list_filter = ['tenant', 'branch', 'payment_method', 'status']
    search_fields = ['invoice_no', 'customer_name', 'customer_phone']
    inlines = [SaleItemInline]
    readonly_fields = ['invoice_no', 'created_at']
