# apps/food_master/models.py

from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import date
from apps.shared.tenants.models import Tenant as CompanyTenant

User = get_user_model()


class Branch(models.Model):
    """Restaurant branches/locations"""
    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='food_branches')
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    county = models.CharField(max_length=100, blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'name']

    def __str__(self):
        return f"{self.name} - {self.location}"


class Category(models.Model):
    """Menu categories (e.g., Appetizers, Main Course, Desserts, Drinks)"""
    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='food_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="Font Awesome icon class")
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        unique_together = ['tenant', 'name']

    def __str__(self):
        return self.name

    @property
    def total_items(self):
        return self.items.filter(is_active=True).count()


class MenuItem(models.Model):
    """Menu items"""
    UNIT_CHOICES = [
        ('piece', 'Piece'),
        ('plate', 'Plate'),
        ('serving', 'Serving'),
        ('kg', 'Kilogram'),
        ('g', 'Gram'),
        ('ml', 'Milliliter'),
        ('l', 'Liter'),
        ('bottle', 'Bottle'),
        ('glass', 'Glass'),
        ('cup', 'Cup'),
        ('bowl', 'Bowl'),
        ('pot', 'Pot'),
    ]

    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='food_items')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='menu_items', null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Cost to make")
    
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='serving')
    preparation_time = models.IntegerField(default=0, help_text="Preparation time in minutes")
    
    is_available = models.BooleanField(default=True)
    is_vegetarian = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    is_gluten_free = models.BooleanField(default=False)
    is_spicy = models.BooleanField(default=False)
    has_allergens = models.BooleanField(default=False)
    
    image = models.ImageField(upload_to='menu_items/', blank=True, null=True)
    display_order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        unique_together = ['tenant', 'name']

    def __str__(self):
        return f"{self.name} - KES {self.price}"

    @property
    def profit_margin(self):
        if self.cost > 0:
            return ((self.price - self.cost) / self.price) * 100
        return 0


class Table(models.Model):
    """Restaurant tables"""
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('reserved', 'Reserved'),
        ('cleaning', 'Cleaning'),
        ('maintenance', 'Under Maintenance'),
    ]

    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='food_tables')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='tables')
    
    table_number = models.CharField(max_length=20)
    capacity = models.IntegerField(default=2, help_text="Number of seats")
    location = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Window, Patio, VIP")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['table_number']
        unique_together = ['tenant', 'branch', 'table_number']

    def __str__(self):
        return f"Table {self.table_number} - {self.branch.name}"


class Customer(models.Model):
    """Restaurant customers"""
    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='food_customers')
    
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    address = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['tenant', 'phone_number']

    def __str__(self):
        return self.name

    @property
    def total_orders(self):
        return self.orders.filter(status='completed').count()

    @property
    def total_spent(self):
        return self.orders.filter(status='completed').aggregate(
            total=models.Sum('total_amount')
        )['total'] or Decimal('0.00')


class Order(models.Model):
    """Customer orders"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('served', 'Served'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partial', 'Partial'),
        ('refunded', 'Refunded'),
    ]

    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='food_orders')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='orders')
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    
    order_number = models.CharField(max_length=50, unique=True)
    order_type = models.CharField(max_length=20, choices=[
        ('dine_in', 'Dine In'),
        ('takeaway', 'Takeaway'),
        ('delivery', 'Delivery'),
    ], default='dine_in')

    # Created by fields
    created_by_id = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="ID of user who created this order"
    )
    created_by_username = models.CharField(
        max_length=150, 
        blank=True, 
        null=True, 
        help_text="Username of user who created this order"
    )
    created_by_full_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Full name of user who created this order"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00') )
    
    payment_method = models.CharField(max_length=20, choices=[
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
        ('voucher', 'Voucher'),
    ], blank=True, null=True)
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        permissions = [
            ('can_take_orders', 'Can take orders'),
            ('can_view_orders', 'Can view orders'),
            ('can_process_payments', 'Can process payments'),
            ('can_manage_menu', 'Can manage menu'),
            ('can_manage_branches', 'Can manage branches'),
            ('can_manage_tables', 'Can manage tables'),
            ('can_manage_reservations', 'Can manage reservations'),
            ('can_manage_customers', 'Can manage customers'),
            ('can_view_reports', 'Can view reports'),
            ('can_manage_settings', 'Can manage settings'),
        ]

    def __str__(self):
        return f"Order #{self.order_number} - {self.customer.name if self.customer else 'Walk-in'}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            today = date.today().strftime('%Y%m%d')
            last_order = Order.objects.filter(
                order_number__startswith=f'ORD-{today}'
            ).order_by('-order_number').first()
            
            if last_order:
                last_num = int(last_order.order_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.order_number = f"ORD-{today}-{str(new_num).zfill(4)}"
        
        # Calculate subtotal and tax properly
        # Get tenant's tax settings
        from apps.shared.settings.models import ReceiptSetting
        try:
            receipt_settings = ReceiptSetting.objects.get(tenant=self.tenant)
            vat_rate = receipt_settings.vat_rate if receipt_settings.vat_rate else Decimal('16.00')
            tax_type = receipt_settings.tax_type if receipt_settings.tax_type else 'exclusive'
        except ReceiptSetting.DoesNotExist:
            vat_rate = Decimal('16.00')
            tax_type = 'exclusive'
        
        # If inclusive tax, the subtotal is already the total including VAT
        if tax_type == 'inclusive':
            # Subtotal is the total including VAT (from order items)
            # Calculate VAT-exclusive amount
            vat_rate_decimal = vat_rate / Decimal('100.00')
            divisor = Decimal('1.00') + vat_rate_decimal
            vat_exclusive = self.subtotal / divisor
            self.tax = self.subtotal - vat_exclusive
            self.total_amount = self.subtotal
        else:
            # Exclusive tax: VAT is added to subtotal
            self.tax = self.subtotal * (vat_rate / Decimal('100.00'))
            self.total_amount = self.subtotal + self.tax
        
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    """Items in an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='order_items')
    
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    
    special_instructions = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name} - Order #{self.order.order_number}"

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class Reservation(models.Model):
    """Table reservations"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('seated', 'Seated'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]

    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='food_reservations')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='reservations')
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, blank=True, related_name='reservations')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='reservations')
    
    reservation_date = models.DateField()
    reservation_time = models.TimeField()
    number_of_guests = models.IntegerField(default=2)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    special_requests = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['reservation_date', 'reservation_time']

    def __str__(self):
        return f"Reservation for {self.customer.name} - {self.reservation_date} {self.reservation_time}"


class Staff(models.Model):
    """Restaurant staff"""
    ROLE_CHOICES = [
        ('manager', 'Manager'),
        ('chef', 'Chef'),
        ('waiter', 'Waiter'),
        ('cashier', 'Cashier'),
        ('kitchen', 'Kitchen Staff'),
        ('cleaner', 'Cleaner'),
        ('other', 'Other'),
    ]

    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='food_staff')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='staff', null=True, blank=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='food_staff_profile', null=True, blank=True)
    
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='waiter')
    pin = models.CharField(max_length=128, blank=True, null=True, help_text="4-digit PIN for POS access")
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    hire_date = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Staff"

    def __str__(self):
        return f"{self.name} - {self.get_role_display()}"

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
        # Check if pin is hashed or plain text (for backward compatibility)
        if self.pin.startswith('pbkdf2_sha256') or self.pin.startswith('bcrypt'):
            return check_password(raw_pin, self.pin)
        else:
            # Legacy plain text comparison
            return self.pin == raw_pin
        

class Expense(models.Model):
    """Restaurant expenses"""
    EXPENSE_TYPE_CHOICES = [
        ('food', 'Food Supplies'),
        ('beverage', 'Beverage Supplies'),
        ('utility', 'Utilities'),
        ('rent', 'Rent'),
        ('salary', 'Salaries'),
        ('maintenance', 'Maintenance'),
        ('equipment', 'Equipment'),
        ('marketing', 'Marketing'),
        ('other', 'Other'),
    ]

    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='food_expenses')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='expenses')
    
    description = models.CharField(max_length=255)
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()
    
    receipt = models.FileField(upload_to='expenses/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date']

    def __str__(self):
        return f"{self.description} - KES {self.amount}"
    

class Purchase(models.Model):
    """Purchase records for inventory"""
    
    PURCHASE_TYPE_CHOICES = [
        ('food', 'Food Supplies'),
        ('beverage', 'Beverage Supplies'),
        ('ingredient', 'Ingredients'),
        ('packaging', 'Packaging Materials'),
        ('cleaning', 'Cleaning Supplies'),
        ('equipment', 'Equipment'),
        ('other', 'Other'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('partial', 'Partial'),
    ]
    
    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='purchases')
    supplier = models.CharField(max_length=200, blank=True, null=True, help_text="Supplier name")
    supplier_contact = models.CharField(max_length=50, blank=True, null=True, help_text="Supplier phone/email")
    
    item_name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=PURCHASE_TYPE_CHOICES, default='food')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    unit = models.CharField(max_length=20, default='kg', choices=[
        ('kg', 'Kilogram'),
        ('g', 'Gram'),
        ('l', 'Liter'),
        ('ml', 'Milliliter'),
        ('piece', 'Piece'),
        ('dozen', 'Dozen'),
        ('pack', 'Pack'),
        ('bottle', 'Bottle'),
        ('bag', 'Bag'),
        ('box', 'Box'),
        ('carton', 'Carton'),
        ('other', 'Other'),
    ])
    
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    purchase_date = models.DateField(auto_now_add=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='paid')
    payment_method = models.CharField(max_length=20, choices=[
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
        ('card', 'Card'),
        ('credit', 'Credit'),
    ], blank=True, null=True)
    
    receipt = models.FileField(upload_to='purchase_receipts/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-purchase_date', '-created_at']
        verbose_name = 'Purchase'
        verbose_name_plural = 'Purchases'
        indexes = [
            models.Index(fields=['tenant', 'purchase_date']),
            models.Index(fields=['tenant', 'category']),
            models.Index(fields=['tenant', 'item_name']),
        ]
    
    def __str__(self):
        return f"{self.item_name} - {self.quantity}{self.unit} - KES {self.total_cost}"
    
    def save(self, *args, **kwargs):
        self.total_cost = self.quantity * self.unit_price
        super().save(*args, **kwargs)