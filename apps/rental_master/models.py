# apps/rental_master/models.py

from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timezone

from apps.shared.tenants.models import Tenant


User = get_user_model()
builtin_property = property


class Branch(models.Model):
    """Branch/Location where properties are located"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rental_branches')
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    county = models.CharField(max_length=100, blank=True, null=True)
    coordinates = models.CharField(max_length=100, blank=True, null=True, help_text="GPS coordinates")
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'name']

    def __str__(self):
        return f"{self.name} - {self.location}"

    @property
    def total_properties(self):
        return self.properties.count()

    @property
    def total_units(self):
        return RentalUnit.objects.filter(property__branch=self).count()

class Block(models.Model):
    """Block/Building within a branch"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rental_blocks')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='blocks')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True, help_text="Block code e.g., BLK-A")
    floor_count = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def total_units(self):
        return self.units.count()

class RoomSize(models.Model):
    """Room sizes e.g., Single, Double, Executive, etc."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='room_sizes')
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=200, blank=True, null=True)
    area_sqft = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    standard_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'name']

    def __str__(self):
        return self.name

class PropertyType(models.Model):
    """Types of properties: Apartment, Shop, Office, etc."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='property_types')
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=200, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'name']

    def __str__(self):
        return self.name

class Property(models.Model):
    """Main property/estate"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rental_properties')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='properties')
    property_type = models.ForeignKey(PropertyType, on_delete=models.CASCADE, related_name='properties')
    name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    location = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Properties"
        unique_together = ['tenant', 'name']

    def __str__(self):
        return f"{self.name} ({self.property_type.name})"

    @property
    def total_units(self):
        return self.rental_units.count()

    @property
    def occupied_units(self):
        return self.rental_units.filter(status='occupied').count()

    @property
    def available_units(self):
        return self.rental_units.filter(status='available').count()

    @property
    def occupancy_rate(self):
        total = self.total_units
        if total == 0:
            return 0
        return round((self.occupied_units / total) * 100, 2)

class RentalUnit(models.Model):
    """Individual rental unit (room, apartment, shop)"""
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('reserved', 'Reserved'),
        ('maintenance', 'Under Maintenance'),
        ('closed', 'Closed'),
    ]

    UNIT_TYPES = [
        ('room', 'Room'),
        ('apartment', 'Apartment'),
        ('shop', 'Shop'),
        ('office', 'Office'),
        ('warehouse', 'Warehouse'),
        ('parking', 'Parking Space'),
        ('other', 'Other'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rental_units')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='rental_units')
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='units', null=True, blank=True)
    room_size = models.ForeignKey(RoomSize, on_delete=models.CASCADE, related_name='units', null=True, blank=True)
    
    unit_number = models.CharField(max_length=50)
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPES, default='room')
    floor_number = models.IntegerField(default=0, blank=True, null=True)
    
    # Unit details
    description = models.TextField(blank=True, null=True)
    monthly_rent = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), 
                                        help_text="Deposit required before moving in")
    maintenance_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Monthly maintenance fee if applicable")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_active = models.BooleanField(default=True)
    
    # Features
    has_water = models.BooleanField(default=False)
    has_electricity = models.BooleanField(default=False)
    has_security = models.BooleanField(default=False)
    has_parking = models.BooleanField(default=False)
    has_furniture = models.BooleanField(default=False)
    has_internet = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['property', 'unit_number']
        unique_together = ['tenant', 'property', 'unit_number']

    def __str__(self):
        return f"{self.unit_number} - {self.property.name} ({self.get_unit_type_display()})"

    @builtin_property
    def is_occupied(self):
        return self.status == 'occupied'

    @builtin_property
    def current_lease(self):
        return self.leases.filter(is_active=True).first()

    @builtin_property
    def current_tenant(self):
        lease = self.current_lease
        return lease.tenant if lease else None

class Lease(models.Model):
    """Lease/rental agreement"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
        ('pending', 'Pending Approval'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='leases')
    rental_unit = models.ForeignKey(RentalUnit, on_delete=models.CASCADE, related_name='leases')
    
    # Tenant who is renting
    client_tenant = models.ForeignKey('TenantProfile', on_delete=models.CASCADE, related_name='leases', 
                                     null=True, blank=True)
    
    # Lease details
    start_date = models.DateField()
    end_date = models.DateField()
    monthly_rent = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    deposit_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Payment terms
    payment_day = models.IntegerField(default=1, help_text="Day of month rent is due")
    late_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00')) 
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=True)
    
    # Documents
    agreement_document = models.FileField(upload_to='leases/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        unique_together = ['tenant', 'rental_unit', 'start_date']

    def __str__(self):
        return f"{self.rental_unit.unit_number} - {self.client_tenant.full_name if self.client_tenant else 'Unknown'}"

    def save(self, *args, **kwargs):
        # Update unit status when lease is active
        super().save(*args, **kwargs)
        if self.status == 'active' and self.is_active:
            self.rental_unit.status = 'occupied'
            self.rental_unit.save()
        elif self.status in ['expired', 'terminated']:
            self.rental_unit.status = 'available'
            self.rental_unit.save()

    @property
    def is_current(self):
        today = date.today()
        return self.start_date <= today <= self.end_date and self.status == 'active'

    @property
    def days_remaining(self):
        if self.end_date >= date.today():
            return (self.end_date - date.today()).days
        return 0

    @property
    def is_expiring_soon(self):
        return self.days_remaining <= 30 and self.days_remaining > 0

class TenantProfile(models.Model):
    """Client tenant profile (person/company renting)"""
    TENANT_TYPES = [
        ('individual', 'Individual'),
        ('company', 'Company'),
        ('family', 'Family'),
        ('group', 'Group'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='client_tenants')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tenant_profile', null=True, blank=True)
    
    # Personal/Company details
    tenant_type = models.CharField(max_length=20, choices=TENANT_TYPES, default='individual')
    full_name = models.CharField(max_length=200)
    company_name = models.CharField(max_length=200, blank=True, null=True)
    id_number = models.CharField(max_length=50, blank=True, null=True)
    pin_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Contact details
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    alternative_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Address
    physical_address = models.TextField(blank=True, null=True)
    postal_address = models.CharField(max_length=200, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    
    # Emergency contact
    emergency_contact_name = models.CharField(max_length=200, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True, null=True)
    
    # Documents
    id_photo = models.ImageField(upload_to='tenants/ids/', blank=True, null=True)
    passport_photo = models.ImageField(upload_to='tenants/passports/', blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']
        unique_together = ['tenant', 'email']

    def __str__(self):
        return self.company_name if self.company_name else self.full_name

    @property
    def active_leases(self):
        return self.leases.filter(is_active=True, status='active')

    @property
    def current_rental_unit(self):
        lease = self.active_leases.first()
        return lease.rental_unit if lease else None

    @property
    def total_paid(self):
        return self.payments.filter(payment_status='paid').aggregate(
            total=models.Sum('amount_paid')
        )['total'] or Decimal('0.00')

    @property
    def total_due(self):
        return self.payments.filter(
            payment_status__in=['pending', 'partial']
        ).aggregate(
            total=models.Sum('amount_due')
        )['total'] or Decimal('0.00')

class RentPayment(models.Model):
    """Rent payment records"""
    PAYMENT_STATUS = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('overdue', 'Overdue'),
        ('failed', 'Failed'),
    ]

    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mpesa', 'M-Pesa'),
        ('cheque', 'Cheque'),
        ('credit_card', 'Credit Card'),
        ('other', 'Other'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rent_payments')
    rental_unit = models.ForeignKey(RentalUnit, on_delete=models.CASCADE, related_name='payments')
    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    tenant_profile = models.ForeignKey(TenantProfile, on_delete=models.CASCADE, related_name='payments')
    
    # Payment details
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payment_date = models.DateField()
    due_date = models.DateField()
    
    # Additional charges
    late_fee_charged = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    other_charges_description = models.CharField(max_length=255, blank=True, null=True)
    
    # Payment info
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    receipt_number = models.CharField(max_length=100, blank=True, null=True)
    
    # For recurring payments
    is_recurring = models.BooleanField(default=False)
    recurring_month = models.IntegerField(null=True, blank=True)
    recurring_year = models.IntegerField(null=True, blank=True)
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date']
        unique_together = ['tenant', 'rental_unit', 'payment_date', 'recurring_month', 'recurring_year']

    def __str__(self):
        return f"{self.rental_unit.unit_number} - {self.payment_date} - {self.amount_paid}"

    @property
    def balance(self):
        return self.amount_due - self.amount_paid

    @property
    def is_overdue(self):
        return date.today() > self.due_date and self.payment_status != 'paid'


    def save(self, *args, **kwargs):
        # Auto-set recurring month/year
        if self.is_recurring and self.payment_date:
            # Ensure payment_date is a date object
            if isinstance(self.payment_date, str):
                from datetime import datetime
                self.payment_date = datetime.strptime(self.payment_date, '%Y-%m-%d').date()
            
            self.recurring_month = self.payment_date.month
            self.recurring_year = self.payment_date.year
        
        # Update status based on payment
        if self.amount_paid >= self.amount_due:
            self.payment_status = 'paid'
        elif self.amount_paid > 0:
            self.payment_status = 'partial'
        elif self.due_date:
            if isinstance(self.due_date, str):
                from datetime import datetime
                self.due_date = datetime.strptime(self.due_date, '%Y-%m-%d').date()
            if self.is_overdue:
                self.payment_status = 'overdue'
        
        super().save(*args, **kwargs)

class Deposit(models.Model):
    """Deposit payments made by tenants"""
    DEPOSIT_STATUS = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('refunded', 'Refunded'),
        ('forfeited', 'Forfeited'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='deposits')
    tenant_profile = models.ForeignKey(TenantProfile, on_delete=models.CASCADE, related_name='deposits')
    rental_unit = models.ForeignKey(RentalUnit, on_delete=models.CASCADE, related_name='deposits')
    lease = models.ForeignKey(Lease, on_delete=models.CASCADE, related_name='deposits')
    
    # Deposit details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=RentPayment.PAYMENT_METHODS, default='cash')
    status = models.CharField(max_length=20, choices=DEPOSIT_STATUS, default='pending')
    
    # Refund details
    refund_date = models.DateField(blank=True, null=True)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    refund_reason = models.TextField(blank=True, null=True)
    
    receipt_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date']
        unique_together = ['tenant', 'tenant_profile', 'rental_unit', 'lease']

    def __str__(self):
        return f"Deposit for {self.tenant_profile.full_name} - {self.rental_unit.unit_number}"

    @property
    def is_refundable(self):
        return self.status == 'paid' and not self.refund_date

class UtilityBill(models.Model):
    """Utility bills for units"""
    UTILITY_TYPES = [
        ('water', 'Water'),
        ('electricity', 'Electricity'),
        ('security', 'Security'),
        ('internet', 'Internet'),
        ('garbage', 'Garbage Collection'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('disputed', 'Disputed'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='utility_bills')
    rental_unit = models.ForeignKey(RentalUnit, on_delete=models.CASCADE, related_name='utility_bills')
    tenant_profile = models.ForeignKey(TenantProfile, on_delete=models.CASCADE, related_name='utility_bills', 
                                      null=True, blank=True)
    
    utility_type = models.CharField(max_length=20, choices=UTILITY_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    bill_date = models.DateField()
    due_date = models.DateField()
    paid_date = models.DateField(blank=True, null=True)
    
    meter_reading_start = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    meter_reading_end = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    units_consumed = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    receipt_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-bill_date']

    def __str__(self):
        return f"{self.get_utility_type_display()} - {self.rental_unit.unit_number} - {self.amount}"

    @property
    def is_overdue(self):
        return date.today() > self.due_date and self.status != 'paid'
    
class MaintenanceRequest(models.Model):
    """Maintenance requests from tenants"""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    CATEGORY_CHOICES = [
        ('plumbing', 'Plumbing'),
        ('electrical', 'Electrical'),
        ('carpentry', 'Carpentry'),
        ('painting', 'Painting'),
        ('appliance', 'Appliance Repair'),
        ('hvac', 'HVAC / Air Conditioning'),
        ('cleaning', 'Cleaning'),
        ('security', 'Security'),
        ('structural', 'Structural'),
        ('other', 'Other'),
    ]
    
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='maintenance_requests')
    rental_unit = models.ForeignKey(RentalUnit, on_delete=models.CASCADE, related_name='maintenance_requests')
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    reported_by = models.CharField(max_length=200, blank=True, null=True)
    assigned_to = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    scheduled_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    before_photos = models.ImageField(upload_to='maintenance/before/', null=True, blank=True)
    after_photos = models.ImageField(upload_to='maintenance/after/', null=True, blank=True)
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.rental_unit.unit_number}"
    
    @property
    def is_overdue(self):
        if self.scheduled_date and self.status not in ['completed', 'cancelled']:
            return timezone.now() > self.scheduled_date
        return False
    
    @property
    def priority_icon(self):
        icons = {
            'low': 'fa-arrow-down text-secondary',
            'medium': 'fa-arrow-right text-info',
            'high': 'fa-arrow-up text-warning',
            'urgent': 'fa-exclamation-triangle text-danger'
        }
        return icons.get(self.priority, 'fa-circle text-secondary')
    
    @property
    def status_icon(self):
        icons = {
            'pending': 'fa-clock text-warning',
            'in_progress': 'fa-spinner fa-spin text-info',
            'completed': 'fa-check-circle text-success',
            'cancelled': 'fa-times-circle text-danger'
        }
        return icons.get(self.status, 'fa-circle text-secondary')
    