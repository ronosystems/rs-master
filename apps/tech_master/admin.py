# apps/tech_master/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.contrib.admin import SimpleListFilter
from .models import (
    Branch, BranchStock, Supplier, Category, Product, ProductUnit,
    BranchTransfer, StockEntry, StockAlert,
    InvoiceCounter, Sale, SaleItem, Return,
    CashDrawer, CashTransaction,
    Staff, StaffAttendance, StaffLeave
)

# ============================================
# CUSTOM FILTERS
# ============================================

class LowStockFilter(SimpleListFilter):
    title = _('Stock Status')
    parameter_name = 'stock_status'
    
    def lookups(self, request, model_admin):
        return (
            ('low', _('Low Stock')),
            ('out', _('Out of Stock')),
            ('available', _('Available')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(available_quantity__lte=5, available_quantity__gt=0)
        if self.value() == 'out':
            return queryset.filter(available_quantity=0)
        if self.value() == 'available':
            return queryset.filter(available_quantity__gt=0)
        return queryset

# ============================================
# BRANCH ADMIN
# ============================================

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'tenant', 'branch_type', 'is_main_branch', 'is_active', 'city', 'phone']
    list_filter = ['tenant', 'branch_type', 'is_active', 'is_main_branch']
    search_fields = ['name', 'code', 'city', 'address', 'phone', 'email']
    readonly_fields = ['created_at', 'updated_at', 'product_count', 'unit_count', 'available_unit_count']
    list_editable = ['is_active']
    fieldsets = (
        ('Tenant Information', {
            'fields': ('tenant',)
        }),
        ('Branch Information', {
            'fields': ('name', 'code', 'branch_type', 'is_main_branch')
        }),
        ('Contact Details', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code', 'phone', 'email')
        }),
        ('Manager & Operations', {
            'fields': ('manager_name', 'opening_time', 'closing_time', 'is_24_hours')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude')
        }),
        ('Status', {
            'fields': ('is_active', 'notes')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at', 'created_by', 'last_modified_by')
        }),
    )
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Total Products'
    
    def unit_count(self, obj):
        return obj.product_units.count()
    unit_count.short_description = 'Total Units'
    
    def available_unit_count(self, obj):
        return obj.product_units.filter(status='available').count()
    available_unit_count.short_description = 'Available Units'

# ============================================
# SUPPLIER ADMIN
# ============================================

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'phone', 'email', 'is_active', 'product_count']
    list_filter = ['tenant', 'is_active']
    search_fields = ['name', 'contact_person', 'phone', 'email', 'tax_id']
    list_editable = ['is_active']
    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Supplier Details', {
            'fields': ('name', 'contact_person', 'phone', 'email', 'address')
        }),
        ('Financial', {
            'fields': ('tax_id', 'payment_terms')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'

# ============================================
# CATEGORY ADMIN
# ============================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_code', 'tenant', 'item_type', 'identifier_type', 'is_active']
    list_filter = ['tenant', 'item_type', 'identifier_type', 'is_active']
    search_fields = ['name', 'category_code', 'description']
    list_editable = ['is_active']
    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Category Information', {
            'fields': ('name', 'category_code', 'description', 'item_type', 'identifier_type')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

# ============================================
# PRODUCT ADMIN
# ============================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'sku_code', 'name', 'tenant', 'category', 'brand', 'model',
        'price_display', 'available_quantity', 'stock_status', 'is_active'
    ]
    list_filter = ['tenant', 'category', 'brand', 'is_active', 'is_discontinued', LowStockFilter]
    search_fields = ['sku_code', 'name', 'brand', 'model', 'barcode']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at', 'total_quantity', 'available_quantity', 'reserved_quantity', 'damaged_quantity']
    list_per_page = 50
    
    fieldsets = (
        ('Tenant & Branch', {
            'fields': ('tenant', 'branch')
        }),
        ('SKU & Identification', {
            'fields': ('sku_code', 'barcode', 'category')
        }),
        ('Product Details', {
            'fields': ('name', 'brand', 'model', 'specifications', 'description')
        }),
        ('Pricing', {
            'fields': ('buying_price', 'selling_price', 'best_price')
        }),
        ('Stock Management', {
            'fields': ('total_quantity', 'available_quantity', 'reserved_quantity', 'damaged_quantity', 'reorder_level')
        }),
        ('Supplier & Warranty', {
            'fields': ('supplier', 'warranty_months')
        }),
        ('Images', {
            'fields': ('image',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_discontinued')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at', 'created_by', 'last_modified_by')
        }),
    )
    
    def price_display(self, obj):
        return f"Kes {obj.selling_price}"
    price_display.short_description = 'Price'
    
    def stock_status(self, obj):
        if obj.available_quantity <= 0:
            return format_html('<span style="color: red;">Out of Stock</span>')
        elif obj.available_quantity <= obj.reorder_level:
            return format_html('<span style="color: orange;">Low Stock</span>')
        else:
            return format_html('<span style="color: green;">In Stock</span>')
    stock_status.short_description = 'Stock Status'

# ============================================
# PRODUCT UNIT ADMIN
# ============================================

@admin.register(ProductUnit)
class ProductUnitAdmin(admin.ModelAdmin):
    list_display = [
        'unique_id_display', 'product', 'tenant', 'branch', 'status', 
        'condition', 'current_owner', 'price_display', 'is_in_warranty_display'
    ]
    list_filter = ['tenant', 'status', 'condition', 'product__category', 'branch']
    search_fields = ['imei_number', 'serial_number', 'product__sku_code', 'product__name']
    readonly_fields = ['created_at', 'updated_at', 'assigned_date', 'sold_date']
    list_editable = ['status']
    list_per_page = 50
    
    fieldsets = (
        ('Tenant & Product', {
            'fields': ('tenant', 'product', 'branch')
        }),
        ('Identification', {
            'fields': ('imei_number', 'serial_number')
        }),
        ('Pricing', {
            'fields': ('unit_buying_price', 'unit_selling_price', 'best_price')
        }),
        ('Ownership', {
            'fields': ('current_owner', 'assigned_date', 'assigned_by')
        }),
        ('Status & Condition', {
            'fields': ('status', 'condition')
        }),
        ('Sales Information', {
            'fields': ('sold_at_price', 'sold_date', 'sold_by')
        }),
        ('Purchase & Warranty', {
            'fields': ('purchase_date', 'supplier', 'purchase_price', 'warranty_start', 'warranty_end')
        }),
        ('Loss/Theft', {
            'fields': ('loss_type', 'loss_reported_date', 'loss_reported_by', 'loss_notes', 'police_report_number')
        }),
        ('Insurance', {
            'fields': ('insurance_claim_filed', 'insurance_claim_number', 'insurance_claim_amount', 
                      'insurance_payout_amount', 'insurance_payout_date')
        }),
        ('Recovery', {
            'fields': ('recovered_date', 'recovered_by', 'recovery_notes')
        }),
        ('Location', {
            'fields': ('warehouse_location', 'shelf_location')
        }),
        ('Notes & Audit', {
            'fields': ('notes', 'created_at', 'updated_at', 'created_by', 'last_modified_by')
        }),
    )
    
    def unique_id_display(self, obj):
        if obj.imei_number:
            return f"IMEI: {obj.imei_number}"
        elif obj.serial_number:
            return f"S/N: {obj.serial_number}"
        return "No ID"
    unique_id_display.short_description = 'Unique ID'
    
    def price_display(self, obj):
        price = obj.unit_selling_price or obj.product.selling_price
        return f"Kes {price}" if price else '-'
    price_display.short_description = 'Price'
    
    def is_in_warranty_display(self, obj):
        if obj.is_in_warranty:
            return format_html('<span style="color: green;">✓ In Warranty</span>')
        return format_html('<span style="color: red;">✗ Expired</span>')
    is_in_warranty_display.short_description = 'Warranty'

# ============================================
# BRANCH TRANSFER ADMIN
# ============================================

@admin.register(BranchTransfer)
class BranchTransferAdmin(admin.ModelAdmin):
    list_display = ['product_display', 'from_branch', 'to_branch', 'status', 'transferred_by', 'transfer_date']
    list_filter = ['status', 'from_branch', 'to_branch', 'transfer_date']
    search_fields = ['product_unit__imei_number', 'product_unit__serial_number', 'product_unit__product__name']
    readonly_fields = ['transfer_date']
    list_editable = ['status']
    
    def product_display(self, obj):
        return obj.product_unit.unique_identifier
    product_display.short_description = 'Product'

# ============================================
# SALE ADMIN
# ============================================

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['invoice_no', 'customer_display', 'total', 'payment_method', 'status', 'cashier', 'created_at']
    list_filter = ['tenant', 'status', 'payment_method', 'created_at']
    search_fields = ['invoice_no', 'customer__name', 'customer_phone', 'customer_name']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 50
    
    fieldsets = (
        ('Sale Information', {
            'fields': ('tenant', 'branch', 'invoice_no')
        }),
        ('Customer', {
            'fields': ('customer', 'customer_name', 'customer_phone')
        }),
        ('Financial', {
            'fields': ('subtotal', 'tax', 'discount', 'total')
        }),
        ('Payment', {
            'fields': ('payment_method', 'payment_status', 'tax_inclusive')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Audit', {
            'fields': ('cashier', 'created_at', 'updated_at')
        }),
    )
    
    def customer_display(self, obj):
        if obj.customer:
            return obj.customer.name
        return obj.customer_name or 'Walk-in'
    customer_display.short_description = 'Customer'

# ============================================
# SALE ITEM ADMIN
# ============================================

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'product', 'quantity', 'price', 'subtotal']
    list_filter = ['sale__tenant']
    search_fields = ['product__name', 'product__sku_code']

# ============================================
# STOCK ENTRY ADMIN
# ============================================

@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = ['product_display', 'quantity', 'entry_type', 'unit_price', 'total_amount', 'created_at']
    list_filter = ['tenant', 'entry_type', 'branch', 'created_at']
    search_fields = ['product_sku__sku_code', 'product_sku__name', 'notes']
    readonly_fields = ['created_at']
    list_editable = ['entry_type']
    
    def product_display(self, obj):
        if obj.product_sku:
            return obj.product_sku.display_name
        elif obj.product_unit:
            return obj.product_unit.unique_identifier
        return '-'
    product_display.short_description = 'Product'

# ============================================
# STOCK ALERT ADMIN
# ============================================

@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ['product', 'alert_type', 'severity', 'current_stock', 'threshold', 'is_active', 'created_at']
    list_filter = ['tenant', 'alert_type', 'severity', 'is_active']
    search_fields = ['product__name', 'product__sku_code']
    list_editable = ['is_active']

# ============================================
# RETURN ADMIN
# ============================================

@admin.register(Return)
class ReturnAdmin(admin.ModelAdmin):
    list_display = ['id', 'sale', 'product', 'quantity', 'amount', 'status', 'created_at']
    list_filter = ['tenant', 'status', 'created_at']
    search_fields = ['sale__invoice_no', 'product__name', 'reason']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status']

# ============================================
# CASH DRAWER ADMIN
# ============================================

@admin.register(CashDrawer)
class CashDrawerAdmin(admin.ModelAdmin):
    list_display = ['id', 'cashier', 'branch', 'opening_amount', 'closing_amount', 'is_open', 'opened_at']
    list_filter = ['tenant', 'is_open', 'opened_at']
    search_fields = ['cashier__username', 'cashier__first_name', 'cashier__last_name']
    readonly_fields = ['opened_at', 'closed_at']

# ============================================
# CASH TRANSACTION ADMIN
# ============================================

@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
    list_display = ['drawer', 'amount', 'transaction_type', 'reason', 'created_by', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['reason', 'created_by__username']
    readonly_fields = ['created_at']

# ============================================
# STAFF ADMIN
# ============================================

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'tenant', 'branch', 'phone_number', 'is_active', 'pin_set']
    list_filter = ['tenant', 'role', 'is_active', 'branch']
    search_fields = ['name', 'email', 'phone_number']
    list_editable = ['is_active']
    
    def pin_set(self, obj):
        return bool(obj.pin)
    pin_set.boolean = True
    pin_set.short_description = 'PIN Set'

# ============================================
# STAFF ATTENDANCE ADMIN
# ============================================

@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = ['staff', 'date', 'status', 'check_in_time', 'check_out_time', 'hours_worked']
    list_filter = ['tenant', 'status', 'date']
    search_fields = ['staff__name']
    list_editable = ['status']

# ============================================
# STAFF LEAVE ADMIN
# ============================================

@admin.register(StaffLeave)
class StaffLeaveAdmin(admin.ModelAdmin):
    list_display = ['staff', 'leave_type', 'start_date', 'end_date', 'days', 'status']
    list_filter = ['tenant', 'status', 'leave_type']
    search_fields = ['staff__name', 'reason']
    list_editable = ['status']
    
    def days(self, obj):
        return obj.days
    days.short_description = 'Days'

# ============================================
# CUSTOM ADMIN SITE
# ============================================

class TechMasterAdminSite(admin.AdminSite):
    site_header = 'Tech Master Administration'
    site_title = 'Tech Master Admin'
    index_title = 'Tech Master Dashboard'
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            # Add custom admin views here
        ]
        return custom_urls + urls

# ============================================
# INLINE ADMIN FOR SALE ITEMS
# ============================================

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    fields = ['product', 'product_unit', 'quantity', 'price', 'subtotal']
    readonly_fields = ['subtotal']

# Update SaleAdmin to include inline items
SaleAdmin.inlines = [SaleItemInline]

# ============================================
# INLINE ADMIN FOR PRODUCT UNITS
# ============================================

class ProductUnitInline(admin.TabularInline):
    model = ProductUnit
    extra = 1
    fields = ['imei_number', 'serial_number', 'status', 'condition', 'unit_selling_price']
    readonly_fields = ['created_at']

# Update ProductAdmin to include inline units
ProductAdmin.inlines = [ProductUnitInline]

print("✅ Tech Master Admin registered successfully!")