# apps/shared/payments/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Payment, PaymentMethod, Refund


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'tenant', 'is_active', 'is_available']
    list_filter = ['is_active', 'is_available', 'tenant']
    search_fields = ['name', 'code']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description', 'icon')
        }),
        ('Status', {
            'fields': ('is_active', 'is_available')
        }),
        ('Tenant', {
            'fields': ('tenant',)
        }),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['reference', 'amount_display', 'payment_method', 'status_badge', 'customer', 'user', 'payment_date']
    list_filter = ['status', 'payment_method', 'payment_date']
    search_fields = ['reference', 'transaction_id', 'customer__name', 'user__username']
    readonly_fields = ['reference', 'payment_date', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Payment Details', {
            'fields': ('reference', 'amount', 'payment_method', 'status')
        }),
        ('Customer & User', {
            'fields': ('customer', 'user', 'tenant')
        }),
        ('References', {
            'fields': ('transaction_id', 'sale_id', 'invoice_number')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('payment_date', 'completed_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Amount')
    def amount_display(self, obj):
        return f"KES {obj.amount:,.2f}"
    
    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'pending': 'warning',
            'processing': 'info',
            'completed': 'success',
            'failed': 'danger',
            'refunded': 'secondary',
            'cancelled': 'dark',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    
    actions = ['mark_completed', 'mark_failed', 'mark_refunded']
    
    @admin.action(description="Mark selected as Completed")
    def mark_completed(self, request, queryset):
        count = 0
        for payment in queryset:
            if payment.status != 'completed':
                payment.mark_completed()
                count += 1
        self.message_user(request, f'Marked {count} payments as completed')
    
    @admin.action(description="Mark selected as Failed")
    def mark_failed(self, request, queryset):
        count = queryset.update(status='failed')
        self.message_user(request, f'Marked {count} payments as failed')
    
    @admin.action(description="Mark selected as Refunded")
    def mark_refunded(self, request, queryset):
        count = queryset.update(status='refunded')
        self.message_user(request, f'Marked {count} payments as refunded')


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['refund_reference', 'payment', 'amount_display', 'status_badge', 'requested_at']
    list_filter = ['status', 'requested_at']
    search_fields = ['refund_reference', 'payment__reference', 'reason']
    readonly_fields = ['refund_reference', 'requested_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Refund Details', {
            'fields': ('refund_reference', 'payment', 'amount', 'reason', 'status')
        }),
        ('Processing', {
            'fields': ('processed_by', 'processed_at')
        }),
        ('Timestamps', {
            'fields': ('requested_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Amount')
    def amount_display(self, obj):
        return f"KES {obj.amount:,.2f}"
    
    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'pending': 'warning',
            'approved': 'info',
            'rejected': 'danger',
            'completed': 'success',
            'failed': 'danger',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    
    actions = ['approve_refunds', 'reject_refunds']
    
    @admin.action(description="Approve selected refunds")
    def approve_refunds(self, request, queryset):
        count = 0
        for refund in queryset:
            if refund.status == 'pending':
                refund.approve(request.user)
                count += 1
        self.message_user(request, f'Approved {count} refunds')
    
    @admin.action(description="Reject selected refunds")
    def reject_refunds(self, request, queryset):
        count = 0
        for refund in queryset:
            if refund.status == 'pending':
                refund.reject(request.user)
                count += 1
        self.message_user(request, f'Rejected {count} refunds')