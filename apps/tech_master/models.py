# apps/tech_master/models.py - Fix the imports

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone  # ✅ Use Django's timezone
from decimal import Decimal
import logging
from datetime import timedelta  # ✅ Only import timedelta, not timezone
from apps.shared.tenants.models import Tenant
from apps.shared.users.models import User
from apps.shared.customers.models import Customer
from django.db.models import Sum, Count, Avg
from apps.shared.tenants.models import SyncQueue
from django.contrib.auth.hashers import check_password, make_password
from datetime import date  # ✅ For date.today()
from apps.shared.tenants.models import Tenant as CompanyTenant


User = settings.AUTH_USER_MODEL

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
        permissions = [
            # Product permissions
            ("can_view_product", "Can view products"),
            ("can_add_product", "Can add products"),
            ("can_edit_product", "Can edit products"),
            ("can_delete_product", "Can delete products"),
            ("can_manage_product", "Can manage products"),

            # Category permissions
            ("can_view_category", "Can view categories"),
            ("can_add_category", "Can add categories"),
            ("can_edit_category", "Can edit categories"),
            ("can_delete_category", "Can delete categories"),

            # Branch permissions
            ("can_view_branch", "Can view branches"),
            ("can_add_branch", "Can add branches"),
            ("can_edit_branch", "Can edit branches"),
            ("can_delete_branch", "Can delete branches"),
            ("can_manage_branch", "Can manage branches"),

            # Supplier permissions
            ("can_view_supplier", "Can view suppliers"),
            ("can_add_supplier", "Can add suppliers"),
            ("can_edit_supplier", "Can edit suppliers"),
            ("can_delete_supplier", "Can delete suppliers"),

            # Stock permissions
            ("can_view_stock", "Can view stock"),
            ("can_manage_stock", "Can manage stock"),
            ("can_adjust_stock", "Can adjust stock"),
            ("can_view_low_stock", "Can view low stock alerts"),

            # Sales permissions
            ("can_view_sale", "Can view sales"),
            ("can_create_sale", "Can create sales"),
            ("can_edit_sale", "Can edit sales"),
            ("can_delete_sale", "Can delete sales"),
            ("can_process_payment", "Can process payments"),
            ("can_view_receipt", "Can view receipts"),

            # Staff permissions
            ("can_view_staff", "Can view staff"),
            ("can_add_staff", "Can add staff"),
            ("can_edit_staff", "Can edit staff"),
            ("can_delete_staff", "Can delete staff"),
            ("can_manage_staff", "Can manage staff"),

            # Report permissions
            ("can_view_report", "Can view reports"),
            ("can_export_report", "Can export reports"),

            # Settings permissions
            ("can_view_settings", "Can view settings"),
            ("can_manage_settings", "Can manage settings"),
        ]



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
        from django.db import connection

        with transaction.atomic():
            # ✅ MySQL-compatible CAST - detect database type
            if connection.vendor == 'mysql':
                # MySQL: Use SIGNED (MySQL doesn't have INTEGER)
                last_product = Product.objects.filter(
                    tenant=self.tenant
                ).extra(
                    select={'sku_int': 'CAST(sku_code AS SIGNED)'}
                ).order_by('-sku_int').first()
            else:
                # SQLite/PostgreSQL: Use INTEGER
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



# ============================================
# INVOICE COUNTER - For sequential numbering
# ============================================

class InvoiceCounter(models.Model):
    """Counter for generating sequential invoice numbers per tenant"""
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='invoice_counter'
    )
    last_number = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Invoice Counter'
        verbose_name_plural = 'Invoice Counters'
        indexes = [
            models.Index(fields=['tenant']),
        ]

    def __str__(self):
        return f"{self.tenant.company_name} - {self.last_number}"

    @classmethod
    def get_next_number(cls, tenant):
        """Get the next invoice number for a tenant"""
        counter, created = cls.objects.get_or_create(tenant=tenant)
        counter.last_number += 1
        counter.save()
        return counter.last_number

    @classmethod
    def reset_counter(cls, tenant, start_from=0):
        """Reset the counter for a tenant (admin use only)"""
        counter, created = cls.objects.get_or_create(tenant=tenant)
        counter.last_number = start_from
        counter.save()
        return counter


# ============================================
# SALE MANAGER
# ============================================

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


# ============================================
# SALE MODEL
# ============================================

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
        ('reversed', 'Reversed'),
    ]

    objects = SaleManager()

    # Tenant & Branch
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='sales'
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales'
    )

    # Customer
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales'
    )
    customer_name = models.CharField(max_length=200, blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)

    # Invoice - Auto-generated sequential number
    invoice_no = models.CharField(max_length=50, unique=True, db_index=True)

    # Amounts
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
    cashier = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales'
    )
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

    def _generate_invoice_number(self):
        """
        Generate sequential invoice number per tenant using InvoiceCounter.
        Format: #000001, #000002, #000003, etc.
        """
        try:
            # ✅ Use the counter table for reliable sequential numbering
            next_number = InvoiceCounter.get_next_number(self.tenant)
            return f"#{next_number:06d}"
        except Exception as e:
            logger.error(f"Failed to generate invoice number: {e}")
            # Fallback: use timestamp-based number
            from datetime import datetime
            return f"#TMP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def save(self, *args, **kwargs):
        """Save sale and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id

        # ✅ Generate invoice number only for new sales
        if is_new and not self.invoice_no:
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


# ============================================
# SALE ITEM MODEL
# ============================================

class SaleItem(models.Model):
    """Sale items (line items)"""

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='sale_items'
    )
    product_unit = models.ForeignKey(
        ProductUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_items'
    )

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


# ============================================
# RETURN MODEL
# ============================================

class Return(models.Model):
    """Product returns model"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='returns'
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='returns'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='returns'
    )

    quantity = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    reason = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Approval
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_returns'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Audit
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_returns'
    )
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
        """Approve the return"""
        self.status = 'approved'
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save()

    def reject(self, approver):
        """Reject the return"""
        self.status = 'rejected'
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save()

    def complete(self):
        """Complete the return"""
        self.status = 'completed'
        self.save()


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
        from apps.tech_master.models import Sale
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
        from apps.tech_master.models import Sale
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




# ===============================================
#  STAFF MODELS
# ==============================================

class Staff(models.Model):
    """Tech Master Staff - Employees working in branches"""

    # ============================================
    # STAFF ROLES (Matching Food Master pattern)
    # ============================================
    ROLE_CHOICES = [
        ('manager', 'Manager'),
        ('cashier', 'Cashier'),
        ('sales_agent', 'Sales Agent'),
        ('stock_controller', 'Stock Controller'),
        ('technician', 'Technician'),
        ('cleaner', 'Cleaner'),
        ('other', 'Other'),
    ]

    # ============================================
    # RELATIONSHIPS
    # ============================================
    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='tech_staff')
    branch = models.ForeignKey(
        'Branch',
        on_delete=models.CASCADE,
        related_name='staff',
        null=True,
        blank=True
    )
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='tech_staff_profile',
        null=True,
        blank=True
    )

    # ============================================
    # STAFF DETAILS
    # ============================================
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cashier')
    pin = models.CharField(max_length=128, blank=True, null=True, help_text="4-digit PIN for POS access")
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    hire_date = models.DateField(null=True, blank=True)

    # ============================================
    # STATUS
    # ============================================
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Staff"
        indexes = [
            models.Index(fields=['tenant', 'branch']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_role_display()}"

    # ============================================
    # PIN METHODS (Matching Food Master pattern)
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
        # Check if pin is hashed or plain text (for backward compatibility)
        if self.pin.startswith('pbkdf2_sha256') or self.pin.startswith('bcrypt'):
            return check_password(raw_pin, self.pin)
        else:
            # Legacy plain text comparison
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
        from apps.tech_master.models import Sale
        if self.user:
            return Sale.objects.filter(
                cashier=self.user,
                status='completed'
            ).aggregate(total=models.Sum('total'))['total'] or Decimal('0.00')
        return Decimal('0.00')

    @property
    def total_orders(self):
        """Total orders processed by this staff member"""
        from apps.tech_master.models import Sale
        if self.user:
            return Sale.objects.filter(
                cashier=self.user,
                status='completed'
            ).count()
        return 0


class StaffAttendance(models.Model):
    """Tech Master Staff Attendance - Matching Food Master pattern"""

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
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='attendances')
    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='tech_staff_attendances')
    branch = models.ForeignKey('Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_attendances')

    # ============================================
    # ATTENDANCE DETAILS
    # ============================================
    date = models.DateField(default=date.today)
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
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_tech_attendances'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # ============================================
    # TIMESTAMPS
    # ============================================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Staff Attendance'
        verbose_name_plural = 'Staff Attendances'
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


class StaffLeave(models.Model):
    """Tech Master Staff Leave - Matching Food Master pattern"""

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
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='leaves')
    tenant = models.ForeignKey(CompanyTenant, on_delete=models.CASCADE, related_name='tech_staff_leaves')
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_tech_leaves'
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
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tech_leaves'
    )

    class Meta:
        verbose_name = 'Staff Leave'
        verbose_name_plural = 'Staff Leaves'
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

