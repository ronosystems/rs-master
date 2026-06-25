# apps/shared/settings/models.py

from django.db import models
from django.conf import settings
import logging

from apps.shared.tenants.models import Tenant

# ✅ ADD THIS IMPORT FOR SYNC QUEUE
from apps.shared.tenants.models import SyncQueue

logger = logging.getLogger(__name__)


class SystemSetting(models.Model):
    """System settings stored in database"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'
        indexes = [
            models.Index(fields=['key']),
        ]
    
    def __str__(self):
        return f"{self.key} = {self.value}"
    
    def save(self, *args, **kwargs):
        """Save system setting and queue for sync"""
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync (system-wide, no tenant)
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=None,  # System-wide
                    model_name='SystemSetting',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'key': self.key,
                        'value': self.value,
                        'description': self.description,
                    }
                )
                logger.debug(f"✅ Queued SystemSetting sync: {self.key}")
            except Exception as e:
                logger.error(f"Failed to queue SystemSetting sync: {e}")
    
    @classmethod
    def get(cls, key, default=None):
        """Get a setting value"""
        try:
            setting = cls.objects.get(key=key)
            return setting.value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set(cls, key, value):
        """Set a setting value"""
        setting, created = cls.objects.update_or_create(
            key=key,
            defaults={'value': value}
        )
        return setting


class ReceiptSetting(models.Model):
    """Receipt settings per tenant"""
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='receipt_settings')
    
    # Business Details
    business_name = models.CharField(max_length=200, blank=True, default='')
    business_address = models.TextField(blank=True, default='')
    business_phone = models.CharField(max_length=20, blank=True, default='')
    business_email = models.EmailField(blank=True, default='')
    business_tax_pin = models.CharField(max_length=50, blank=True, default='')
    
    # Business Header Toggles
    show_business_name = models.BooleanField(default=True)
    show_address = models.BooleanField(default=True)
    show_phone = models.BooleanField(default=True)
    show_email = models.BooleanField(default=True)
    show_tax_pin = models.BooleanField(default=True)
    
    # Receipt Details Toggles
    show_receipt_number = models.BooleanField(default=True)
    show_sale_date = models.BooleanField(default=True)
    show_sale_time = models.BooleanField(default=True)
    show_agent_user = models.BooleanField(default=True)
    
    # Buyer Information Toggles
    show_buyer_name = models.BooleanField(default=True)
    show_buyer_phone = models.BooleanField(default=True)
    show_buyer_id = models.BooleanField(default=True)
    show_next_of_kin_name = models.BooleanField(default=True)
    show_next_of_kin_phone = models.BooleanField(default=True)
    
    # Line Items Toggles
    show_items_table = models.BooleanField(default=True)
    show_imei = models.BooleanField(default=True)
    show_quantity = models.BooleanField(default=True)
    show_unit_price = models.BooleanField(default=True)
    show_line_total = models.BooleanField(default=True)
    show_gross_total = models.BooleanField(default=True)
    
    # Footer
    show_footer_message = models.BooleanField(default=True)
    footer_text = models.CharField(max_length=500, blank=True, default='Thank you for your business!')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Receipt Setting'
        verbose_name_plural = 'Receipt Settings'
        indexes = [
            models.Index(fields=['tenant']),
        ]
    
    def __str__(self):
        return f"Receipt settings for {self.tenant.company_name}"
    
    def save(self, *args, **kwargs):
        """Save receipt settings and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='ReceiptSetting',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'tenant_id': tenant_id,
                        'business_name': self.business_name,
                        'business_address': self.business_address,
                        'business_phone': self.business_phone,
                        'business_email': self.business_email,
                        'business_tax_pin': self.business_tax_pin,
                        'show_business_name': self.show_business_name,
                        'show_address': self.show_address,
                        'show_phone': self.show_phone,
                        'show_email': self.show_email,
                        'show_tax_pin': self.show_tax_pin,
                        'show_receipt_number': self.show_receipt_number,
                        'show_sale_date': self.show_sale_date,
                        'show_sale_time': self.show_sale_time,
                        'show_agent_user': self.show_agent_user,
                        'show_buyer_name': self.show_buyer_name,
                        'show_buyer_phone': self.show_buyer_phone,
                        'show_buyer_id': self.show_buyer_id,
                        'show_next_of_kin_name': self.show_next_of_kin_name,
                        'show_next_of_kin_phone': self.show_next_of_kin_phone,
                        'show_items_table': self.show_items_table,
                        'show_imei': self.show_imei,
                        'show_quantity': self.show_quantity,
                        'show_unit_price': self.show_unit_price,
                        'show_line_total': self.show_line_total,
                        'show_gross_total': self.show_gross_total,
                        'show_footer_message': self.show_footer_message,
                        'footer_text': self.footer_text,
                    }
                )
                logger.debug(f"✅ Queued ReceiptSetting sync for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Failed to queue ReceiptSetting sync: {e}")


class ProfileSetting(models.Model):
    """User profile settings"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile_settings'
    )
    
    theme = models.CharField(max_length=20, default='light', choices=[
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto'),
    ])
    
    language = models.CharField(max_length=10, default='en', choices=[
        ('en', 'English'),
        ('sw', 'Swahili'),
    ])
    
    currency = models.CharField(max_length=10, default='KES')
    date_format = models.CharField(max_length=20, default='Y-m-d')
    time_format = models.CharField(max_length=20, default='H:i')
    
    notifications_enabled = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    notify_on_sale = models.BooleanField(default=True)
    notify_on_stock = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Profile Setting'
        verbose_name_plural = 'Profile Settings'
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Profile Settings - {self.user.username}"
    
    def save(self, *args, **kwargs):
        """Save profile settings and queue for sync"""
        is_new = self.pk is None
        user_id = self.user_id
        tenant_id = self.user.tenant_id if self.user and self.user.tenant_id else None
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync (only if user has a tenant)
        if getattr(settings, 'OFFLINE_MODE', False) and tenant_id:
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='ProfileSetting',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'user_id': user_id,
                        'theme': self.theme,
                        'language': self.language,
                        'currency': self.currency,
                        'date_format': self.date_format,
                        'time_format': self.time_format,
                        'notifications_enabled': self.notifications_enabled,
                        'email_notifications': self.email_notifications,
                        'sms_notifications': self.sms_notifications,
                        'push_notifications': self.push_notifications,
                        'notify_on_sale': self.notify_on_sale,
                        'notify_on_stock': self.notify_on_stock,
                        'tenant_id': tenant_id,
                    }
                )
                logger.debug(f"✅ Queued ProfileSetting sync for user {self.user.username}")
            except Exception as e:
                logger.error(f"Failed to queue ProfileSetting sync: {e}")