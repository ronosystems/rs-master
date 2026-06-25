# apps/shared/customers/models.py

from django.db import models
from django.conf import settings
from decimal import Decimal
from apps.shared.tenants.models import Tenant


class Customer(models.Model):
    """Customer model - Shared across ALL projects"""
    
    # Tenant relationship
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='customers'
    )
    
    # Basic info
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    id_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Next of kin
    next_of_kin_name = models.CharField(max_length=200, blank=True, null=True)
    next_of_kin_phone = models.CharField(max_length=20, blank=True, null=True)
    next_of_kin_relationship = models.CharField(max_length=50, blank=True, null=True)
    
    # Stats
    total_spent = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0')
    )
    loyalty_points = models.IntegerField(default=0)
    
    # Who created this customer
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_customers'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [['tenant', 'phone']]
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
    
    def __str__(self):
        return f"{self.name} ({self.phone})"
    
    def add_purchase(self, amount):
        """Add purchase amount to total_spent and loyalty points"""
        self.total_spent += Decimal(str(amount))
        self.loyalty_points += int(amount / 100)  # 1 point per 100 spent
        self.save()
    
    def get_loyalty_tier(self):
        """Get loyalty tier based on points"""
        if self.loyalty_points >= 1000:
            return 'Platinum'
        elif self.loyalty_points >= 500:
            return 'Gold'
        elif self.loyalty_points >= 100:
            return 'Silver'
        else:
            return 'Bronze'