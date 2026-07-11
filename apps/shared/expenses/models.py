# apps/tech_master/expenses/models.py

from django.db import models
from django.conf import settings
from decimal import Decimal
import logging

from apps.shared.tenants.models import Tenant
from apps.shared.users.models import User

# ✅ ADD THIS IMPORT FOR SYNC QUEUE
from apps.shared.tenants.models import SyncQueue

logger = logging.getLogger(__name__)


class ExpenseCategory(models.Model):
    """Expense category (e.g., Rent, Utilities, Salaries)"""
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='expense_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'name']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'name']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Save expense category and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='ExpenseCategory',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'name': self.name,
                        'description': self.description,
                        'is_active': self.is_active,
                        'tenant_id': tenant_id,
                    }
                )
                logger.debug(f"✅ Queued ExpenseCategory sync: {self.name}")
            except Exception as e:
                logger.error(f"Failed to queue ExpenseCategory sync: {e}")


class Expense(models.Model):
    """Expense model for tracking business expenses"""
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('mobile', 'Mobile Money'),
        ('cheque', 'Cheque'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, related_name='expenses')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='expenses')
    
    # Expense details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    # ✅ FIXED DecimalField default
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    date = models.DateField()
    
    # Payment info
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    receipt = models.FileField(upload_to='expense_receipts/', blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    approved_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'date']),
            models.Index(fields=['tenant', 'category']),
            models.Index(fields=['tenant', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.amount}"
    
    def save(self, *args, **kwargs):
        """Save expense and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='Expense',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'category_id': self.category_id if self.category_id else None,
                        'created_by_id': self.created_by_id if self.created_by_id else None,
                        'title': self.title,
                        'description': self.description,
                        'amount': str(self.amount),
                        'date': self.date.isoformat() if self.date else None,
                        'payment_method': self.payment_method,
                        'receipt': self.receipt.name if self.receipt else None,
                        'status': self.status,
                        'approved_by_id': self.approved_by_id if self.approved_by_id else None,
                        'approved_at': self.approved_at.isoformat() if self.approved_at else None,
                        'tenant_id': tenant_id,
                    }
                )
                logger.debug(f"✅ Queued Expense sync: {self.title}")
            except Exception as e:
                logger.error(f"Failed to queue Expense sync: {e}")
    
    def approve(self, approver):
        """Approve the expense"""
        from django.utils import timezone
        self.status = 'approved'
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save()
    
    def reject(self, approver):
        """Reject the expense"""
        from django.utils import timezone
        self.status = 'rejected'
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save()
    
    def mark_paid(self):
        """Mark expense as paid"""
        self.status = 'paid'
        self.save()