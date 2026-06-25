# apps/tech_master/cashier/models.py

from django.db import models
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import logging

from apps.shared.tenants.models import Tenant
from apps.shared.users.models import User
from apps.tech_master.inventory.models import Branch

# ✅ ADD THIS IMPORT FOR SYNC QUEUE
from apps.shared.tenants.models import SyncQueue

logger = logging.getLogger(__name__)


class CashDrawer(models.Model):
    """Cash drawer for tracking cash transactions"""
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='cash_drawers')
    cashier = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cash_drawers')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    
    # ✅ FIXED DecimalField defaults
    opening_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    closing_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    is_open = models.BooleanField(default=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-opened_at']
        indexes = [
            models.Index(fields=['tenant', 'is_open']),
            models.Index(fields=['cashier', 'is_open']),
            models.Index(fields=['tenant', 'opened_at']),
        ]
    
    def __str__(self):
        return f"Drawer - {self.cashier.username} - {self.opened_at.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        """Save cash drawer and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='CashDrawer',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'cashier_id': self.cashier_id,
                        'branch_id': self.branch_id if self.branch_id else None,
                        'opening_amount': str(self.opening_amount),
                        'closing_amount': str(self.closing_amount) if self.closing_amount else None,
                        'opened_at': self.opened_at.isoformat() if self.opened_at else None,
                        'closed_at': self.closed_at.isoformat() if self.closed_at else None,
                        'is_open': self.is_open,
                        'notes': self.notes,
                        'tenant_id': tenant_id,
                    }
                )
                logger.debug(f"✅ Queued CashDrawer sync: {self.id}")
            except Exception as e:
                logger.error(f"Failed to queue CashDrawer sync: {e}")
    
    def total_sales(self):
        """Calculate total sales for this drawer session"""
        from apps.tech_master.sales.models import Sale
        from django.db.models import Sum
        
        try:
            result = Sale.objects.filter(
                cashier=self.cashier,
                created_at__gte=self.opened_at,
                created_at__lte=self.closed_at or timezone.now(),
                status='completed'
            ).aggregate(total=Sum('total'))
            return result['total'] or Decimal('0')
        except Exception as e:
            logger.error(f"Error calculating total sales: {e}")
            return Decimal('0')
    
    def expected_amount(self):
        """Calculate expected amount in drawer"""
        from apps.tech_master.sales.models import Sale
        from django.db.models import Sum
        
        try:
            # Get sales total
            sales_total = Sale.objects.filter(
                cashier=self.cashier,
                created_at__gte=self.opened_at,
                created_at__lte=self.closed_at or timezone.now(),
                status='completed'
            ).aggregate(total=Sum('total'))['total'] or Decimal('0')
            
            # Get transactions
            transactions = self.transactions.all()
            deposit_total = transactions.filter(transaction_type='deposit').aggregate(total=Sum('amount'))['total'] or Decimal('0')
            withdrawal_total = transactions.filter(transaction_type='withdrawal').aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            # Calculate expected
            expected = self.opening_amount + sales_total + deposit_total - withdrawal_total
            return expected
            
        except Exception as e:
            logger.error(f"Error calculating expected amount: {e}")
            return Decimal('0')
    
    def close(self, closing_amount, notes=None, user=None):
        """Close the cash drawer"""
        self.closing_amount = closing_amount
        self.closed_at = timezone.now()
        self.is_open = False
        if notes:
            self.notes = notes
        self.save()
        
        # Create closing transaction record
        try:
            from .models import CashTransaction
            CashTransaction.objects.create(
                drawer=self,
                amount=closing_amount,
                transaction_type='deposit',
                reason=f'Drawer closing - {self.cashier.username}',
                created_by=user or self.cashier
            )
        except Exception as e:
            logger.error(f"Error creating closing transaction: {e}")
        
        return True


class CashTransaction(models.Model):
    """Cash transactions within a drawer"""
    
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]
    
    drawer = models.ForeignKey(CashDrawer, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    reason = models.CharField(max_length=200)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='cash_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['drawer', 'transaction_type']),
            models.Index(fields=['drawer', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} by {self.created_by.username if self.created_by else 'Unknown'}"
    
    def save(self, *args, **kwargs):
        """Save cash transaction and queue for sync"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=self.drawer.tenant_id,
                    model_name='CashTransaction',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'drawer_id': self.drawer_id,
                        'amount': str(self.amount),
                        'transaction_type': self.transaction_type,
                        'reason': self.reason,
                        'created_by_id': self.created_by_id if self.created_by_id else None,
                        'created_at': self.created_at.isoformat() if self.created_at else None,
                        'tenant_id': self.drawer.tenant_id,
                    }
                )
                logger.debug(f"✅ Queued CashTransaction sync: {self.id}")
            except Exception as e:
                logger.error(f"Failed to queue CashTransaction sync: {e}")