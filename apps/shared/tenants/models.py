# apps/shared/tenants/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.files.storage import default_storage
from decimal import Decimal
import logging


logger = logging.getLogger(__name__)


class ProjectType(models.Model):
    """Project Types - Synced from settings.PROJECT_TYPES"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, default='fa-building')
    color = models.CharField(max_length=20, default='primary')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']
    
    @classmethod
    def sync_from_settings(cls):
        """Sync project types from settings.py to database"""
        project_types = getattr(settings, 'PROJECT_TYPES', {})
        created_count = 0
        updated_count = 0
        
        for code, data in project_types.items():
            obj, created = cls.objects.update_or_create(
                code=code.upper(),
                defaults={
                    'name': data.get('name', code),
                    'description': data.get('description', ''),
                    'icon': data.get('icon', 'fa-building'),
                    'color': data.get('color', 'primary'),
                    'is_active': data.get('active', True),
                }
            )
            if created:
                created_count += 1
                print(f"  ✅ Created project type: {obj.name} ({obj.code})")
            else:
                updated_count += 1
        
        return {'created': created_count, 'updated': updated_count}
    
    @classmethod
    def ensure_default_types(cls):
        """Ensure all default project types exist"""
        return cls.sync_from_settings()


class Tenant(models.Model):
    """Tenant - Multi-tenant core model"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('pending', 'Pending Approval'),
        ('expired', 'Expired'),
    ]
    
    # Basic Info
    company_name = models.CharField(max_length=200)
    company_address = models.TextField(blank=True)
    company_phone = models.CharField(max_length=20, blank=True)
    company_email = models.EmailField(blank=True)
    company_pin = models.CharField(max_length=50, blank=True)
    
    # Company Logo
    logo = models.ImageField(
        upload_to='tenant_logos/',
        blank=True,
        null=True,
        help_text="Upload company logo (PNG, JPG, JPEG - Max 5MB)"
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_tenants'
    )

    # Project Type - ForeignKey to ProjectType model
    project_type = models.ForeignKey(
        ProjectType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='tenants'
    )
    
    # Identification
    code = models.CharField(max_length=50, unique=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    till_number = models.CharField(max_length=50, blank=True, null=True)
    paybill_number = models.CharField(max_length=50, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    show_till_number = models.BooleanField(default=True)
    show_paybill = models.BooleanField(default=True)
    show_account_number = models.BooleanField(default=True)


    # ✅ SUBSCRIPTION FIELDS
    subscription_plan = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Code of the current subscription plan"
    )
    subscription_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start date of current subscription"
    )
    subscription_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End date of current subscription"
    )
    auto_renew = models.BooleanField(
        default=False,
        help_text="Automatically renew subscription"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status']),
        ]

    
    def __str__(self):
        return self.company_name


    def get_logo_url(self):
        """Get logo URL only if the file exists"""
        if not self.logo:
            return None
        # Check if file actually exists in storage
        try:
            if self.logo.name and default_storage.exists(self.logo.name):
                return self.logo.url
        except Exception:
            pass
        return None
    
    def has_valid_logo(self):
        """Check if tenant has a valid logo file"""
        if not self.logo:
            return False
        try:
            if self.logo.name:
                return default_storage.exists(self.logo.name)
            return False
        except Exception:
            return False
    
    def save(self, *args, **kwargs):
        """Auto-generate code if not provided, and validate logo"""
        is_new = self.pk is None
        tenant_id = self.id if self.pk else None
        
        if not self.code:
            self.code = self.company_name.upper().replace(' ', '_')[:50]
        
        # Check if logo file exists, if not clear it
        if self.logo and not self.has_valid_logo():
            self.logo = None
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=self.id,
                    model_name='Tenant',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'company_name': self.company_name,
                        'company_address': self.company_address,
                        'company_phone': self.company_phone,
                        'company_email': self.company_email,
                        'company_pin': self.company_pin,
                        'code': self.code,
                        'status': self.status,
                        'project_type_id': self.project_type_id if self.project_type_id else None,
                        'owner_id': self.owner_id if self.owner_id else None,
                        'subscription_plan': self.subscription_plan,
                        'subscription_start': self.subscription_start.isoformat() if self.subscription_start else None,
                        'subscription_end': self.subscription_end.isoformat() if self.subscription_end else None,
                        'auto_renew': self.auto_renew,
                        'is_active': self.status == 'active',
                    }
                )
                logger.debug(f"✅ Queued Tenant sync: {self.company_name}")
            except Exception as e:
                logger.error(f"Failed to queue Tenant sync: {e}")

    # ============================================
    # ✅ SUBSCRIPTION PROPERTIES
    # ============================================
    
    @property
    def is_subscription_active(self):
        """Check if subscription is currently active"""
        if not self.subscription_end:
            return False
        return timezone.now() < self.subscription_end
    
    @property
    def days_remaining(self):
        """Get days remaining in subscription"""
        if not self.subscription_end:
            return 0
        if timezone.now() > self.subscription_end:
            return 0
        delta = self.subscription_end - timezone.now()
        return delta.days
    
    @property
    def subscription_status(self):
        """Get subscription status text"""
        if not self.subscription_end:
            return 'No Subscription'
        if self.is_subscription_active:
            if self.days_remaining <= 7:
                return 'Expiring Soon'
            return 'Active'
        return 'Expired'
    
    def get_subscription_plan(self):
        """Get the subscription plan object"""
        if not self.subscription_plan:
            return None
        try:
            return SubscriptionPlan.objects.get(code=self.subscription_plan)
        except SubscriptionPlan.DoesNotExist:
            return None


# ============================================
# SUBSCRIPTION PLAN MODEL
# ============================================

class SubscriptionPlan(models.Model):
    """Available subscription plans - Managed by Super Admin"""
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=20, unique=True)
    # ✅ FIXED DecimalField defaults
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    
    # Limits
    max_users = models.IntegerField(default=5)
    max_products = models.IntegerField(default=100)
    max_branches = models.IntegerField(default=1)
    max_storage_gb = models.IntegerField(default=1)
    max_rooms = models.IntegerField(default=20, help_text="Maximum rooms for Hotel Master")
    
    # Features as JSON
    features = models.JSONField(default=dict)
    
    # Display
    icon = models.CharField(max_length=50, default='fa-building')
    color = models.CharField(max_length=20, default='primary')
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    # Description
    description = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'price_monthly']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - ${self.price_monthly}/month"
    
    def save(self, *args, **kwargs):
        """Save subscription plan and queue for sync"""
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=None,  # System-wide
                    model_name='SubscriptionPlan',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'name': self.name,
                        'code': self.code,
                        'price_monthly': str(self.price_monthly),
                        'price_yearly': str(self.price_yearly),
                        'max_users': self.max_users,
                        'max_products': self.max_products,
                        'max_branches': self.max_branches,
                        'max_storage_gb': self.max_storage_gb,
                        'features': self.features,
                        'icon': self.icon,
                        'color': self.color,
                        'is_active': self.is_active,
                        'order': self.order,
                        'description': self.description,
                    }
                )
                logger.debug(f"✅ Queued SubscriptionPlan sync: {self.name}")
            except Exception as e:
                logger.error(f"Failed to queue SubscriptionPlan sync: {e}")

    # ✅ Add helper methods
    def get_active_tenant_count(self):
        """Get count of active tenants using this plan"""
        from .models import Tenant  # Import here to avoid circular imports
        return Tenant.objects.filter(
            subscription_plan=self.code,
            status='active'
        ).count()
    
    def get_monthly_revenue(self):
        """Calculate monthly revenue from active tenants"""
        return self.get_active_tenant_count() * self.price_monthly
    
    def get_tenants(self):
        """Get all tenants using this plan"""
        from .models import Tenant
        return Tenant.objects.filter(subscription_plan=self.code)
    
    def has_active_tenants(self):
        """Check if this plan has any active tenants"""
        return self.get_active_tenant_count() > 0
    
    def can_delete(self):
        """Check if plan can be deleted (no active tenants)"""
        return not self.has_active_tenants()

# ============================================
# SUBSCRIPTION INVOICE MODEL
# ============================================

class SubscriptionInvoice(models.Model):
    """Subscription invoices for tenants"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHODS = [
        ('card', 'Credit Card'),
        ('mpesa', 'M-Pesa'),
        ('bank', 'Bank Transfer'),
        ('paypal', 'PayPal'),
    ]
    
    tenant = models.ForeignKey(
        'Tenant',
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    
    invoice_number = models.CharField(max_length=50, unique=True)
    
    # Plan details
    plan = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    
    # Period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Payment
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, blank=True, null=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=200, blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.tenant.company_name}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            import random
            import datetime
            year = datetime.datetime.now().year
            random_num = random.randint(10000, 99999)
            self.invoice_number = f"INV-{year}-{random_num}"
        
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='SubscriptionInvoice',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'tenant_id': tenant_id,
                        'invoice_number': self.invoice_number,
                        'plan': self.plan,
                        'amount': str(self.amount),
                        'period_start': self.period_start.isoformat() if self.period_start else None,
                        'period_end': self.period_end.isoformat() if self.period_end else None,
                        'payment_method': self.payment_method,
                        'payment_date': self.payment_date.isoformat() if self.payment_date else None,
                        'transaction_id': self.transaction_id,
                        'status': self.status,
                    }
                )
                logger.debug(f"✅ Queued SubscriptionInvoice sync: {self.invoice_number}")
            except Exception as e:
                logger.error(f"Failed to queue SubscriptionInvoice sync: {e}")


# ============================================
# OFFLINE SYNC MODELS
# ============================================

class SyncQueue(models.Model):
    """Queue for offline operations - Enhanced for maintenance"""
    
    OPERATION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('TRANSFER', 'Branch Transfer'),
        ('SALE', 'Sale'),
        ('RETURN', 'Return'),
        ('ADJUSTMENT', 'Stock Adjustment'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Sync'),
        ('SYNCING', 'Sync in Progress'),
        ('SYNCED', 'Synced Successfully'),
        ('FAILED', 'Sync Failed'),
        ('CONFLICT', 'Conflict Detected'),
    ]
    
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='sync_queue')
    model_name = models.CharField(max_length=100)  # e.g., 'Product', 'ProductUnit', 'StockEntry'
    object_id = models.CharField(max_length=50)  # Can store string IDs for UUIDs
    operation = models.CharField(max_length=20, choices=OPERATION_CHOICES)
    data = models.JSONField(default=dict)  # Full object data for sync
    previous_data = models.JSONField(null=True, blank=True)  # For conflict resolution
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=5)
    last_attempt = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # For conflict resolution
    conflict_resolved = models.BooleanField(default=False)
    resolved_data = models.JSONField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_sync_entries'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Priority for sync (1-10, higher = more urgent)
    priority = models.PositiveSmallIntegerField(default=5)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['tenant', 'priority']),
        ]
        verbose_name = 'Sync Queue Entry'
        verbose_name_plural = 'Sync Queue Entries'
    
    def __str__(self):
        return f"{self.get_operation_display()} {self.model_name} #{self.object_id}"
    
    def mark_synced(self):
        """Mark as successfully synced"""
        self.status = 'SYNCED'
        self.last_attempt = timezone.now()
        self.save()
        
    def mark_failed(self, error):
        """Mark as failed and increment retry count"""
        self.status = 'FAILED'
        self.retry_count += 1
        self.last_attempt = timezone.now()
        self.error_message = str(error)
        self.save()
        
    def mark_conflict(self, previous_data):
        """Mark as conflict for manual resolution"""
        self.status = 'CONFLICT'
        self.previous_data = previous_data
        self.save()
    
    def retry(self):
        """Reset status for retry"""
        if self.retry_count < self.max_retries:
            self.status = 'PENDING'
            self.save()
            return True
        return False


class OfflineCache(models.Model):
    """Cache for offline data"""
    
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE, related_name='offline_cache')
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.IntegerField(db_index=True)
    data = models.JSONField(default=dict)
    last_synced = models.DateTimeField(auto_now_add=True, db_index=True)
    version = models.IntegerField(default=1)
    
    class Meta:
        ordering = ['-last_synced']
        indexes = [
            models.Index(fields=['tenant', 'model_name']),
            models.Index(fields=['last_synced']),
        ]
        unique_together = ['tenant', 'model_name', 'object_id']
        verbose_name = "Offline Cache"
        verbose_name_plural = "Offline Caches"
    
    def __str__(self):
        return f"{self.model_name} #{self.object_id} - {self.tenant.company_name}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'tenant_name': self.tenant.company_name if self.tenant else None,
            'model_name': self.model_name,
            'object_id': self.object_id,
            'data': self.data,
            'last_synced': self.last_synced.isoformat() if self.last_synced else None,
            'version': self.version,
        }