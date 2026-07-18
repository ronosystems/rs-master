from django.db import models
from apps.shared.tenants.models import Tenant
from decimal import Decimal

class LiquorCategory(models.Model):
    """Liquor categories"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='liquor_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'name']
        verbose_name_plural = "Liquor Categories"

    def __str__(self):
        return self.name


class LiquorProduct(models.Model):
    """Liquor products"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='liquor_products')
    category = models.ForeignKey(LiquorCategory, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100)
    sku = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    volume = models.CharField(max_length=50, help_text="e.g., 750ml, 1L")
    alcohol_content = models.DecimalField(max_digits=5, decimal_places=2, help_text="Alcohol %")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    quantity = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'sku']

    def __str__(self):
        return f"{self.brand} - {self.name}"


class LiquorSale(models.Model):
    """Liquor sales"""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('card', 'Card'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='liquor_sales')
    invoice_number = models.CharField(max_length=50, unique=True)
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    status = models.CharField(max_length=20, default='completed')
    created_by = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='liquor_sales')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.invoice_number} - {self.customer_name}"