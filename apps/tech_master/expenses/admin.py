from django.contrib import admin
from .models import ExpenseCategory, Expense

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'is_active']
    list_filter = ['tenant', 'is_active']
    search_fields = ['name']

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'amount', 'date', 'payment_method', 'status', 'created_by']
    list_filter = ['status', 'payment_method', 'category']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
