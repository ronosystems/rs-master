# apps/shared/notifications/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient', 'type_badge', 'is_read', 'created_at']
    list_filter = ['type', 'is_read', 'tenant']
    search_fields = ['title', 'message', 'recipient__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'message', 'type', 'link')
        }),
        ('Recipient', {
            'fields': ('recipient', 'tenant')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Type')
    def type_badge(self, obj):
        """Display type as colored badge"""
        colors = {
            'info': 'info',
            'success': 'success',
            'warning': 'warning',
            'error': 'danger',
            'system': 'secondary',
            'sale': 'primary',
            'stock': 'warning',
            'booking': 'info',
            'payment': 'success',
        }
        color = colors.get(obj.type, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_type_display()
        )
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    @admin.action(description="Mark selected notifications as read")
    def mark_as_read(self, request, queryset):
        """Mark selected notifications as read"""
        count = queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(request, f'Marked {count} notifications as read')
    
    @admin.action(description="Mark selected notifications as unread")
    def mark_as_unread(self, request, queryset):
        """Mark selected notifications as unread"""
        count = queryset.update(is_read=False, read_at=None)
        self.message_user(request, f'Marked {count} notifications as unread')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'email_notifications', 'push_notifications', 'sms_notifications']
    search_fields = ['user__username', 'user__email']
    list_filter = ['email_notifications', 'push_notifications', 'sms_notifications']