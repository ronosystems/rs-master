# apps/tech_master/inventory/models.py

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal
import logging
from datetime import timedelta

# ✅ ADD THIS IMPORT FOR SYNC QUEUE
from apps.shared.tenants.models import SyncQueue

logger = logging.getLogger(__name__)

# ====================================
# BRANCH MODEL 📍
# ====================================
class Branch(models.Model):
    """
    Store/Branch locations - Tenant-specific
    Each tenant can have multiple branches (main store, sub-branches, warehouses)
    """
    
    # ============================================
    # MULTI-TENANCY
    # ============================================
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='branches',
        verbose_name="Tenant"
    )
    
    # ============================================
    # BASIC INFORMATION
    # ============================================
    name = models.CharField(
        max_length=200,
        verbose_name="Branch Name",
        help_text="e.g., Main Store, Mombasa Branch, Warehouse A"
    )
    
    code = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name="Branch Code",
        help_text="Unique branch code per tenant (e.g., MAIN, MSA, WARE-A)"
    )
    
    # ============================================
    # CONTACT INFORMATION
    # ============================================
    address = models.TextField(blank=True, verbose_name="Physical Address")
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True, verbose_name="State/County")
    country = models.CharField(max_length=100, default="Kenya")
    postal_code = models.CharField(max_length=20, blank=True)
    
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # ============================================
    # BRANCH TYPE
    # ============================================
    BRANCH_TYPE_CHOICES = [
        ('main', 'Main Store'),
        ('sub_branch', 'Sub-Branch'),
        ('warehouse', 'Warehouse'),
        ('outlet', 'Outlet'),
        ('kiosk', 'Kiosk'),
    ]
    
    branch_type = models.CharField(
        max_length=20,
        choices=BRANCH_TYPE_CHOICES,
        default='sub_branch',
        verbose_name="Branch Type"
    )
    
    is_main_branch = models.BooleanField(
        default=False,
        verbose_name="Is Main Branch?",
        help_text="Only one branch per tenant can be the main branch"
    )

    manager_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Branch Manager",
        help_text="Name of the branch manager"
    )
    
    # ============================================
    # OPERATIONAL HOURS
    # ============================================
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    is_24_hours = models.BooleanField(default=False)
    
    # ============================================
    # STATUS
    # ============================================
    is_active = models.BooleanField(default=True, verbose_name="Is Active?")
    
    # ============================================
    # ADDITIONAL INFO
    # ============================================
    notes = models.TextField(blank=True, null=True)
    
    # ============================================
    # COORDINATES (For mapping)
    # ============================================
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # ============================================
    # AUDIT FIELDS (Using AUTH_USER_MODEL)
    # ============================================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_branches'
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_branches'
    )

    class Meta:
        unique_together = [
            ['tenant', 'code'],
            ['tenant', 'name'],
        ]
        ordering = ['tenant', 'name']
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'branch_type']),
            models.Index(fields=['is_main_branch']),
        ]
        verbose_name = 'Branch'
        verbose_name_plural = 'Branches'

    def save(self, *args, **kwargs):
        """Ensure only one main branch per tenant and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        if self.is_main_branch:
            Branch.objects.filter(
                tenant=self.tenant, 
                is_main_branch=True
            ).exclude(id=self.id).update(is_main_branch=False)
        
        if not self.code:
            self.code = self._generate_branch_code()
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='Branch',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'name': self.name,
                        'code': self.code,
                        'address': self.address,
                        'city': self.city,
                        'state': self.state,
                        'country': self.country,
                        'postal_code': self.postal_code,
                        'phone': self.phone,
                        'email': self.email,
                        'branch_type': self.branch_type,
                        'is_main_branch': self.is_main_branch,
                        'manager_name': self.manager_name,
                        'opening_time': str(self.opening_time) if self.opening_time else None,
                        'closing_time': str(self.closing_time) if self.closing_time else None,
                        'is_24_hours': self.is_24_hours,
                        'is_active': self.is_active,
                        'latitude': str(self.latitude) if self.latitude else None,
                        'longitude': str(self.longitude) if self.longitude else None,
                        'tenant_id': tenant_id,
                    }
                )
                logger.debug(f"✅ Queued Branch sync: {self.name}")
            except Exception as e:
                logger.error(f"Failed to queue Branch sync: {e}")
    
    def _generate_branch_code(self):
        """Generate branch code from name if not provided"""
        name_clean = self.name.upper()
        name_clean = name_clean.replace('STORE', '').replace('BRANCH', '').replace('WAREHOUSE', '')
        name_clean = ''.join(e for e in name_clean if e.isalnum())
        
        if len(name_clean) >= 4:
            return name_clean[:4]
        elif len(name_clean) >= 2:
            return name_clean
        else:
            count = Branch.objects.filter(tenant=self.tenant).count() + 1
            return f"BR{count:03d}"
    
    @property
    def full_address(self):
        parts = []
        if self.address:
            parts.append(self.address)
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.country:
            parts.append(self.country)
        if self.postal_code:
            parts.append(self.postal_code)
        return ', '.join(parts)
    
    @property
    def product_count(self):
        return self.products.count()
    
    @property
    def unit_count(self):
        return self.product_units.count()
    
    @property
    def available_unit_count(self):
        return self.product_units.filter(status='available').count()
    
    @property
    def is_open_now(self):
        if self.is_24_hours:
            return True
        if not self.opening_time or not self.closing_time:
            return True
        now = timezone.now().time()
        return self.opening_time <= now <= self.closing_time
    
    def __str__(self):
        main_indicator = " (MAIN)" if self.is_main_branch else ""
        return f"{self.name} ({self.code}){main_indicator}"


# ====================================
# BRANCH STOCK MODEL 📦
# ====================================
class BranchStock(models.Model):
    """Track stock levels per branch for bulk items"""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='branch_stocks')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='branch_stocks')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='branch_stocks')
    quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['branch', 'product']]
        indexes = [
            models.Index(fields=['branch', 'product']),
            models.Index(fields=['tenant', 'branch']),
        ]
        verbose_name = 'Branch Stock'
        verbose_name_plural = 'Branch Stocks'
    
    def __str__(self):
        return f"{self.branch.code} - {self.product.sku_code}: {self.quantity}"


# ====================================
# INVENTORY SUPPLIER MODEL 📦
# ====================================
class Supplier(models.Model):
    """Product suppliers"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='suppliers'
    )
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True, null=True)
    tax_id = models.CharField(max_length=50, blank=True, null=True)
    payment_terms = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [['tenant', 'name']]
        ordering = ['tenant', 'name']
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'

    def __str__(self):
        return f"{self.name}"

    @property
    def product_count(self):
        return self.products.count()


# ====================================
# INVENTORY CATEGORY MODEL 📦
# ====================================
class Category(models.Model):
    """
    Product categories - Tenant-specific
    """
    
    ITEM_TYPE_CHOICES = [
        ('single', 'Single Item'),
        ('bulk', 'Bulk Item'),
    ]
    
    IDENTIFIER_TYPE_CHOICES = [
        ('imei', 'IMEI Number (15-digit)'),
        ('serial', 'Serial Number'),
        ('none', 'No Unique Identifier'),
    ]

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='inventory_categories'
    )
    
    name = models.CharField(max_length=100)
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES)
    identifier_type = models.CharField(max_length=10, choices=IDENTIFIER_TYPE_CHOICES, default='imei')
    category_code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [['tenant', 'name'], ['tenant', 'category_code']]
        ordering = ['tenant', 'name']
        indexes = [
            models.Index(fields=['tenant', 'name']),
            models.Index(fields=['tenant', 'category_code']),
        ]

    def save(self, *args, **kwargs):
        """Save category and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        if not self.category_code:
            clean_name = self.name.strip().upper()
            clean_name = ''.join(e for e in clean_name if e.isalnum())
            self.category_code = clean_name[:20]
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='Category',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'name': self.name,
                        'category_code': self.category_code,
                        'description': self.description,
                        'item_type': self.item_type,
                        'identifier_type': self.identifier_type,
                        'is_active': self.is_active,
                        'tenant_id': tenant_id,
                    }
                )
                logger.debug(f"✅ Queued Category sync: {self.name}")
            except Exception as e:
                logger.error(f"Failed to queue Category sync: {e}")

    def __str__(self):
        return f"{self.name} ({self.category_code})"
    
    @property
    def is_single_item(self):
        return self.item_type == 'single'
    
    @property
    def is_bulk_item(self):
        return self.item_type == 'bulk'
    
    @property
    def requires_unique_id(self):
        return self.identifier_type in ['imei', 'serial']


# ====================================
# PRODUCT SKU MODEL (VARIANT LEVEL) 📦
# ====================================
class Product(models.Model):
    """
    Product SKU - Represents a PRODUCT VARIANT (not individual items)
    SKU is unique per tenant, not globally
    """
    
    # ============================================
    # MULTI-TENANCY
    # ============================================
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name="Tenant"
    )
    
    # ===========================================
    # BRANCH SHOPS
    # ===========================================
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name="Default Branch"
    )

    # ============================================
    # SKU IDENTIFICATION (Tenant-specific)
    # ============================================
    sku_code = models.CharField(
        max_length=50, 
        db_index=True,
        verbose_name="SKU Code",
        help_text="Unique product code per tenant (e.g., 001, 002 or custom)"
    )

    # Add barcode field for bulk products
    barcode = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Barcode",
        help_text="Product barcode (for bulk products)"
    )    
    
    # ============================================
    # PRODUCT VARIANT INFORMATION
    # ============================================
    name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Product Name",
        help_text="Display name (auto-generated if blank)"
    )
    
    brand = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name="Brand"
    )
    
    model = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Model"
    )
    
    category = models.ForeignKey(
        Category, 
        on_delete=models.PROTECT, 
        related_name='products',
        verbose_name="Category"
    )
    
    specifications = models.JSONField(
        default=dict,
        blank=True, 
        verbose_name="Specifications",
        help_text="RAM, storage, color, etc. Example: {'ram': '4GB', 'storage': '128GB', 'color': 'Black'}"
    )

    # ============================================
    # PRICING
    # ============================================
    buying_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0'),
        verbose_name="Buying Price (KES)"
    )
    
    selling_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0'),
        verbose_name="Selling Price (KES)"
    )
    
    best_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Best/Retail Price (KES)"
    )
    
    # ============================================
    # STOCK MANAGEMENT
    # ============================================
    total_quantity = models.PositiveIntegerField(default=0)
    available_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    damaged_quantity = models.PositiveIntegerField(default=0)
    
    # For bulk items
    bulk_quantity = models.PositiveIntegerField(default=0)
    bulk_serial_number = models.CharField(max_length=100, blank=True, null=True)
    
    # ============================================
    # SUPPLIER AND STOCK MANAGEMENT
    # ============================================
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='products',
        verbose_name="Supplier"
    )
    
    reorder_level = models.PositiveIntegerField(default=5)
    last_restocked = models.DateTimeField(null=True, blank=True)
    warranty_months = models.PositiveIntegerField(default=12)
    
    # ============================================
    # IMAGES
    # ============================================
    image = models.ImageField(
        upload_to='product_images/',
        blank=True,
        null=True,
        verbose_name="Product Image"
    )

    
    # ============================================
    # STATUS
    # ============================================
    is_active = models.BooleanField(default=True)
    is_discontinued = models.BooleanField(default=False)
    
    # ============================================
    # AUDIT FIELDS (Using AUTH_USER_MODEL)
    # ============================================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_products'
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_products'
    )
    
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['tenant', 'sku_code']
        unique_together = [
            ['tenant', 'sku_code'],
            ['tenant', 'brand', 'model', 'specifications'],
        ]
        indexes = [
            models.Index(fields=['tenant', 'sku_code']),
            models.Index(fields=['tenant', 'brand', 'model']),
            models.Index(fields=['tenant', 'category', 'is_active']),
            models.Index(fields=['tenant', 'available_quantity']),
        ]
        verbose_name = 'Product SKU'
        verbose_name_plural = 'Product SKUs'

    def save(self, *args, **kwargs):
        """Enhanced save with full sync support"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        # Track previous state for conflict resolution
        if not is_new:
            try:
                old_instance = Product.objects.get(pk=self.pk)
                self._previous_data = {
                    'sku_code': old_instance.sku_code,
                    'name': old_instance.name,
                    'brand': old_instance.brand,
                    'model': old_instance.model,
                    'buying_price': str(old_instance.buying_price),
                    'selling_price': str(old_instance.selling_price),
                    'total_quantity': old_instance.total_quantity,
                    'available_quantity': old_instance.available_quantity,
                    'reorder_level': old_instance.reorder_level,
                    'is_active': old_instance.is_active,
                }
            except Product.DoesNotExist:
                self._previous_data = None
        
        # Existing save logic
        if 'modified_by' in kwargs:
            self.last_modified_by = kwargs.pop('modified_by')
        if 'created_by' in kwargs and not self.pk:
            self.created_by = kwargs.pop('created_by')
        
        if not self.sku_code:
            self.sku_code = self._generate_sku_code()
        
        if not self.name:
            self.name = self._generate_name()
        
        self.clean()
        super().save(*args, **kwargs)
        
        # ✅ Enhanced sync queuing with priority
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                # Determine priority based on stock levels
                priority = 5
                if self.available_quantity <= self.reorder_level:
                    priority = 8  # High priority for low stock
                if self.is_discontinued:
                    priority = 3  # Low priority
                    
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='Product',
                    object_id=str(self.id),
                    operation='CREATE' if is_new else 'UPDATE',
                    data={
                        'id': self.id,
                        'sku_code': self.sku_code,
                        'barcode': self.barcode,
                        'name': self.name,
                        'brand': self.brand,
                        'model': self.model,
                        'category_id': self.category_id,
                        'category_name': self.category.name,
                        'specifications': self.specifications,
                        'buying_price': str(self.buying_price),
                        'selling_price': str(self.selling_price),
                        'best_price': str(self.best_price) if self.best_price else None,
                        'total_quantity': self.total_quantity,
                        'available_quantity': self.available_quantity,
                        'reserved_quantity': self.reserved_quantity,
                        'damaged_quantity': self.damaged_quantity,
                        'bulk_quantity': self.bulk_quantity,
                        'supplier_id': self.supplier_id if self.supplier_id else None,
                        'supplier_name': self.supplier.name if self.supplier else None,
                        'reorder_level': self.reorder_level,
                        'warranty_months': self.warranty_months,
                        'is_active': self.is_active,
                        'is_discontinued': self.is_discontinued,
                        'tenant_id': tenant_id,
                        'branch_id': self.branch_id if self.branch_id else None,
                        'branch_name': self.branch.name if self.branch else None,
                        'description': self.description,
                        'last_updated': self.updated_at.isoformat(),
                        'previous_data': self._previous_data if hasattr(self, '_previous_data') else None,
                    },
                    priority=priority
                )
                logger.debug(f"✅ Queued Product sync: {self.sku_code} (Priority: {priority})")
            except Exception as e:
                logger.error(f"Failed to queue Product sync: {e}")
    
    def delete(self, *args, **kwargs):
        """Queue deletion for sync, then delete the object"""
        
        # ✅ Queue the deletion for sync BEFORE deleting
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=self.tenant_id,
                    model_name='Product',
                    object_id=str(self.id),
                    operation='DELETE',
                    data={
                        'id': self.id,
                        'sku_code': self.sku_code,
                        'name': self.name,
                        'tenant_id': self.tenant_id,
                    }
                )
                logger.debug(f"✅ Queued Product deletion for sync: {self.sku_code}")
            except Exception as e:
                logger.error(f"Failed to queue Product deletion sync: {e}")
        
        # ✅ Call parent delete method and return its result
        return super().delete(*args, **kwargs)
    
    def _generate_sku_code(self):
        """
        Generate tenant-specific sequential SKU code
        Examples: 000001, 000002, 000003, ... 999999, 1000000, 1000001, etc.
        """
        from django.db import transaction
        
        with transaction.atomic():
            # Get the last product for this tenant only
            # Order by sku_code as integer for proper sequential ordering
            last_product = Product.objects.filter(
                tenant=self.tenant
            ).extra(
                select={'sku_int': 'CAST(sku_code AS INTEGER)'}
            ).order_by('-sku_int').first()
        
            if last_product and last_product.sku_code:
                try:
                    # Try to convert existing SKU to integer
                    last_number = int(last_product.sku_code)
                    new_number = last_number + 1
                    
                    # Format with leading zeros (6 digits for numbers under 1 million)
                    if new_number < 1000000:
                        return f"{new_number:06d}"  # 000001 to 999999
                    else:
                        return str(new_number)  # 1000000, 1000001, etc.
                except (ValueError, TypeError):
                    # If conversion fails, find max numeric value
                    products = Product.objects.filter(tenant=self.tenant)
                    max_number = 0
                    for p in products:
                        try:
                            num = int(p.sku_code)
                            if num > max_number:
                                max_number = num
                        except:
                            pass
                    new_number = max_number + 1
                    
                    if new_number < 1000000:
                        return f"{new_number:06d}"
                    else:
                        return str(new_number)
            else:
                # First product for this tenant
                return "000001"
    
    def _generate_name(self):
        name_parts = [self.brand, self.model]
        
        if self.specifications:
            storage = self.specifications.get('storage', '')
            ram = self.specifications.get('ram', '')
            color = self.specifications.get('color', '')
            
            specs = []
            if ram:
                specs.append(ram)
            if storage:
                specs.append(storage)
            if color:
                specs.append(color)
            
            if specs:
                name_parts.append(f"({' '.join(specs)})")
        
        return ' '.join(name_parts)
    
    def clean(self):
        if not self.category:
            raise ValidationError("Category is required")
        
        if self.buying_price and self.selling_price:
            if self.buying_price > self.selling_price:
                raise ValidationError("Buying price cannot exceed selling price")
        
        if self.best_price and self.selling_price:
            if self.best_price > self.selling_price:
                raise ValidationError("Best price cannot exceed selling price")
    
    def update_quantities(self):
        if self.category.is_single_item:
            self.total_quantity = self.units.count()
            self.available_quantity = self.units.filter(status='available').count()
            self.reserved_quantity = self.units.filter(status='reserved').count()
            self.damaged_quantity = self.units.filter(status='damaged').count()
            self.bulk_quantity = 0
        else:
            total_in = StockEntry.objects.filter(
                product_sku=self, 
                quantity__gt=0
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            total_out = StockEntry.objects.filter(
                product_sku=self, 
                quantity__lt=0
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            self.bulk_quantity = total_in + abs(total_out)
            self.total_quantity = self.bulk_quantity
            self.available_quantity = self.bulk_quantity
        
        self.save(update_fields=[
            'total_quantity', 'available_quantity', 
            'reserved_quantity', 'damaged_quantity', 
            'bulk_quantity', 'updated_at'
        ])
    
    @property
    def display_name(self):
        return f"{self.name} ({self.sku_code})"
    
    @property
    def current_stock(self):
        if self.category.is_single_item:
            return self.available_quantity
        else:
            return self.bulk_quantity
    
    @property
    def needs_reorder(self):
        if not self.is_active or self.is_discontinued:
            return False
        current = self.current_stock
        return current <= self.reorder_level and current > 0
    
    @property
    def is_out_of_stock(self):
        return self.current_stock == 0
    
    @property
    def is_low_stock(self):
        return 0 < self.current_stock <= self.reorder_level
    
    @property
    def profit_margin(self):
        if self.buying_price and self.selling_price:
            return self.selling_price - self.buying_price
        return Decimal('0.00')
    
    @property
    def profit_percentage(self):
        if self.buying_price and self.buying_price > 0:
            return (self.profit_margin / self.buying_price) * 100
        return Decimal('0.0')
    
    @property
    def stock_value(self):
        return self.current_stock * self.buying_price
    
    @property
    def retail_value(self):
        return self.current_stock * self.selling_price
    
    def __str__(self):
        return self.display_name


# ====================================
# PRODUCT UNIT MODEL (INDIVIDUAL ITEMS) 📦
# ====================================
class ProductUnit(models.Model):
    """
    Individual physical items for single-item categories (phones, electronics)
    """
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('sold', 'Sold'),
        ('reserved', 'Reserved'),
        ('damaged', 'Damaged'),
        ('stolen', 'Stolen'),
        ('lost', 'Lost'),
        ('returned', 'Returned'),
        ('writeoff', 'Written Off'),
    ]
    
    CONDITION_CHOICES = [
        ('new', 'Brand New'),
        ('refurbished', 'Refurbished'),
        ('used_excellent', 'Used - Excellent'),
        ('used_good', 'Used - Good'),
        ('used_fair', 'Used - Fair'),
        ('damaged', 'Damaged'),
    ]

    # ============================================
    # MULTI-TENANCY & RELATIONSHIPS
    # ============================================
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='product_units'
    )
    
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_units',
        verbose_name="Current Branch Location"
    )
    
    last_branch_transfer_date = models.DateTimeField(null=True, blank=True)
    transferred_from_branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transferred_units',
        verbose_name="Transferred From Branch"
    )

    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='units',
        verbose_name="Product SKU"
    )
    
    # ============================================
    # UNIQUE IDENTIFIERS (Unique per tenant)
    # ============================================
    imei_number = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="IMEI Number"
    )
    
    serial_number = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Serial Number"
    )
    
    # ============================================
    # UNIT-SPECIFIC OVERRIDES
    # ============================================
    unit_buying_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Unit Buying Price"
    )
    
    unit_selling_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Unit Selling Price"
    )

    best_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Best/wholesale Price",
        help_text="whosale price for this specific unit (market price)"
    )
    
    # ============================================
    # OWNERSHIP TRACKING (For Sales Agents)
    # ============================================
    current_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_units',
        verbose_name="Current Owner",
        help_text="Sales agent currently assigned to this unit"
    )
    
    assigned_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Assigned Date"
    )
    
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_units',
        verbose_name="Assigned By"
    )
    
    # ============================================
    # STATUS AND CONDITION
    # ============================================
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='available',
        db_index=True,
        verbose_name="Status"
    )
    
    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default='new',
        verbose_name="Condition"
    )
    
    # ============================================
    # SALES INFORMATION
    # ============================================
    sold_at_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Sold At Price"
    )
    
    sold_date = models.DateTimeField(null=True, blank=True)
    sold_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sold_units'
    )
    
    # ============================================
    # PURCHASE INFORMATION
    # ============================================
    purchase_date = models.DateTimeField(default=timezone.now)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # ============================================
    # WARRANTY
    # ============================================
    warranty_start = models.DateTimeField(default=timezone.now)
    warranty_end = models.DateTimeField(null=True, blank=True)
    
    # ============================================
    # THEFT / LOSS TRACKING
    # ============================================
    loss_type = models.CharField(
        max_length=20,
        choices=[
            ('stolen', 'Stolen'),
            ('lost', 'Lost'),
            ('damaged_total', 'Totally Damaged'),
        ],
        null=True,
        blank=True
    )
    loss_reported_date = models.DateTimeField(null=True, blank=True)
    loss_reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='reported_unit_losses'
    )
    loss_notes = models.TextField(blank=True, null=True)
    police_report_number = models.CharField(max_length=100, blank=True, null=True)
    
    # ============================================
    # INSURANCE TRACKING
    # ============================================
    insurance_claim_filed = models.BooleanField(default=False)
    insurance_claim_number = models.CharField(max_length=100, blank=True, null=True)
    insurance_claim_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    insurance_payout_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    insurance_payout_date = models.DateTimeField(null=True, blank=True)
    
    # ============================================
    # RECOVERY TRACKING
    # ============================================
    recovered_date = models.DateTimeField(null=True, blank=True)
    recovered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='recovered_units'
    )
    recovery_notes = models.TextField(blank=True, null=True)
    
    # ============================================
    # LOCATION TRACKING
    # ============================================
    warehouse_location = models.CharField(max_length=50, blank=True, null=True)
    shelf_location = models.CharField(max_length=50, blank=True, null=True)
    
    # ============================================
    # NOTES & AUDIT
    # ============================================
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_units'
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='modified_units'
    )

    class Meta:
        unique_together = [
            ['tenant', 'imei_number'],
            ['tenant', 'serial_number'],
        ]
        ordering = ['product__sku_code', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'imei_number']),
            models.Index(fields=['tenant', 'serial_number']),
            models.Index(fields=['status']),
            models.Index(fields=['product', 'status']),
            models.Index(fields=['branch', 'status']),
            models.Index(fields=['current_owner', 'status']), 
        ]
        verbose_name = 'Product Unit'
        verbose_name_plural = 'Product Units'

    def save(self, *args, **kwargs):
        """Enhanced save with full sync support"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        branch_id = self.branch_id if self.branch_id else None
        
        # Track status changes for priority
        old_status = None
        if not is_new:
            try:
                old_instance = ProductUnit.objects.get(pk=self.pk)
                old_status = old_instance.status
                self._previous_data = {
                    'status': old_instance.status,
                    'branch_id': old_instance.branch_id,
                    'condition': old_instance.condition,
                    'current_owner_id': old_instance.current_owner_id,
                }
            except ProductUnit.DoesNotExist:
                self._previous_data = None
        
        # Existing validation
        if 'modified_by' in kwargs:
            self.last_modified_by = kwargs.pop('modified_by')
        if 'created_by' in kwargs and not self.pk:
            self.created_by = kwargs.pop('created_by')
        
        if not self.imei_number and not self.serial_number:
            if self.product.category.requires_unique_id:
                raise ValidationError("IMEI or Serial Number is required for this category")
        
        if self.imei_number:
            if len(self.imei_number) != 15:
                raise ValidationError("IMEI number must be exactly 15 digits")
            if not self.imei_number.isdigit():
                raise ValidationError("IMEI number must contain only digits")
        
        if not self.warranty_end and self.product.warranty_months:
            self.warranty_end = self.warranty_start + timedelta(days=self.product.warranty_months * 30)
        
        super().save(*args, **kwargs)
        
        # ✅ Enhanced sync queuing with priority based on status changes
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                # Determine priority
                priority = 5
                if self.status == 'sold':
                    priority = 9  # High priority - revenue tracking
                elif self.status == 'damaged' or self.status == 'stolen':
                    priority = 8  # High priority - loss tracking
                elif old_status and old_status != self.status:
                    priority = 7  # Status change is important
                
                # Branch transfer is high priority
                if branch_id and hasattr(self, 'transferred_from_branch_id') and self.transferred_from_branch_id:
                    priority = 8
                
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='ProductUnit',
                    object_id=str(self.id),
                    operation='CREATE' if is_new else 'UPDATE',
                    data={
                        'id': self.id,
                        'product_id': self.product_id,
                        'product_sku': self.product.sku_code,
                        'product_name': self.product.name,
                        'imei_number': self.imei_number,
                        'serial_number': self.serial_number,
                        'branch_id': branch_id,
                        'branch_name': self.branch.name if self.branch else None,
                        'status': self.status,
                        'condition': self.condition,
                        'unit_buying_price': str(self.unit_buying_price) if self.unit_buying_price else None,
                        'unit_selling_price': str(self.unit_selling_price) if self.unit_selling_price else None,
                        'best_price': str(self.best_price) if self.best_price else None,
                        'current_owner_id': self.current_owner_id,
                        'current_owner_name': self.current_owner.get_full_name() if self.current_owner else None,
                        'sold_at_price': str(self.sold_at_price) if self.sold_at_price else None,
                        'sold_date': self.sold_date.isoformat() if self.sold_date else None,
                        'sold_by_id': self.sold_by_id,
                        'warranty_end': self.warranty_end.isoformat() if self.warranty_end else None,
                        'is_in_warranty': self.is_in_warranty,
                        'tenant_id': tenant_id,
                        'previous_data': self._previous_data if hasattr(self, '_previous_data') else None,
                        'last_updated': self.updated_at.isoformat(),
                    },
                    priority=priority
                )
                logger.debug(f"✅ Queued ProductUnit sync: {self.unique_identifier} (Priority: {priority})")
            except Exception as e:
                logger.error(f"Failed to queue ProductUnit sync: {e}")
    
    @property
    def effective_buying_price(self):
        return self.unit_buying_price or self.product.buying_price
    
    @property
    def effective_selling_price(self):
        return self.unit_selling_price or self.product.selling_price
    
    @property
    def unique_identifier(self):
        if self.imei_number:
            return f"IMEI: {self.imei_number}"
        elif self.serial_number:
            return f"S/N: {self.serial_number}"
        return "No identifier"
    
    @property
    def is_in_warranty(self):
        """Check if product is still under warranty"""
        if not self.warranty_end:
            return False
        try:
            return timezone.now() < self.warranty_end
        except Exception:
            return False

    @property
    def warranty_remaining_days(self):
        """Get remaining warranty days"""
        if not self.warranty_end:
            return 0
        if not self.is_in_warranty:
            return 0
        try:
            remaining = self.warranty_end - timezone.now()
            return max(0, remaining.days)
        except Exception:
            return 0
    
    def mark_as_sold(self, price=None, sold_by=None):
        self.status = 'sold'
        self.sold_at_price = price or self.effective_selling_price
        self.sold_date = timezone.now()
        self.sold_by = sold_by
        self.save()
        self.product.update_quantities()
        return True
    
    def mark_as_available(self):
        self.status = 'available'
        self.sold_at_price = None
        self.sold_date = None
        self.save()
        self.product.update_quantities()
        return True
    
    def mark_as_reserved(self):
        self.status = 'reserved'
        self.save()
        self.product.update_quantities()
        return True
    
    def mark_as_damaged(self, notes=None, reported_by=None):
        self.status = 'damaged'
        if notes:
            self.notes = notes
        if reported_by:
            self.last_modified_by = reported_by
        self.save()
        self.product.update_quantities()
        return True
    
    def mark_as_stolen(self, reported_by, police_report=None, notes=None):
        self.status = 'stolen'
        self.loss_type = 'stolen'
        self.loss_reported_date = timezone.now()
        self.loss_reported_by = reported_by
        self.loss_notes = notes
        self.police_report_number = police_report
        self.save()
        self.product.update_quantities()
        return True
    
    def __str__(self):
        return f"{self.product.sku_code} - {self.unique_identifier}"


# ====================================
# BRANCH TRANSFER HISTORY 📦
# ====================================
class BranchTransfer(models.Model):
    """Track product unit transfers between branches"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_transit', 'In Transit'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='branch_transfers')
    product_unit = models.ForeignKey(ProductUnit, on_delete=models.CASCADE, related_name='branch_transfers')
    
    from_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='transfers_out')
    to_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='transfers_in')
    
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    transferred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='initiated_transfers'
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='received_transfers'
    )
    
    transfer_date = models.DateTimeField(auto_now_add=True)
    received_date = models.DateTimeField(null=True, blank=True)
    
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-transfer_date']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['from_branch', 'to_branch']),
            models.Index(fields=['tenant', 'status']),
        ]
        verbose_name = 'Branch Transfer'
        verbose_name_plural = 'Branch Transfers'
    
    def save(self, *args, **kwargs):
        """Queue branch transfers for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        super().save(*args, **kwargs)
        
        if getattr(settings, 'OFFLINE_MODE', False):
            SyncQueue.objects.create(
                tenant_id=tenant_id,
                model_name='BranchTransfer',
                object_id=str(self.id),
                operation='TRANSFER',
                data={
                    'id': self.id,
                    'product_unit_id': self.product_unit_id,
                    'product_sku': self.product_unit.product.sku_code,
                    'imei': self.product_unit.imei_number,
                    'serial': self.product_unit.serial_number,
                    'from_branch_id': self.from_branch_id,
                    'from_branch_name': self.from_branch.name,
                    'to_branch_id': self.to_branch_id,
                    'to_branch_name': self.to_branch.name,
                    'status': self.status,
                    'transferred_by_id': self.transferred_by_id,
                    'transfer_date': self.transfer_date.isoformat(),
                    'received_date': self.received_date.isoformat() if self.received_date else None,
                    'reason': self.reason,
                    'notes': self.notes,
                    'tenant_id': tenant_id,
                },
                priority=7  # High priority for transfers
            )
            logger.debug(f"✅ Queued BranchTransfer sync: {self.product_unit.unique_identifier}")
    

    def complete_transfer(self, received_by):
        """Override to add sync queue for completion"""
        self.status = 'completed'
        self.received_date = timezone.now()
        self.received_by = received_by
        self.save()
        
        self.product_unit.branch = self.to_branch
        self.product_unit.last_branch_transfer_date = self.received_date
        self.product_unit.transferred_from_branch = self.from_branch
        self.product_unit.save()
        
        # Queue the transfer completion
        if getattr(settings, 'OFFLINE_MODE', False):
            SyncQueue.objects.create(
                tenant_id=self.tenant_id,
                model_name='BranchTransfer',
                object_id=str(self.id),
                operation='UPDATE',
                data={
                    'id': self.id,
                    'status': 'completed',
                    'received_by_id': received_by.id,
                    'received_date': self.received_date.isoformat(),
                },
                priority=7
            )
    
    def __str__(self):
        return f"Transfer {self.product_unit.unique_identifier}: {self.from_branch.code} → {self.to_branch.code}"


# ====================================
# STOCK ENTRY MODEL 📦
# ====================================
class StockEntry(models.Model):
    """Tracks all inventory movements for BOTH single and bulk items"""
    
    ENTRY_TYPE_CHOICES = [
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('reversal', 'Reversal / Return'),
        ('adjustment', 'Manual Adjustment'),
        ('damage', 'Damaged Write-off'),
        ('theft', 'Theft/Loss'),
    ]

    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='stock_entries')
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_entries'
    )
    product_unit = models.ForeignKey(ProductUnit, on_delete=models.CASCADE, null=True, blank=True, related_name='stock_entries')
    product_sku = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name='stock_entries')
    
    quantity = models.IntegerField(help_text="Positive for stock IN, Negative for stock OUT")
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    
    reference_id = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='stock_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['entry_type']),
            models.Index(fields=['tenant', 'branch']),
            models.Index(fields=['product_sku', '-created_at']),
        ]
        verbose_name = 'Stock Entry'
        verbose_name_plural = 'Stock Entries'

    def save(self, *args, **kwargs):
        """Queue stock entries for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        if not self.total_amount and self.unit_price:
            self.total_amount = abs(self.quantity) * self.unit_price
        
        super().save(*args, **kwargs)
        
        # Update bulk quantities
        if self.product_sku and self.product_sku.category.is_bulk_item:
            total = StockEntry.objects.filter(product_sku=self.product_sku).aggregate(total=Sum('quantity'))['total'] or 0
            self.product_sku.bulk_quantity = max(0, total)
            self.product_sku.save(update_fields=['bulk_quantity', 'updated_at'])
        
        # ✅ Queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                # Priority based on entry type
                priority_map = {
                    'purchase': 7,
                    'sale': 8,  # High - revenue
                    'damage': 8,  # High - loss
                    'theft': 9,  # Critical - loss
                    'reversal': 6,
                    'adjustment': 5,
                }
                priority = priority_map.get(self.entry_type, 5)
                
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='StockEntry',
                    object_id=str(self.id),
                    operation='CREATE' if is_new else 'UPDATE',
                    data={
                        'id': self.id,
                        'product_unit_id': self.product_unit_id,
                        'product_sku_id': self.product_sku_id,
                        'product_sku': self.product_sku.sku_code if self.product_sku else None,
                        'product_name': self.product_sku.name if self.product_sku else None,
                        'quantity': self.quantity,
                        'entry_type': self.entry_type,
                        'unit_price': str(self.unit_price),
                        'total_amount': str(self.total_amount),
                        'branch_id': self.branch_id,
                        'branch_name': self.branch.name if self.branch else None,
                        'reference_id': self.reference_id,
                        'notes': self.notes,
                        'created_by_id': self.created_by_id,
                        'created_by_name': self.created_by.get_full_name() if self.created_by else None,
                        'created_at': self.created_at.isoformat(),
                        'tenant_id': tenant_id,
                    },
                    priority=priority
                )
                logger.debug(f"✅ Queued StockEntry sync: {self.entry_type} {abs(self.quantity)} units (Priority: {priority})")
            except Exception as e:
                logger.error(f"Failed to queue StockEntry sync: {e}")

    def __str__(self):
        direction = "IN" if self.quantity > 0 else "OUT"
        return f"{self.get_entry_type_display()} {direction} - {abs(self.quantity)} units"


# ====================================
# STOCK ALERT MODEL 📦
# ====================================
class StockAlert(models.Model):
    """Alert when products are running low or out of stock"""
    
    ALERT_TYPE_CHOICES = [
        ('lowstock', 'Low Stock'),
        ('needs_reorder', 'Needs Reorder'),
        ('outofstock', 'Out of Stock'),
    ]
    
    SEVERITY_CHOICES = [
        ('warning', 'Warning'),
        ('danger', 'Danger'),
        ('critical', 'Critical'),
    ]
    
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='stock_alerts')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    current_stock = models.PositiveIntegerField(default=0)
    threshold = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    is_dismissed = models.BooleanField(default=False)
    dismissed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    dismissed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-severity', '-created_at']
        indexes = [
            models.Index(fields=['tenant', 'product', 'is_active']),
            models.Index(fields=['alert_type']),
        ]
        verbose_name = 'Stock Alert'
        verbose_name_plural = 'Stock Alerts'
    
    def __str__(self):
        return f"{self.get_alert_type_display()}: {self.product.display_name}"
    
    def dismiss(self, user=None, reason=""):
        self.is_active = False
        self.is_dismissed = True
        self.dismissed_by = user
        self.dismissed_at = timezone.now()
        self.save()


# ====================================
# SIGNALS
# ====================================

@receiver([post_save, post_delete], sender=ProductUnit)
def update_product_quantities_from_units(sender, instance, **kwargs):
    if instance.product.category.is_single_item:
        instance.product.update_quantities()


@receiver(post_save, sender=Product)
def create_stock_alerts(sender, instance, created, **kwargs):
    try:
        if not instance.is_active or instance.is_discontinued:
            return
        
        current_stock = instance.current_stock
        alert_type = None
        severity = 'warning'
        
        if current_stock == 0:
            alert_type = 'outofstock'
            severity = 'critical'
        elif current_stock <= instance.reorder_level:
            alert_type = 'needs_reorder'
            severity = 'danger'
        elif current_stock <= 5:
            alert_type = 'lowstock'
            severity = 'warning'
        
        if alert_type:
            StockAlert.objects.update_or_create(
                tenant=instance.tenant,
                product=instance,
                is_dismissed=False,
                defaults={
                    'alert_type': alert_type,
                    'severity': severity,
                    'current_stock': current_stock,
                    'threshold': instance.reorder_level,
                    'is_active': True,
                }
            )
        else:
            StockAlert.objects.filter(
                tenant=instance.tenant,
                product=instance, 
                is_active=True
            ).update(is_active=False, is_dismissed=True)
    except Exception as e:
        logger.error(f"Error creating stock alert: {str(e)}")


@receiver(pre_save, sender=ProductUnit)
def validate_unit_identifiers(sender, instance, **kwargs):
    if instance.imei_number:
        existing = ProductUnit.objects.filter(
            tenant=instance.tenant,
            imei_number=instance.imei_number
        ).exclude(pk=instance.pk)
        if existing.exists():
            raise ValidationError(f"IMEI {instance.imei_number} already exists for this tenant")
    
    if instance.serial_number:
        existing = ProductUnit.objects.filter(
            tenant=instance.tenant,
            serial_number=instance.serial_number
        ).exclude(pk=instance.pk)
        if existing.exists():
            raise ValidationError(f"Serial {instance.serial_number} already exists for this tenant")


__all__ = [
    'Branch',
    'BranchStock',
    'Supplier',
    'Category', 
    'Product',
    'ProductUnit',
    'BranchTransfer', 
    'StockEntry',
    'StockAlert',
]