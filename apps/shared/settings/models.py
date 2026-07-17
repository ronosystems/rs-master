# apps/shared/tenants/models.py

from django.db import models
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.cache import cache
import logging
from decimal import Decimal
from apps.shared.tenants.models import Tenant
from apps.shared.tenants.models import SyncQueue
from django.core.signing import Signer, BadSignature

logger = logging.getLogger(__name__)



class CompanySetting(models.Model):
    """Company/Business Settings per tenant"""
    tenant = models.OneToOneField(
        Tenant, 
        on_delete=models.CASCADE, 
        related_name='company_settings'
    )
    
    # Company Details
    company_name = models.CharField(max_length=200, blank=True, default='')
    company_address = models.TextField(blank=True, default='')
    company_phone = models.CharField(max_length=20, blank=True, default='')
    company_email = models.EmailField(blank=True, default='')
    company_website = models.URLField(blank=True, default='')
    company_tax_pin = models.CharField(max_length=50, blank=True, default='')
    
    # Logo
    logo = models.ImageField(
        upload_to='company_logos/',
        blank=True,
        null=True,
        help_text="Upload company logo (PNG, JPG, JPEG - Max 5MB)"
    )
    
    # Favicon
    favicon = models.ImageField(
        upload_to='favicons/',
        blank=True,
        null=True,
        help_text="Upload favicon (ICO, PNG - Max 1MB)"
    )
    
    # ============================================
    # SLIDESHOW IMAGES - NEW
    # ============================================
    slide_image_1 = models.ImageField(
        upload_to='company_slides/',
        blank=True,
        null=True,
        help_text="Slide 1 - Upload image (recommended: 1920x1080)"
    )
    slide_title_1 = models.CharField(max_length=200, blank=True, default='', help_text="Title for slide 1")
    slide_subtitle_1 = models.CharField(max_length=300, blank=True, default='', help_text="Subtitle for slide 1")
    slide_button_text_1 = models.CharField(max_length=50, blank=True, default='', help_text="Button text for slide 1")
    slide_button_url_1 = models.CharField(max_length=200, blank=True, default='', help_text="Button URL for slide 1")
    
    slide_image_2 = models.ImageField(
        upload_to='company_slides/',
        blank=True,
        null=True,
        help_text="Slide 2 - Upload image (recommended: 1920x1080)"
    )
    slide_title_2 = models.CharField(max_length=200, blank=True, default='', help_text="Title for slide 2")
    slide_subtitle_2 = models.CharField(max_length=300, blank=True, default='', help_text="Subtitle for slide 2")
    slide_button_text_2 = models.CharField(max_length=50, blank=True, default='', help_text="Button text for slide 2")
    slide_button_url_2 = models.CharField(max_length=200, blank=True, default='', help_text="Button URL for slide 2")
    
    slide_image_3 = models.ImageField(
        upload_to='company_slides/',
        blank=True,
        null=True,
        help_text="Slide 3 - Upload image (recommended: 1920x1080)"
    )
    slide_title_3 = models.CharField(max_length=200, blank=True, default='', help_text="Title for slide 3")
    slide_subtitle_3 = models.CharField(max_length=300, blank=True, default='', help_text="Subtitle for slide 3")
    slide_button_text_3 = models.CharField(max_length=50, blank=True, default='', help_text="Button text for slide 3")
    slide_button_url_3 = models.CharField(max_length=200, blank=True, default='', help_text="Button URL for slide 3")
    
    slide_image_4 = models.ImageField(
        upload_to='company_slides/',
        blank=True,
        null=True,
        help_text="Slide 4 - Upload image (recommended: 1920x1080)"
    )
    slide_title_4 = models.CharField(max_length=200, blank=True, default='', help_text="Title for slide 4")
    slide_subtitle_4 = models.CharField(max_length=300, blank=True, default='', help_text="Subtitle for slide 4")
    slide_button_text_4 = models.CharField(max_length=50, blank=True, default='', help_text="Button text for slide 4")
    slide_button_url_4 = models.CharField(max_length=200, blank=True, default='', help_text="Button URL for slide 4")
    
    slide_image_5 = models.ImageField(
        upload_to='company_slides/',
        blank=True,
        null=True,
        help_text="Slide 5 - Upload image (recommended: 1920x1080)"
    )
    slide_title_5 = models.CharField(max_length=200, blank=True, default='', help_text="Title for slide 5")
    slide_subtitle_5 = models.CharField(max_length=300, blank=True, default='', help_text="Subtitle for slide 5")
    slide_button_text_5 = models.CharField(max_length=50, blank=True, default='', help_text="Button text for slide 5")
    slide_button_url_5 = models.CharField(max_length=200, blank=True, default='', help_text="Button URL for slide 5")
    
    # Slide Settings
    enable_slideshow = models.BooleanField(default=True, help_text="Enable slideshow on dashboard")
    slideshow_interval = models.IntegerField(default=5000, help_text="Slideshow interval in milliseconds (e.g., 5000 = 5 seconds)")
    
    # Branding Colors
    primary_color = models.CharField(
        max_length=20, 
        default='#0d6efd', 
        help_text="Primary brand color (e.g., #0d6efd)"
    )
    secondary_color = models.CharField(
        max_length=20, 
        default='#6c757d', 
        help_text="Secondary brand color (e.g., #6c757d)"
    )
    accent_color = models.CharField(
        max_length=20, 
        default='#ffc107', 
        help_text="Accent brand color (e.g., #ffc107)"
    )
    
    # Display Settings
    show_logo_on_receipts = models.BooleanField(default=True)
    show_logo_on_invoices = models.BooleanField(default=True)
    show_logo_on_reports = models.BooleanField(default=True)
    show_logo_on_dashboard = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Company Setting'
        verbose_name_plural = 'Company Settings'
        indexes = [
            models.Index(fields=['tenant']),
        ]
    
    def __str__(self):
        return f"Company Settings - {self.tenant.company_name if self.tenant else 'No Tenant'}"
    
    def get_slides(self):
        """Get list of slides with images and content"""
        slides = []
        slide_fields = [
            (1, 'slide_image_1', 'slide_title_1', 'slide_subtitle_1', 'slide_button_text_1', 'slide_button_url_1'),
            (2, 'slide_image_2', 'slide_title_2', 'slide_subtitle_2', 'slide_button_text_2', 'slide_button_url_2'),
            (3, 'slide_image_3', 'slide_title_3', 'slide_subtitle_3', 'slide_button_text_3', 'slide_button_url_3'),
            (4, 'slide_image_4', 'slide_title_4', 'slide_subtitle_4', 'slide_button_text_4', 'slide_button_url_4'),
            (5, 'slide_image_5', 'slide_title_5', 'slide_subtitle_5', 'slide_button_text_5', 'slide_button_url_5'),
        ]
        
        for num, img_field, title_field, subtitle_field, btn_text_field, btn_url_field in slide_fields:
            img = getattr(self, img_field)
            if img and img.name:
                slides.append({
                    'order': num,
                    'image': img,
                    'image_url': img.url if img else None,
                    'title': getattr(self, title_field, ''),
                    'subtitle': getattr(self, subtitle_field, ''),
                    'button_text': getattr(self, btn_text_field, ''),
                    'button_url': getattr(self, btn_url_field, ''),
                })
        
        return slides
    
    def get_active_slides(self):
        """Get only active slides with images"""
        return [s for s in self.get_slides() if s['image']]
    
    def get_logo_url(self):
        """Get logo URL if it exists"""
        if not self.logo:
            return None
        try:
            if self.logo.name and default_storage.exists(self.logo.name):
                return self.logo.url
        except Exception:
            pass
        return None
    
    def has_valid_logo(self):
        """Check if logo file exists"""
        if not self.logo:
            return False
        try:
            if self.logo.name:
                return default_storage.exists(self.logo.name)
            return False
        except Exception:
            return False
    
    def get_favicon_url(self):
        """Get favicon URL if it exists"""
        if not self.favicon:
            return None
        try:
            if self.favicon.name and default_storage.exists(self.favicon.name):
                return self.favicon.url
        except Exception:
            pass
        return None
    
    def save(self, *args, **kwargs):
        """Save company settings and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        # Clean up old logo file if replaced
        if self.pk:
            try:
                old = CompanySetting.objects.get(pk=self.pk)
                if old.logo and old.logo != self.logo:
                    old.logo.delete(save=False)
                if old.favicon and old.favicon != self.favicon:
                    old.favicon.delete(save=False)
                # Clean up old slide images
                for i in range(1, 6):
                    old_field = getattr(old, f'slide_image_{i}')
                    new_field = getattr(self, f'slide_image_{i}')
                    if old_field and old_field != new_field:
                        old_field.delete(save=False)
            except CompanySetting.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # ✅ Clear settings cache for this tenant
        if tenant_id:
            cache.delete(f"settings_{tenant_id}_global")
            cache.delete(f"settings_{tenant_id}_None_global")
        
        # If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                sync_data = {
                    'id': self.id,
                    'tenant_id': tenant_id,
                    'company_name': self.company_name,
                    'company_address': self.company_address,
                    'company_phone': self.company_phone,
                    'company_email': self.company_email,
                    'company_website': self.company_website,
                    'company_tax_pin': self.company_tax_pin,
                    'logo': self.logo.name if self.logo else None,
                    'favicon': self.favicon.name if self.favicon else None,
                    'primary_color': self.primary_color,
                    'secondary_color': self.secondary_color,
                    'accent_color': self.accent_color,
                    'show_logo_on_receipts': self.show_logo_on_receipts,
                    'show_logo_on_invoices': self.show_logo_on_invoices,
                    'show_logo_on_reports': self.show_logo_on_reports,
                    'show_logo_on_dashboard': self.show_logo_on_dashboard,
                    'enable_slideshow': self.enable_slideshow,
                    'slideshow_interval': self.slideshow_interval,
                }
                # Add slide data
                for i in range(1, 6):
                    img = getattr(self, f'slide_image_{i}')
                    sync_data[f'slide_image_{i}'] = img.name if img else None
                    sync_data[f'slide_title_{i}'] = getattr(self, f'slide_title_{i}', '')
                    sync_data[f'slide_subtitle_{i}'] = getattr(self, f'slide_subtitle_{i}', '')
                    sync_data[f'slide_button_text_{i}'] = getattr(self, f'slide_button_text_{i}', '')
                    sync_data[f'slide_button_url_{i}'] = getattr(self, f'slide_button_url_{i}', '')
                
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='CompanySetting',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data=sync_data
                )
                logger.debug(f"✅ Queued CompanySetting sync for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Failed to queue CompanySetting sync: {e}")


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
        
        # ✅ Clear system settings cache
        cache.delete("settings_system_global")
        
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
    
    # ============================================
    # ADD LOGO FIELD HERE
    # ============================================
    logo = models.ImageField(
        upload_to='receipt_logos/',
        blank=True,
        null=True,
        help_text="Upload company logo for receipts (PNG, JPG, JPEG - Max 5MB)"
    )
    
    # Business Header Toggles
    show_business_name = models.BooleanField(default=True)
    show_address = models.BooleanField(default=True)
    show_phone = models.BooleanField(default=True)
    show_email = models.BooleanField(default=True)
    show_tax_pin = models.BooleanField(default=True)
    
    # ============================================
    # ADD LOGO TOGGLE
    # ============================================
    show_logo_on_receipts = models.BooleanField(default=True)
    
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

    # ============================================
    # VAT / TAX SETTINGS - NEW
    # ============================================
    show_vat_on_receipt = models.BooleanField(default=False, help_text="Show VAT/Tax breakdown on receipt")
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('16.00'), help_text="VAT/Tax rate percentage")
    vat_label = models.CharField(max_length=20, default='VAT', help_text="Label for tax (e.g., VAT, GST, TAX)")
    tax_type = models.CharField(
        max_length=20,
        default='exclusive',
        choices=[
            ('exclusive', 'Before Tax (Add VAT)'),
            ('inclusive', 'After Tax (VAT Included)'),
        ],
        help_text="Whether VAT is added to price or included in price"
    )

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
    
    def get_logo_url(self):
        """Get logo URL if it exists"""
        if not self.logo:
            return None
        try:
            if self.logo.name and default_storage.exists(self.logo.name):
                return self.logo.url
        except Exception:
            pass
        return None
    
    def has_valid_logo(self):
        """Check if logo file exists"""
        if not self.logo:
            return False
        try:
            if self.logo.name:
                return default_storage.exists(self.logo.name)
            return False
        except Exception:
            return False
    
    def save(self, *args, **kwargs):
        """Save receipt settings and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        # Clean up old logo file if replaced
        if self.pk:
            try:
                old = ReceiptSetting.objects.get(pk=self.pk)
                if old.logo and old.logo != self.logo:
                    old.logo.delete(save=False)
            except ReceiptSetting.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # ✅ Clear settings cache for this tenant
        if tenant_id:
            cache.delete(f"settings_{tenant_id}_global")
            cache.delete(f"settings_{tenant_id}_None_global")
        
        # If offline, queue for sync
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
                        'logo': self.logo.name if self.logo else None,
                        'show_logo_on_receipts': self.show_logo_on_receipts,
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
                        'show_vat_on_receipt': self.show_vat_on_receipt,
                        'vat_rate': self.vat_rate,
                        'vat_label': self.vat_label,
                        'tax_type': self.tax_type,
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
        
        # ✅ Clear settings cache for this tenant and user
        if tenant_id:
            cache.delete(f"settings_{tenant_id}_global")
            cache.delete(f"settings_{tenant_id}_{user_id}_global")
        
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


class HotelSetting(models.Model):
    """Hotel Settings Model"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='hotel_settings')
    
    # Hotel Details
    hotel_name = models.CharField(max_length=255, blank=True, help_text="Hotel/Property Name")
    hotel_address = models.TextField(blank=True, help_text="Hotel Address")
    hotel_phone = models.CharField(max_length=50, blank=True, help_text="Contact Phone Number")
    hotel_email = models.EmailField(blank=True, help_text="Contact Email")
    hotel_website = models.URLField(blank=True, help_text="Hotel Website URL")
    hotel_description = models.TextField(blank=True, help_text="Hotel Description")
    
    # Check-in / Check-out Times
    check_in_time = models.CharField(max_length=10, default='14:00', help_text="Check-in Time (e.g., 14:00)")
    check_out_time = models.CharField(max_length=10, default='11:00', help_text="Check-out Time (e.g., 11:00)")
    
    # Policies
    cancellation_policy = models.TextField(blank=True, help_text="Cancellation Policy")
    early_checkin_policy = models.TextField(blank=True, help_text="Early Check-in Policy")
    late_checkout_policy = models.TextField(blank=True, help_text="Late Check-out Policy")
    payment_policy = models.TextField(blank=True, help_text="Payment Policy")
    
    # Financial Settings
    currency = models.CharField(max_length=10, default='KES', help_text="Default Currency")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Tax Rate (%)")
    service_charge = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Service Charge (%)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Hotel Settings - {self.tenant.company_name if self.tenant else 'No Tenant'}"
    
    class Meta:
        verbose_name = "Hotel Setting"
        verbose_name_plural = "Hotel Settings"
        unique_together = ['tenant']  # One setting per tenant
    
    def save(self, *args, **kwargs):
        """Save hotel settings and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        super().save(*args, **kwargs)
        
        # ✅ Clear settings cache for this tenant
        if tenant_id:
            cache.delete(f"settings_{tenant_id}_global")
            cache.delete(f"settings_{tenant_id}_None_global")
        
        # If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='HotelSetting',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'tenant_id': tenant_id,
                        'hotel_name': self.hotel_name,
                        'hotel_address': self.hotel_address,
                        'hotel_phone': self.hotel_phone,
                        'hotel_email': self.hotel_email,
                        'hotel_website': self.hotel_website,
                        'hotel_description': self.hotel_description,
                        'check_in_time': self.check_in_time,
                        'check_out_time': self.check_out_time,
                        'cancellation_policy': self.cancellation_policy,
                        'early_checkin_policy': self.early_checkin_policy,
                        'late_checkout_policy': self.late_checkout_policy,
                        'payment_policy': self.payment_policy,
                        'currency': self.currency,
                        'tax_rate': str(self.tax_rate),
                        'service_charge': str(self.service_charge),
                    }
                )
                logger.debug(f"✅ Queued HotelSetting sync for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Failed to queue HotelSetting sync: {e}")


class PaymentSetting(models.Model):
    """Payment settings per tenant"""
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='payment_settings')
    
    # ============================================
    # RECEIPT PAYMENT DETAILS
    # ============================================
    till_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="Till number for cash payments"
    )
    paybill_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="Paybill number for M-Pesa payments"
    )
    account_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="Account number for M-Pesa paybill"
    )
    show_till_number = models.BooleanField(
        default=True, 
        help_text="Show till number on receipts"
    )
    show_paybill = models.BooleanField(
        default=True, 
        help_text="Show paybill number on receipts"
    )
    show_account_number = models.BooleanField(
        default=True, 
        help_text="Show account number on receipts"
    )
    show_payment_details_on_receipt = models.BooleanField(
        default=True, 
        help_text="Show payment details on receipt"
    )
    
    # Payment Methods Toggles
    enable_cash = models.BooleanField(default=True)
    enable_mpesa = models.BooleanField(default=True)
    enable_card = models.BooleanField(default=False)
    enable_bank_transfer = models.BooleanField(default=False)
    enable_credit = models.BooleanField(default=False)  # Buy now, pay later
    
    # M-Pesa Settings
    mpesa_shortcode = models.CharField(max_length=50, blank=True, default='')
    mpesa_consumer_key = models.CharField(max_length=200, blank=True, default='')
    mpesa_consumer_secret = models.CharField(max_length=200, blank=True, default='')
    mpesa_passkey = models.CharField(max_length=200, blank=True, default='')
    mpesa_environment = models.CharField(
        max_length=20, 
        default='sandbox',
        choices=[
            ('sandbox', 'Sandbox'),
            ('production', 'Production'),
        ]
    )
    
    # Card Payment Settings
    card_payment_gateway = models.CharField(
        max_length=50,
        blank=True,
        default='',
        choices=[
            ('', 'None'),
            ('stripe', 'Stripe'),
            ('paypal', 'PayPal'),
            ('flutterwave', 'Flutterwave'),
        ]
    )
    card_public_key = models.CharField(max_length=200, blank=True, default='')
    card_secret_key = models.CharField(max_length=200, blank=True, default='')
    card_webhook_secret = models.CharField(max_length=200, blank=True, default='')
    
    # Bank Transfer Settings
    bank_name = models.CharField(max_length=100, blank=True, default='')
    bank_account_name = models.CharField(max_length=200, blank=True, default='')
    bank_account_number = models.CharField(max_length=50, blank=True, default='')
    bank_branch = models.CharField(max_length=100, blank=True, default='')
    bank_swift_code = models.CharField(max_length=20, blank=True, default='')
    
    # Credit Settings
    credit_limit_enabled = models.BooleanField(default=False)
    credit_limit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    credit_days_allowed = models.IntegerField(default=30)  # Days before payment due
    credit_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    credit_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # Payment Validation
    require_payment_confirmation = models.BooleanField(default=True)
    require_payment_receipt = models.BooleanField(default=False)
    send_payment_receipt_email = models.BooleanField(default=True)
    send_payment_receipt_sms = models.BooleanField(default=False)
    
    # Payment Limits
    max_cash_payment = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    min_cash_payment = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    max_mpesa_payment = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    min_mpesa_payment = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Payment Status Options
    enable_partial_payment = models.BooleanField(default=False)
    enable_deposit_payment = models.BooleanField(default=False)
    deposit_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # Currency Settings
    display_currency = models.CharField(max_length=10, default='KES')
    display_currency_symbol = models.CharField(max_length=10, default='KSh')
    currency_position = models.CharField(
        max_length=10,
        default='before',
        choices=[
            ('before', 'Before Amount'),
            ('after', 'After Amount'),
        ]
    )
    decimal_places = models.IntegerField(default=2)
    thousand_separator = models.CharField(max_length=1, default=',')
    decimal_separator = models.CharField(max_length=1, default='.')
    
    # Tax Settings
    enable_tax = models.BooleanField(default=False)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('16.00'))
    tax_inclusive = models.BooleanField(default=True)  # True: Tax included in price, False: Tax added
    tax_label = models.CharField(max_length=50, default='VAT')
    
    # Payment Footer Messages
    payment_footer_text = models.TextField(blank=True, default='')
    show_payment_instructions = models.BooleanField(default=True)
    payment_instructions = models.TextField(blank=True, default='')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Payment Setting'
        verbose_name_plural = 'Payment Settings'
        indexes = [
            models.Index(fields=['tenant']),
        ]
    
    def __str__(self):
        return f"Payment settings for {self.tenant.company_name}"
    
    def save(self, *args, **kwargs):
        """Save payment settings and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        super().save(*args, **kwargs)
        
        # ✅ Clear settings cache for this tenant
        if tenant_id:
            cache.delete(f"settings_{tenant_id}_global")
            cache.delete(f"settings_{tenant_id}_None_global")
        
        # If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='PaymentSetting',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'tenant_id': tenant_id,
                        'enable_cash': self.enable_cash,
                        'enable_mpesa': self.enable_mpesa,
                        'enable_card': self.enable_card,
                        'enable_bank_transfer': self.enable_bank_transfer,
                        'enable_credit': self.enable_credit,
                        'mpesa_shortcode': self.mpesa_shortcode,
                        'mpesa_consumer_key': self.mpesa_consumer_key,
                        'mpesa_consumer_secret': self.mpesa_consumer_secret,
                        'mpesa_passkey': self.mpesa_passkey,
                        'mpesa_environment': self.mpesa_environment,
                        'card_payment_gateway': self.card_payment_gateway,
                        'card_public_key': self.card_public_key,
                        'card_secret_key': self.card_secret_key,
                        'card_webhook_secret': self.card_webhook_secret,
                        'bank_name': self.bank_name,
                        'bank_account_name': self.bank_account_name,
                        'bank_account_number': self.bank_account_number,
                        'bank_branch': self.bank_branch,
                        'bank_swift_code': self.bank_swift_code,
                        'credit_limit_enabled': self.credit_limit_enabled,
                        'credit_limit_amount': str(self.credit_limit_amount),
                        'credit_days_allowed': self.credit_days_allowed,
                        'credit_interest_rate': str(self.credit_interest_rate),
                        'credit_fee_percentage': str(self.credit_fee_percentage),
                        'require_payment_confirmation': self.require_payment_confirmation,
                        'require_payment_receipt': self.require_payment_receipt,
                        'send_payment_receipt_email': self.send_payment_receipt_email,
                        'send_payment_receipt_sms': self.send_payment_receipt_sms,
                        'max_cash_payment': str(self.max_cash_payment) if self.max_cash_payment is not None else None,
                        'min_cash_payment': str(self.min_cash_payment),
                        'max_mpesa_payment': str(self.max_mpesa_payment) if self.max_mpesa_payment is not None else None,
                        'min_mpesa_payment': str(self.min_mpesa_payment),
                        'enable_partial_payment': self.enable_partial_payment,
                        'enable_deposit_payment': self.enable_deposit_payment,
                        'deposit_percentage': str(self.deposit_percentage),
                        'display_currency': self.display_currency,
                        'display_currency_symbol': self.display_currency_symbol,
                        'currency_position': self.currency_position,
                        'decimal_places': self.decimal_places,
                        'thousand_separator': self.thousand_separator,
                        'decimal_separator': self.decimal_separator,
                        'enable_tax': self.enable_tax,
                        'tax_percentage': str(self.tax_percentage),
                        'tax_inclusive': self.tax_inclusive,
                        'tax_label': self.tax_label,
                        'payment_footer_text': self.payment_footer_text,
                        'show_payment_instructions': self.show_payment_instructions,
                        'payment_instructions': self.payment_instructions,
                    }
                )
                logger.debug(f"✅ Queued PaymentSetting sync for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Failed to queue PaymentSetting sync: {e}")
    
    def get_enabled_payment_methods(self):
        """Get list of enabled payment methods"""
        methods = []
        if self.enable_cash:
            methods.append('cash')
        if self.enable_mpesa:
            methods.append('mpesa')
        if self.enable_card:
            methods.append('card')
        if self.enable_bank_transfer:
            methods.append('bank_transfer')
        if self.enable_credit:
            methods.append('credit')
        return methods
    
    def get_payment_method_display(self, method):
        """Get display name for payment method"""
        method_names = {
            'cash': 'Cash',
            'mpesa': 'M-Pesa',
            'card': 'Card Payment',
            'bank_transfer': 'Bank Transfer',
            'credit': 'Credit',
        }
        return method_names.get(method, method.capitalize())
    
    def set_mpesa_consumer_secret(self, value):
        """Securely store M-Pesa consumer secret with signing"""
        signer = Signer()
        self.mpesa_consumer_secret = signer.sign(value)
    
    def get_mpesa_consumer_secret(self):
        """Retrieve and verify M-Pesa consumer secret"""
        if not self.mpesa_consumer_secret:
            return None
        signer = Signer()
        try:
            return signer.unsign(self.mpesa_consumer_secret)
        except BadSignature:
            logger.warning(f"Invalid signature for M-Pesa consumer secret for tenant {self.tenant_id}")
            return None
    
    def set_mpesa_passkey(self, value):
        """Securely store M-Pesa passkey with signing"""
        signer = Signer()
        self.mpesa_passkey = signer.sign(value)
    
    def get_mpesa_passkey(self):
        """Retrieve and verify M-Pesa passkey"""
        if not self.mpesa_passkey:
            return None
        signer = Signer()
        try:
            return signer.unsign(self.mpesa_passkey)
        except BadSignature:
            logger.warning(f"Invalid signature for M-Pesa passkey for tenant {self.tenant_id}")
            return None
    
    def set_card_secret_key(self, value):
        """Securely store card secret key with signing"""
        signer = Signer()
        self.card_secret_key = signer.sign(value)
    
    def get_card_secret_key(self):
        """Retrieve and verify card secret key"""
        if not self.card_secret_key:
            return None
        signer = Signer()
        try:
            return signer.unsign(self.card_secret_key)
        except BadSignature:
            logger.warning(f"Invalid signature for card secret key for tenant {self.tenant_id}")
            return None
    
    def set_card_webhook_secret(self, value):
        """Securely store card webhook secret with signing"""
        signer = Signer()
        self.card_webhook_secret = signer.sign(value)
    
    def get_card_webhook_secret(self):
        """Retrieve and verify card webhook secret"""
        if not self.card_webhook_secret:
            return None
        signer = Signer()
        try:
            return signer.unsign(self.card_webhook_secret)
        except BadSignature:
            logger.warning(f"Invalid signature for card webhook secret for tenant {self.tenant_id}")
            return None