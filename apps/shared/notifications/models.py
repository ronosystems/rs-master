# apps/shared/notifications/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
import logging

from apps.shared.tenants.models import Tenant

# ✅ ADD THIS IMPORT FOR SYNC QUEUE
from apps.shared.tenants.models import SyncQueue

logger = logging.getLogger(__name__)


class Notification(models.Model):
    """Notification model - Shared across ALL projects"""
    
    NOTIFICATION_TYPES = [
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('system', 'System'),
        ('sale', 'Sale'),
        ('stock', 'Stock Alert'),
        ('booking', 'Booking'),
        ('payment', 'Payment'),
    ]
    
    # Relationships
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True
    )
    
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Content
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.URLField(blank=True, null=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_notifications'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['tenant']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def mark_as_unread(self):
        """Mark notification as unread"""
        self.is_read = False
        self.read_at = None
        self.save()
    
    @classmethod
    def get_unread_count(cls, user):
        """Get unread notification count for a user"""
        return cls.objects.filter(recipient=user, is_read=False).count()


class NotificationPreference(models.Model):
    """User notification preferences"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    # Specific notification types
    notify_on_sale = models.BooleanField(default=True)
    notify_on_stock = models.BooleanField(default=True)
    notify_on_payment = models.BooleanField(default=True)
    notify_on_booking = models.BooleanField(default=True)
    notify_on_system = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user.username}'s Preferences"
    
    def save(self, *args, **kwargs):
        """Save notification preferences and queue for sync"""
        is_new = self.pk is None
        user_id = self.user_id
        tenant_id = self.user.tenant_id if self.user and self.user.tenant_id else None
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync (only if user has a tenant)
        if getattr(settings, 'OFFLINE_MODE', False) and tenant_id:
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='NotificationPreference',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'user_id': user_id,
                        'email_notifications': self.email_notifications,
                        'push_notifications': self.push_notifications,
                        'sms_notifications': self.sms_notifications,
                        'notify_on_sale': self.notify_on_sale,
                        'notify_on_stock': self.notify_on_stock,
                        'notify_on_payment': self.notify_on_payment,
                        'notify_on_booking': self.notify_on_booking,
                        'notify_on_system': self.notify_on_system,
                        'tenant_id': tenant_id,
                    }
                )
                logger.debug(f"✅ Queued NotificationPreference sync for user {self.user.username}")
            except Exception as e:
                logger.error(f"Failed to queue NotificationPreference sync: {e}")
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create notification preferences for a user"""
        obj, created = cls.objects.get_or_create(user=user)
        return obj