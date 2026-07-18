from django.db import models
from apps.shared.tenants.models import Tenant
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

class HardwareCategory(models.Model):
    """Hardware product categories"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='hardware_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'name']
        verbose_name_plural = "Hardware Categories"

    def __str__(self):
        return self.name

    def product_count(self):
        return self.products.filter(is_active=True).count()


class HardwareProduct(models.Model):
    """Hardware products/inventory"""
    UNIT_CHOICES = [
        ('piece', 'Piece'),
        ('kg', 'Kilogram'),
        ('g', 'Gram'),
        ('m', 'Meter'),
        ('cm', 'Centimeter'),
        ('l', 'Liter'),
        ('ml', 'Milliliter'),
        ('pack', 'Pack'),
        ('carton', 'Carton'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='hardware_products')
    category = models.ForeignKey(HardwareCategory, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='piece')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    quantity = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)
    minimum_stock = models.IntegerField(default=5)
    location = models.CharField(max_length=100, blank=True, null=True, help_text="Warehouse/Store location")
    image = models.ImageField(upload_to='hardware_products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'sku']

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    @property
    def is_out_of_stock(self):
        return self.quantity <= 0

    @property
    def stock_value(self):
        return self.quantity * self.cost_price


class HardwareSupplier(models.Model):
    """Hardware suppliers"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='hardware_suppliers')
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    tax_id = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'name']

    def __str__(self):
        return self.name


class HardwareSale(models.Model):
    """Hardware sales transactions"""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit', 'Credit'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='hardware_sales')
    invoice_number = models.CharField(max_length=50, unique=True)
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    customer_email = models.EmailField(blank=True, null=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hardware_sales')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Sale {self.invoice_number} - {self.customer_name}"

    def save(self, *args, **kwargs):
        self.net_amount = self.total_amount - self.discount + self.tax
        super().save(*args, **kwargs)


class HardwareSaleItem(models.Model):
    """Hardware sale items"""
    sale = models.ForeignKey(HardwareSale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(HardwareProduct, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class HardwareStockEntry(models.Model):
    """Stock entries for hardware products"""
    ENTRY_TYPES = [
        ('purchase', 'Purchase'),
        ('return', 'Return'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
        ('damage', 'Damage'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='hardware_stock_entries')
    product = models.ForeignKey(HardwareProduct, on_delete=models.CASCADE, related_name='stock_entries')
    quantity = models.IntegerField()
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    supplier = models.ForeignKey(HardwareSupplier, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} - {self.entry_type} ({self.quantity})"