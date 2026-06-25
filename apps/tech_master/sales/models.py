# apps/tech_master/sales/models.py

from django.db import models
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import logging

from apps.shared.tenants.models import Tenant
from apps.shared.users.models import User
from apps.shared.customers.models import Customer
from apps.tech_master.inventory.models import Product, ProductUnit, Branch
from django.db.models import Sum, Count, Avg
from apps.shared.tenants.models import SyncQueue




logger = logging.getLogger(__name__)





class SaleManager(models.Manager):
    """Custom manager for Sale model"""
    
    def get_today_sales(self, tenant):
        """Get today's sales for a tenant"""
        today = timezone.now().date()
        return self.filter(
            tenant=tenant,
            created_at__date=today,
            status='completed'
        )
    
    def get_month_sales(self, tenant):
        """Get current month's sales for a tenant"""
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0)
        return self.filter(
            tenant=tenant,
            created_at__gte=start_of_month,
            status='completed'
        )
    
    def get_tenant_totals(self, tenant):
        """Get totals for a tenant"""
        return self.filter(
            tenant=tenant,
            status='completed'
        ).aggregate(
            total_revenue=Sum('total'),
            total_tax=Sum('tax'),
            total_discount=Sum('discount'),
            total_sales=Count('id'),
            avg_sale=Avg('total')
        )
    
    def get_by_date_range(self, tenant, start_date, end_date):
        """Get sales by date range"""
        return self.filter(
            tenant=tenant,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status='completed'
        )

class Sale(models.Model):
    """Sales model"""
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('bank', 'Bank Transfer'),
        ('card', 'Card'),
        ('mobile', 'Mobile Money'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    objects = SaleManager()
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='sales')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    
    # Customer
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    customer_name = models.CharField(max_length=200, blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Invoice
    invoice_no = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Amounts - ✅ FIXED DecimalField defaults
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    
    # Payment
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    payment_status = models.CharField(max_length=20, default='pending')
    tax_inclusive = models.BooleanField(default=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Audit
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'invoice_no']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.invoice_no} - {self.total}"
    
    @property
    def items_count(self):
        return self.items.count()
    
    def save(self, *args, **kwargs):
        """Save sale and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        if not self.invoice_no:
            self.invoice_no = self._generate_invoice_number()
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='Sale',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'invoice_no': self.invoice_no,
                        'customer_id': self.customer_id if self.customer_id else None,
                        'customer_name': self.customer_name,
                        'customer_phone': self.customer_phone,
                        'branch_id': self.branch_id if self.branch_id else None,
                        'subtotal': str(self.subtotal),
                        'tax': str(self.tax),
                        'discount': str(self.discount),
                        'total': str(self.total),
                        'payment_method': self.payment_method,
                        'payment_status': self.payment_status,
                        'tax_inclusive': self.tax_inclusive,
                        'status': self.status,
                        'cashier_id': self.cashier_id if self.cashier_id else None,
                        'tenant_id': tenant_id,
                        'created_at': self.created_at.isoformat() if self.created_at else None,
                    }
                )
                logger.debug(f"✅ Queued Sale sync: {self.invoice_no}")
            except Exception as e:
                logger.error(f"Failed to queue Sale sync: {e}")


    def delete(self, *args, **kwargs):
        """Queue deletion for sync, then delete the object"""
        
        # ✅ Queue deletion sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=self.tenant_id,
                    model_name='Sale',
                    object_id=str(self.id),
                    operation='DELETE',
                    data={
                        'id': self.id,
                        'invoice_no': self.invoice_no,
                        'tenant_id': self.tenant_id,
                    }
                )
                logger.debug(f"✅ Queued Sale deletion sync: {self.invoice_no}")
            except Exception as e:
                logger.error(f"Failed to queue Sale deletion sync: {e}")
        
        return super().delete(*args, **kwargs)


    def _generate_invoice_number(self):
        """Generate invoice number: INV-YYYYMMDD-XXXX"""
        prefix = f"INV-{timezone.now().strftime('%Y%m%d')}"
        last_sale = Sale.objects.filter(
            invoice_no__startswith=prefix
        ).order_by('-invoice_no').first()
        
        if last_sale:
            try:
                last_number = int(last_sale.invoice_no.split('-')[-1])
                new_number = last_number + 1
            except:
                new_number = 1
        else:
            new_number = 1
        
        return f"{prefix}-{new_number:04d}"
    
    def complete(self, cashier=None):
        """Mark sale as completed"""
        if cashier:
            self.cashier = cashier
        self.status = 'completed'
        self.payment_status = 'paid'
        self.save()
        
        # Update stock quantities
        for item in self.items.all():
            if item.product_unit:
                item.product_unit.status = 'sold'
                item.product_unit.sold_date = timezone.now()
                item.product_unit.sold_by = cashier
                item.product_unit.sold_at_price = item.price
                item.product_unit.save()
                item.product_unit.product.update_quantities()
    
    def cancel(self):
        """Cancel the sale"""
        self.status = 'cancelled'
        self.save()
        
        # Restore stock
        for item in self.items.all():
            if item.product_unit:
                item.product_unit.status = 'available'
                item.product_unit.sold_date = None
                item.product_unit.sold_by = None
                item.product_unit.sold_at_price = None
                item.product_unit.save()
                item.product_unit.product.update_quantities()
    
    def refund(self):
        """Refund the sale"""
        self.status = 'refunded'
        self.save()
        
        # Restore stock
        for item in self.items.all():
            if item.product_unit:
                item.product_unit.status = 'available'
                item.product_unit.sold_date = None
                item.product_unit.sold_by = None
                item.product_unit.sold_at_price = None
                item.product_unit.save()
                item.product_unit.product.update_quantities()

class SaleItem(models.Model):
    """Sale items (line items)"""
    
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sale_items')
    product_unit = models.ForeignKey(ProductUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='sale_items')
    
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        """Save sale item and update stock"""
        is_new = self.pk is None
        
        # Calculate subtotal
        if self.price and self.quantity:
            self.subtotal = Decimal(str(self.price)) * Decimal(str(self.quantity))
        
        super().save(*args, **kwargs)
        
        # If this is a new item and it has a product unit, mark it as reserved
        if is_new and self.product_unit and self.product_unit.status == 'available':
            self.product_unit.status = 'reserved'
            self.product_unit.save()
            self.product_unit.product.update_quantities()
        
        # ✅ Queue sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=self.sale.tenant_id,
                    model_name='SaleItem',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'sale_id': self.sale_id,
                        'product_id': self.product_id,
                        'product_unit_id': self.product_unit_id if self.product_unit_id else None,
                        'quantity': self.quantity,
                        'price': str(self.price),
                        'subtotal': str(self.subtotal),
                        'tenant_id': self.sale.tenant_id,
                    }
                )
                logger.debug(f"✅ Queued SaleItem sync: {self.id}")
            except Exception as e:
                logger.error(f"Failed to queue SaleItem sync: {e}")


    def delete(self, *args, **kwargs):
        """Queue deletion for sync, then delete the object"""
        
        # ✅ Queue deletion sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=self.sale.tenant_id,
                    model_name='SaleItem',
                    object_id=str(self.id),
                    operation='DELETE',
                    data={
                        'id': self.id,
                        'sale_id': self.sale_id,
                        'product_id': self.product_id,
                        'tenant_id': self.sale.tenant_id,
                    }
                )
                logger.debug(f"✅ Queued SaleItem deletion sync: {self.id}")
            except Exception as e:
                logger.error(f"Failed to queue SaleItem deletion sync: {e}")
        
        return super().delete(*args, **kwargs)
    
class Return(models.Model):
    """Product returns model"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='returns')
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='returns')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='returns')
    
    quantity = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    reason = models.TextField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Approval
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_returns')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_returns')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['sale', 'product']),
            models.Index(fields=['tenant', 'created_at']),
        ]
    
    def __str__(self):
        return f"Return #{self.id} - {self.product.name} ({self.status})"
    
    def save(self, *args, **kwargs):
        """Save return and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='Return',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'sale_id': self.sale_id,
                        'product_id': self.product_id,
                        'quantity': self.quantity,
                        'amount': str(self.amount),
                        'reason': self.reason,
                        'status': self.status,
                        'approved_by_id': self.approved_by_id if self.approved_by_id else None,
                        'approved_at': self.approved_at.isoformat() if self.approved_at else None,
                        'created_by_id': self.created_by_id if self.created_by_id else None,
                        'tenant_id': tenant_id,
                    }
                )
                logger.debug(f"✅ Queued Return sync: #{self.id}")
            except Exception as e:
                logger.error(f"Failed to queue Return sync: {e}")


    def delete(self, *args, **kwargs):
        """Queue deletion for sync, then delete the object"""
        
        # ✅ Queue deletion sync if offline
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=self.tenant_id,
                    model_name='Return',
                    object_id=str(self.id),
                    operation='DELETE',
                    data={
                        'id': self.id,
                        'sale_id': self.sale_id,
                        'product_id': self.product_id,
                        'tenant_id': self.tenant_id,
                    }
                )
                logger.debug(f"✅ Queued Return deletion sync: #{self.id}")
            except Exception as e:
                logger.error(f"Failed to queue Return deletion sync: {e}")
        
        return super().delete(*args, **kwargs)


    def approve(self, approver):
        self.status = 'approved'
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save()
    
    def reject(self, approver):
        self.status = 'rejected'
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save()
    
    def complete(self):
        self.status = 'completed'
        self.save()