from django.contrib import admin
from .models import CashDrawer, CashTransaction

@admin.register(CashDrawer)
class CashDrawerAdmin(admin.ModelAdmin):
    list_display = ['id', 'cashier', 'opening_amount', 'closing_amount', 'is_open', 'opened_at']
    list_filter = ['is_open', 'tenant']
    search_fields = ['cashier__username']

@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    list_display = ['drawer', 'amount', 'transaction_type', 'reason', 'created_at']
    list_filter = ['transaction_type']
    search_fields = ['reason']
