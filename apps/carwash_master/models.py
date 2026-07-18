from django.db import models
from apps.shared.tenants.models import Tenant
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()


class ServiceCategory(models.Model):
    """Car wash service categories"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='carwash_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'name']
        verbose_name_plural = "Service Categories"

    def __str__(self):
        return self.name

    def service_count(self):
        return self.services.filter(is_active=True).count()


class Service(models.Model):
    """Car wash services offered"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='carwash_services')
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    duration = models.IntegerField(help_text="Duration in minutes", default=30)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'name']

    def __str__(self):
        return f"{self.name} - KES {self.price}"


class Vehicle(models.Model):
    """Customer vehicles"""
    VEHICLE_TYPES = [
        ('saloon', 'Saloon'),
        ('suv', 'SUV'),
        ('van', 'Van'),
        ('truck', 'Truck'),
        ('bus', 'Bus'),
        ('motorcycle', 'Motorcycle'),
        ('tuktuk', 'Tuk Tuk'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='carwash_vehicles')
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField(blank=True, null=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES, default='saloon')
    license_plate = models.CharField(max_length=20, unique=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    make = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.license_plate} - {self.customer_name}"

    def total_visits(self):
        return self.bookings.filter(status='completed').count()


class Booking(models.Model):
    """Car wash bookings"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='carwash_bookings')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='bookings')
    services = models.ManyToManyField(Service, through='BookingService')
    booking_date = models.DateTimeField()
    estimated_duration = models.IntegerField(help_text="Estimated duration in minutes", default=30)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carwash_bookings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking #{self.id} - {self.vehicle.license_plate}"

    def save(self, *args, **kwargs):
        self.net_amount = self.total_amount - self.discount
        super().save(*args, **kwargs)


class BookingService(models.Model):
    """Services included in a booking"""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='booking_services')
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service.name} x {self.quantity}"


class Employee(models.Model):
    """Car wash employees"""
    ROLE_CHOICES = [
        ('manager', 'Manager'),
        ('supervisor', 'Supervisor'),
        ('worker', 'Worker'),
        ('cashier', 'Cashier'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='carwash_employees')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='carwash_profile', null=True, blank=True)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='worker')
    hire_date = models.DateField()
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"


class Shift(models.Model):
    """Employee work shifts"""
    SHIFT_CHOICES = [
        ('morning', 'Morning (6AM - 2PM)'),
        ('afternoon', 'Afternoon (2PM - 10PM)'),
        ('night', 'Night (10PM - 6AM)'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='carwash_shifts')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='shifts')
    date = models.DateField()
    shift_type = models.CharField(max_length=20, choices=SHIFT_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    bookings = models.ManyToManyField(Booking, blank=True, related_name='shifts')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.employee.name} - {self.date} ({self.get_shift_type_display()})"


class Inventory(models.Model):
    """Car wash inventory items"""
    UNIT_CHOICES = [
        ('piece', 'Piece'),
        ('kg', 'Kilogram'),
        ('l', 'Liter'),
        ('ml', 'Milliliter'),
        ('g', 'Gram'),
        ('box', 'Box'),
        ('bottle', 'Bottle'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='carwash_inventory')
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='piece')
    quantity = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    supplier = models.CharField(max_length=200, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'sku']

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def is_low_stock(self):
        return self.quantity <= self.reorder_level


class Payment(models.Model):
    """Car wash payments"""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='carwash_payments')
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, default='completed')
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment for Booking #{self.booking.id} - KES {self.amount}"