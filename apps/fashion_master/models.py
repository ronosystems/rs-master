# apps/fashion_master/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import logging
from django.contrib.auth.hashers import check_password, make_password

logger = logging.getLogger(__name__)


# ============================================
# FASHION BRANCH MODEL
# ============================================

class FashionBranch(models.Model):
    """
    Fashion-specific branch extensions
    Links to the main Branch model from tronic_master
    """
    
    # Link to the main branch
    branch = models.OneToOneField(
        'tronic_master.Branch',
        on_delete=models.CASCADE,
        related_name='fashion_settings'
    )
    
    # Fashion specific fields
    store_type = models.CharField(max_length=50, choices=[
        ('boutique', 'Boutique'),
        ('department_store', 'Department Store'),
        ('outlet', 'Outlet'),
        ('pop_up', 'Pop-up Store'),
        ('showroom', 'Showroom'),
        ('warehouse', 'Warehouse'),
    ], default='boutique')
    
    # Visual merchandising
    has_fitting_rooms = models.BooleanField(default=True)
    has_tailor_services = models.BooleanField(default=False)
    has_alteration_services = models.BooleanField(default=False)
    
    # Fashion categories available
    specializes_in = models.CharField(max_length=200, blank=True, help_text="e.g., Women's Wear, Men's Wear, Children's Wear")
    
    # Store ambiance
    store_ambiance = models.TextField(blank=True, help_text="Store theme, decor, music, etc.")
    
    # Operating hours (fashion specific)
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    sunday_opening = models.TimeField(null=True, blank=True)
    sunday_closing = models.TimeField(null=True, blank=True)
    is_holiday_open = models.BooleanField(default=False)
    
    # Contact
    contact_person = models.CharField(max_length=200, blank=True)
    instagram_handle = models.CharField(max_length=100, blank=True)
    facebook_page = models.CharField(max_length=200, blank=True)
    
    # Layout
    total_floor_space = models.PositiveIntegerField(null=True, blank=True, help_text="Total floor space in sq ft")
    fitting_rooms_count = models.PositiveIntegerField(default=2)
    cash_registers = models.PositiveIntegerField(default=1)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Fashion Branch'
        verbose_name_plural = 'Fashion Branches'
        indexes = [
            models.Index(fields=['branch', 'store_type']),
            models.Index(fields=['branch', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.branch.name} - {self.get_store_type_display()}"
    
    @property
    def full_address(self):
        return self.branch.full_address
    
    @property
    def branch_name(self):
        return self.branch.name
    
    @property
    def branch_code(self):
        return self.branch.code


# ============================================
# CATEGORY MODEL (Fashion Specific)
# ============================================

class FashionCategory(models.Model):
    """
    Fashion-specific categories
    """
    
    CATEGORY_TYPES = [
        ('clothing', 'Clothing'),
        ('shoes', 'Shoes'),
        ('bedding', 'Bedding'),
        ('cosmetics', 'Cosmetics'),
        ('boutique', 'Boutique'),
        ('babyshop', 'Baby Shop'),
        ('accessories', 'Accessories'),
        ('bags', 'Bags'),
        ('jewelry', 'Jewelry'),
        ('watches', 'Watches'),
        ('other', 'Other'),
    ]
    
    GENDER_CHOICES = [
        ('men', 'Men'),
        ('women', 'Women'),
        ('unisex', 'Unisex'),
        ('kids', 'Kids'),
        ('babies', 'Babies'),
    ]
    
    SIZE_TYPES = [
        ('clothing', 'Clothing Sizes (S, M, L, XL, XXL)'),
        ('shoes', 'Shoe Sizes (35-45)'),
        ('bedding', 'Bedding Sizes (Single, Double, Queen, King)'),
        ('baby', 'Baby Sizes (0-3, 3-6, 6-9, 9-12, 12-18, 18-24)'),
        ('generic', 'Generic Sizes'),
        ('none', 'No Size (Cosmetics, Accessories)'),
    ]
    
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_categories')
    
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, default='clothing')
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='unisex')
    size_type = models.CharField(max_length=20, choices=SIZE_TYPES, default='clothing')
    
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_fashion_categories')
    
    class Meta:
        ordering = ['tenant', 'category_type', 'name']
        unique_together = [['tenant', 'name']]
        indexes = [
            models.Index(fields=['tenant', 'category_type']),
            models.Index(fields=['tenant', 'gender']),
        ]
    
    def __str__(self):
        return f"{self.get_category_type_display()} - {self.name}"
    
    @property
    def product_count(self):
        return self.fashion_products.count()


# ============================================
# FASHION PRODUCT MODEL
# ============================================

class FashionProduct(models.Model):
    """
    Fashion product - Each variant (size, color combination)
    """
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_products')
    category = models.ForeignKey(FashionCategory, on_delete=models.PROTECT, related_name='fashion_products')
    branch = models.ForeignKey('tronic_master.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='fashion_products')
    supplier = models.ForeignKey('tronic_master.Supplier', on_delete=models.SET_NULL, null=True, blank=True, related_name='fashion_products')
    
    # ============================================
    # PRODUCT IDENTIFICATION
    # ============================================
    sku_code = models.CharField(max_length=50, db_index=True)
    barcode = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    
    # ============================================
    # PRODUCT DETAILS
    # ============================================
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100, blank=True)
    
    # Size and Color
    size = models.CharField(max_length=20, blank=True, help_text="e.g., S, M, L, 38, 40")
    color = models.CharField(max_length=50, blank=True)
    material = models.CharField(max_length=100, blank=True)
    
    # ============================================
    # PRICING
    # ============================================
    buying_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    best_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # ============================================
    # STOCK MANAGEMENT
    # ============================================
    quantity_in_stock = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    damaged_quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=10)
    
    # ============================================
    # FASHION SPECIFIC FIELDS
    # ============================================
    season = models.CharField(max_length=50, blank=True, help_text="Summer, Winter, Spring, Fall")
    collection = models.CharField(max_length=100, blank=True, help_text="Collection name")
    style_code = models.CharField(max_length=50, blank=True)
    
    # ============================================
    # IMAGES
    # ============================================
    image = models.ImageField(upload_to='fashion_products/', blank=True, null=True)
    image_alt = models.CharField(max_length=100, blank=True)
    image_2 = models.ImageField(upload_to='fashion_products/', blank=True, null=True)
    image_3 = models.ImageField(upload_to='fashion_products/', blank=True, null=True)
    
    # ============================================
    # STATUS
    # ============================================
    is_active = models.BooleanField(default=True)
    is_discontinued = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    
    # ============================================
    # AUDIT
    # ============================================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_fashion_products')
    last_modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='modified_fashion_products')
    
    class Meta:
        ordering = ['tenant', 'category', 'name']
        unique_together = [
            ['tenant', 'sku_code'],
            ['tenant', 'category', 'name', 'size', 'color'],
        ]
        indexes = [
            models.Index(fields=['tenant', 'sku_code']),
            models.Index(fields=['tenant', 'category', 'is_active']),
            models.Index(fields=['tenant', 'size', 'color']),
            models.Index(fields=['tenant', 'is_featured', 'is_new_arrival']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.size} - {self.color})"
    
    @property
    def display_name(self):
        parts = [self.name]
        if self.size:
            parts.append(f"Size: {self.size}")
        if self.color:
            parts.append(f"Color: {self.color}")
        return " | ".join(parts)
    
    @property
    def available_quantity(self):
        return self.quantity_in_stock - self.reserved_quantity
    
    @property
    def is_low_stock(self):
        return self.available_quantity <= self.reorder_level and self.available_quantity > 0
    
    @property
    def is_out_of_stock(self):
        return self.available_quantity == 0
    
    @property
    def stock_value(self):
        return self.available_quantity * self.buying_price
    
    @property
    def profit_margin(self):
        if self.buying_price and self.buying_price > 0:
            return self.selling_price - self.buying_price
        return Decimal('0.00')
    
    def save(self, *args, **kwargs):
        if not self.sku_code:
            self.sku_code = self._generate_sku()
        super().save(*args, **kwargs)
    
    def _generate_sku(self):
        """Generate SKU: CAT-NAME-SIZE-COLOR"""
        prefix = self.category.category_type.upper()[:3] if self.category else 'FSH'
        name_part = ''.join([word[0] for word in self.name.split()[:3]]).upper()
        size_part = self.size.upper() if self.size else 'ALL'
        color_part = self.color.upper() if self.color else 'ALL'
        return f"{prefix}-{name_part}-{size_part}-{color_part}"


# ============================================
# FASHION PRODUCT VARIANT (Size/Color Combination)
# ============================================

class FashionVariant(models.Model):
    """
    Individual product variants (size + color combinations)
    """
    
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_variants')
    product = models.ForeignKey(FashionProduct, on_delete=models.CASCADE, related_name='variants')
    
    # Variant details
    size = models.CharField(max_length=20)
    color = models.CharField(max_length=50)
    sku = models.CharField(max_length=50, db_index=True)
    barcode = models.CharField(max_length=100, blank=True, null=True)
    
    # Pricing
    buying_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Stock
    quantity = models.PositiveIntegerField(default=0)
    reserved = models.PositiveIntegerField(default=0)
    
    # Image
    image = models.ImageField(upload_to='fashion_variants/', blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['product', 'size', 'color']
        unique_together = [
            ['tenant', 'sku'],
            ['product', 'size', 'color'],
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.size} - {self.color}"
    
    @property
    def available_quantity(self):
        return self.quantity - self.reserved


# ============================================
# FASHION STAFF MODEL
# ============================================

class FashionStaff(models.Model):
    """
    Fashion Master Staff - Employees working in fashion branches
    """
    
    # ============================================
    # STAFF ROLES (Fashion specific)
    # ============================================
    ROLE_CHOICES = [
        ('manager', 'Store Manager'),
        ('sales_rep', 'Sales Representative'),
        ('stylist', 'Fashion Stylist'),
        ('cashier', 'Cashier'),
        ('stock_controller', 'Stock Controller'),
        ('visual_merchandiser', 'Visual Merchandiser'),
        ('tailor', 'Tailor'),
        ('other', 'Other'),
    ]

    # ============================================
    # RELATIONSHIPS
    # ============================================
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_staff')
    branch = models.ForeignKey(
        'tronic_master.Branch', 
        on_delete=models.CASCADE, 
        related_name='fashion_staff', 
        null=True, 
        blank=True
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='fashion_staff_profile', 
        null=True, 
        blank=True
    )
    
    # ============================================
    # STAFF DETAILS
    # ============================================
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='sales_rep')
    pin = models.CharField(max_length=128, blank=True, null=True, help_text="4-digit PIN for POS access")
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    hire_date = models.DateField(null=True, blank=True)
    
    # ============================================
    # FASHION SPECIFIC FIELDS
    # ============================================
    expertise = models.CharField(max_length=200, blank=True, help_text="e.g., Women's Wear, Men's Wear, Children's Wear")
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Commission rate for sales")
    
    # ============================================
    # STATUS
    # ============================================
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Fashion Staff"
        indexes = [
            models.Index(fields=['tenant', 'branch']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_role_display()}"

    # ============================================
    # PIN METHODS
    # ============================================
    def set_pin(self, raw_pin):
        """Set PIN with hashing"""
        if raw_pin and len(raw_pin) == 4 and raw_pin.isdigit():
            self.pin = make_password(raw_pin)
        else:
            raise ValueError("PIN must be 4 digits")

    def check_pin(self, raw_pin):
        """Check PIN against hashed value"""
        if not self.pin:
            return False
        if not raw_pin:
            return False
        if self.pin.startswith('pbkdf2_sha256') or self.pin.startswith('bcrypt'):
            return check_password(raw_pin, self.pin)
        else:
            return self.pin == raw_pin

    # ============================================
    # PROPERTIES
    # ============================================
    @property
    def full_name(self):
        return self.name

    @property
    def total_sales(self):
        """Total sales made by this staff member"""
        from .models import FashionSale
        if self.user:
            return FashionSale.objects.filter(
                cashier=self.user,
                status='completed'
            ).aggregate(total=models.Sum('total'))['total'] or Decimal('0.00')
        return Decimal('0.00')

    @property
    def total_orders(self):
        """Total orders processed by this staff member"""
        from .models import FashionSale
        if self.user:
            return FashionSale.objects.filter(
                cashier=self.user,
                status='completed'
            ).count()
        return 0


# ============================================
# FASHION STAFF ATTENDANCE
# ============================================

class FashionStaffAttendance(models.Model):
    """Fashion Master Staff Attendance"""
    
    # ============================================
    # ATTENDANCE STATUS
    # ============================================
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
        ('leave', 'On Leave'),
        ('holiday', 'Holiday'),
    ]
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    staff = models.ForeignKey(FashionStaff, on_delete=models.CASCADE, related_name='attendances')
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_staff_attendances')
    branch = models.ForeignKey('tronic_master.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='fashion_staff_attendances')
    
    # ============================================
    # ATTENDANCE DETAILS
    # ============================================
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    check_in_location = models.CharField(max_length=255, blank=True)
    check_out_location = models.CharField(max_length=255, blank=True)
    
    # Work Details
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # Notes
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_fashion_attendances'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # ============================================
    # TIMESTAMPS
    # ============================================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Fashion Staff Attendance'
        verbose_name_plural = 'Fashion Staff Attendances'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['staff', 'date']),
            models.Index(fields=['tenant', 'date']),
        ]
        unique_together = ['staff', 'date']
    
    def __str__(self):
        return f"{self.staff.name} - {self.date} ({self.get_status_display()})"
    
    def calculate_hours(self):
        """Calculate hours worked"""
        if self.check_in_time and self.check_out_time:
            from datetime import datetime
            check_in = datetime.combine(datetime.min, self.check_in_time)
            check_out = datetime.combine(datetime.min, self.check_out_time)
            delta = check_out - check_in
            hours = delta.seconds / 3600
            self.hours_worked = Decimal(str(round(hours, 2)))
            return self.hours_worked
        return Decimal('0.00')
    
    def save(self, *args, **kwargs):
        """Calculate hours before saving"""
        if self.check_in_time and self.check_out_time:
            self.calculate_hours()
        super().save(*args, **kwargs)


# ============================================
# FASHION STAFF LEAVE
# ============================================

class FashionStaffLeave(models.Model):
    """Fashion Master Staff Leave"""
    
    # ============================================
    # LEAVE TYPES
    # ============================================
    LEAVE_TYPE_CHOICES = [
        ('annual', 'Annual Leave'),
        ('sick', 'Sick Leave'),
        ('maternity', 'Maternity Leave'),
        ('paternity', 'Paternity Leave'),
        ('compassionate', 'Compassionate Leave'),
        ('study', 'Study Leave'),
        ('other', 'Other'),
    ]
    
    # ============================================
    # LEAVE STATUS
    # ============================================
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    staff = models.ForeignKey(FashionStaff, on_delete=models.CASCADE, related_name='leaves')
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_staff_leaves')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_fashion_leaves'
    )
    
    # ============================================
    # LEAVE DETAILS
    # ============================================
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES, default='annual')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    notes = models.TextField(blank=True)
    
    # Approval
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # ============================================
    # TIMESTAMPS
    # ============================================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_fashion_leaves'
    )
    
    class Meta:
        verbose_name = 'Fashion Staff Leave'
        verbose_name_plural = 'Fashion Staff Leaves'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['staff', 'status']),
            models.Index(fields=['tenant', 'status']),
        ]
    
    def __str__(self):
        return f"{self.staff.name} - {self.get_leave_type_display()} ({self.get_status_display()})"
    
    @property
    def days(self):
        """Calculate number of leave days"""
        return (self.end_date - self.start_date).days + 1
    
    def approve(self, approver):
        """Approve leave request"""
        self.status = 'approved'
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save()
    
    def reject(self, reason, approver):
        """Reject leave request"""
        self.status = 'rejected'
        self.approved_by = approver
        self.rejection_reason = reason
        self.approved_at = timezone.now()
        self.save()


# ============================================
# FASHION ROLE (Custom project roles)
# ============================================

class FashionRole(models.Model):
    """
    Fashion-specific custom roles created by Company Admin
    """
    
    # Which company owns this role
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_roles')
    
    # Role details
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Users assigned to this role
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='fashion_roles',
        blank=True
    )
    
    # Permissions as JSON list
    permissions = models.JSONField(default=list, help_text="List of permission codenames")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_system_role = models.BooleanField(default=False)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_fashion_roles'
    )
    
    class Meta:
        unique_together = [['tenant', 'name']]
        ordering = ['tenant', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.tenant.company_name})"
    
    def has_permission(self, codename):
        return codename in self.permissions
    
    def add_permission(self, codename):
        if codename not in self.permissions:
            self.permissions.append(codename)
            self.save()
    
    def remove_permission(self, codename):
        if codename in self.permissions:
            self.permissions.remove(codename)
            self.save()
    
    def get_users_count(self):
        return self.users.count()


# ============================================
# FASHION SALE MODEL
# ============================================

class FashionSale(models.Model):
    """
    Fashion sales with specific fields
    """
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('card', 'Card'),
        ('bank', 'Bank Transfer'),
        ('mobile', 'Mobile Money'),
        ('credit', 'Credit'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]
    
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_sales')
    branch = models.ForeignKey('tronic_master.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='fashion_sales')
    
    # ✅ Fix: Use correct app reference for Customer
    customer = models.ForeignKey(
        'customers.Customer', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='fashion_sales'
    )
    
    # Customer details (denormalized)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField(blank=True)
    
    # Sale details
    invoice_no = models.CharField(max_length=50, unique=True, db_index=True)
    sale_date = models.DateTimeField(default=timezone.now)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Payment
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    change_given = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Audit
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='fashion_sales')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-sale_date']
        indexes = [
            models.Index(fields=['tenant', 'invoice_no']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'sale_date']),
            models.Index(fields=['customer_phone']),
        ]
    
    def __str__(self):
        return f"{self.invoice_no} - {self.total}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_no:
            self.invoice_no = self._generate_invoice_number()
        super().save(*args, **kwargs)
    
    def _generate_invoice_number(self):
        prefix = f"FSH-{timezone.now().strftime('%Y%m%d')}"
        count = FashionSale.objects.filter(tenant=self.tenant, invoice_no__startswith=prefix).count() + 1
        return f"{prefix}-{count:04d}"


# ============================================
# FASHION SALE ITEM
# ============================================

class FashionSaleItem(models.Model):
    """Fashion sale items"""
    
    sale = models.ForeignKey(FashionSale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(FashionProduct, on_delete=models.CASCADE, related_name='sale_items')
    variant = models.ForeignKey(FashionVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name='sale_items')
    
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Capture product details at time of sale
    product_name = models.CharField(max_length=200)
    product_size = models.CharField(max_length=20, blank=True)
    product_color = models.CharField(max_length=50, blank=True)
    product_sku = models.CharField(max_length=50)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


# ============================================
# FASHION INVENTORY MOVEMENT
# ============================================

class FashionInventoryMovement(models.Model):
    """Track fashion inventory movements"""
    
    MOVEMENT_TYPES = [
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('return', 'Return'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
        ('damage', 'Damage/Loss'),
    ]
    
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_movements')
    product = models.ForeignKey(FashionProduct, on_delete=models.CASCADE, related_name='movements')
    variant = models.ForeignKey(FashionVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name='movements')
    branch = models.ForeignKey('tronic_master.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='fashion_movements')
    
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(help_text="Positive for IN, Negative for OUT")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    reference = models.CharField(max_length=100, blank=True, help_text="Invoice, PO, or reference number")
    notes = models.TextField(blank=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='fashion_movements')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'product']),
            models.Index(fields=['tenant', 'movement_type']),
            models.Index(fields=['tenant', 'created_at']),
        ]
    
    def __str__(self):
        direction = "IN" if self.quantity > 0 else "OUT"
        return f"{self.get_movement_type_display()} {direction} - {abs(self.quantity)} units"


# ============================================
# FASHION RETURN MODEL
# ============================================

class FashionReturn(models.Model):
    """Fashion returns"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_returns')
    sale = models.ForeignKey(FashionSale, on_delete=models.CASCADE, related_name='returns')
    product = models.ForeignKey(FashionProduct, on_delete=models.CASCADE, related_name='fashion_returns')
    variant = models.ForeignKey(FashionVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name='fashion_returns')
    
    quantity = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    reason = models.TextField()
    
    # Return details
    condition = models.CharField(max_length=20, choices=[
        ('new', 'New/Unused'),
        ('worn', 'Worn/Used'),
        ('defective', 'Defective'),
        ('damaged', 'Damaged'),
    ], default='new')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Approval
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_fashion_returns')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='fashion_returns')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['sale', 'product']),
        ]
    
    def __str__(self):
        return f"Return #{self.id} - {self.product.name} ({self.status})"


# ============================================
# FASHION STORE SETTINGS
# ============================================

class FashionStoreSettings(models.Model):
    """Fashion store specific settings"""
    
    tenant = models.OneToOneField('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_settings')
    
    # Store info
    store_name = models.CharField(max_length=200, blank=True)
    store_phone = models.CharField(max_length=20, blank=True)
    store_email = models.EmailField(blank=True)
    store_address = models.TextField(blank=True)
    
    # Tax settings
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('16.00'))
    is_tax_inclusive = models.BooleanField(default=True)
    
    # Loyalty settings
    enable_loyalty = models.BooleanField(default=False)
    points_per_100 = models.PositiveIntegerField(default=10, help_text="Points earned per 100 KES spent")
    
    # Receipt settings
    show_logo_on_receipt = models.BooleanField(default=True)
    footer_message = models.CharField(max_length=200, blank=True, default="Thank you for shopping with us!")
    
    # Inventory settings
    low_stock_threshold = models.PositiveIntegerField(default=10)
    auto_restock_level = models.PositiveIntegerField(default=5)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Settings for {self.tenant.company_name}"


# ============================================
# FASHION SEASON/COLLECTION
# ============================================

class FashionCollection(models.Model):
    """Fashion collections/seasons"""
    
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='fashion_collections')
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    year = models.PositiveIntegerField(help_text="Collection year")
    season = models.CharField(max_length=20, choices=[
        ('spring', 'Spring'),
        ('summer', 'Summer'),
        ('autumn', 'Autumn'),
        ('fall', 'Fall'),
        ('winter', 'Winter'),
        ('holiday', 'Holiday'),
        ('resort', 'Resort'),
    ])
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-year', '-created_at']
        unique_together = [['tenant', 'name']]
    
    def __str__(self):
        return f"{self.name} ({self.year})"


# ============================================
# SIGNALS
# ============================================

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


@receiver(pre_save, sender=FashionProduct)
def generate_fashion_sku(sender, instance, **kwargs):
    if not instance.sku_code:
        instance.sku_code = instance._generate_sku()


@receiver(post_save, sender=FashionSale)
def update_fashion_stock_on_sale(sender, instance, created, **kwargs):
    """Update stock when a sale is created"""
    if created and instance.status == 'completed':
        for item in instance.items.all():
            if item.product:
                item.product.quantity_in_stock -= item.quantity
                item.product.save()
            if item.variant:
                item.variant.quantity -= item.quantity
                item.variant.save()


@receiver(post_save, sender=FashionReturn)
def restore_fashion_stock_on_return(sender, instance, created, **kwargs):
    """Restore stock when a return is approved"""
    if instance.status == 'approved':
        instance.product.quantity_in_stock += instance.quantity
        instance.product.save()
        if instance.variant:
            instance.variant.quantity += instance.quantity
            instance.variant.save()


__all__ = [
    'FashionCategory',
    'FashionProduct',
    'FashionVariant',
    'FashionStaff',
    'FashionStaffAttendance',
    'FashionStaffLeave',
    'FashionRole',
    'FashionSale',
    'FashionSaleItem',
    'FashionInventoryMovement',
    'FashionReturn',
    'FashionStoreSettings',
    'FashionCollection',
]