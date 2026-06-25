# apps/shared/payments/models.py

from django.db import models
from django.conf import settings
from decimal import Decimal
import logging

from apps.shared.tenants.models import Tenant
from apps.shared.customers.models import Customer

# ✅ ADD THIS IMPORT FOR SYNC QUEUE
from apps.shared.tenants.models import SyncQueue

logger = logging.getLogger(__name__)


class PaymentMethod(models.Model):
    """Payment methods available"""
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )
    
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    
    icon = models.CharField(max_length=50, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        unique_together = [['tenant', 'code']]
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def save(self, *args, **kwargs):
        """Save payment method and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='PaymentMethod',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'tenant_id': tenant_id,
                        'name': self.name,
                        'code': self.code,
                        'description': self.description,
                        'is_active': self.is_active,
                        'is_available': self.is_available,
                        'icon': self.icon,
                    }
                )
                logger.debug(f"✅ Queued PaymentMethod sync: {self.name}")
            except Exception as e:
                logger.error(f"Failed to queue PaymentMethod sync: {e}")


class Payment(models.Model):
    """Payment transactions"""
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile', 'Mobile Money'),
        ('bank', 'Bank Transfer'),
        ('mpesa', 'M-Pesa'),
    ]
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_payments'
    )
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    reference = models.CharField(max_length=50, unique=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    
    sale_id = models.CharField(max_length=50, blank=True, null=True)
    invoice_number = models.CharField(max_length=50, blank=True, null=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    payment_date = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status']),
            models.Index(fields=['tenant', 'payment_date']),
            models.Index(fields=['tenant', 'status']),
        ]
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
    
    def __str__(self):
        return f"Payment {self.reference} - {self.amount}"
    
    def save(self, *args, **kwargs):
        """Save payment and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        if not self.reference:
            self.reference = self.generate_reference()
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='Payment',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'tenant_id': tenant_id,
                        'customer_id': self.customer_id if self.customer_id else None,
                        'user_id': self.user_id if self.user_id else None,
                        'amount': str(self.amount),
                        'payment_method': self.payment_method,
                        'status': self.status,
                        'reference': self.reference,
                        'transaction_id': self.transaction_id,
                        'sale_id': self.sale_id,
                        'invoice_number': self.invoice_number,
                        'metadata': self.metadata,
                        'payment_date': self.payment_date.isoformat() if self.payment_date else None,
                        'completed_at': self.completed_at.isoformat() if self.completed_at else None,
                    }
                )
                logger.debug(f"✅ Queued Payment sync: {self.reference}")
            except Exception as e:
                logger.error(f"Failed to queue Payment sync: {e}")
    
    @classmethod
    def generate_reference(cls):
        import random
        import string
        import datetime
        date_str = datetime.datetime.now().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.digits, k=6))
        return f"PAY-{date_str}-{random_str}"
    
    def mark_completed(self):
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self):
        self.status = 'failed'
        self.save()
    
    def mark_refunded(self):
        self.status = 'refunded'
        self.save()
    
    def process_payment(self):
        """Process the payment"""
        self.mark_completed()
        return True


class Refund(models.Model):
    """Payment refunds"""
    
    REFUND_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='refunds'
    )
    
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_refunds'
    )
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=REFUND_STATUS, default='pending')
    
    refund_reference = models.CharField(max_length=50, unique=True, blank=True)
    
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['refund_reference']),
            models.Index(fields=['status']),
            models.Index(fields=['payment', 'status']),
            models.Index(fields=['requested_at']),
        ]
        verbose_name = 'Refund'
        verbose_name_plural = 'Refunds'
    
    def __str__(self):
        return f"Refund {self.refund_reference} - {self.amount}"
    
    def save(self, *args, **kwargs):
        """Save refund and queue for sync"""
        is_new = self.pk is None
        
        if not self.refund_reference:
            import random
            import string
            import datetime
            date_str = datetime.datetime.now().strftime('%Y%m%d')
            random_str = ''.join(random.choices(string.digits, k=6))
            self.refund_reference = f"REF-{date_str}-{random_str}"
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                # Get tenant_id from the payment
                tenant_id = self.payment.tenant_id if self.payment else None
                
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='Refund',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'payment_id': self.payment_id,
                        'processed_by_id': self.processed_by_id if self.processed_by_id else None,
                        'amount': str(self.amount),
                        'reason': self.reason,
                        'status': self.status,
                        'refund_reference': self.refund_reference,
                        'requested_at': self.requested_at.isoformat() if self.requested_at else None,
                        'processed_at': self.processed_at.isoformat() if self.processed_at else None,
                        'tenant_id': tenant_id,
                    }
                )
                logger.debug(f"✅ Queued Refund sync: {self.refund_reference}")
            except Exception as e:
                logger.error(f"Failed to queue Refund sync: {e}")
    
    def approve(self, user):
        from django.utils import timezone
        self.status = 'approved'
        self.processed_by = user
        self.processed_at = timezone.now()
        self.save()
        self.payment.mark_refunded()
    
    def reject(self, user):
        from django.utils import timezone
        self.status = 'rejected'
        self.processed_by = user
        self.processed_at = timezone.now()
        self.save()
    
    def complete(self):
        from django.utils import timezone
        self.status = 'completed'
        self.processed_at = timezone.now()
        self.save()