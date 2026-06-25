# apps/tech_master/inventory/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Branch,
    BranchStock,
    Supplier,
    Category,
    Product,
    ProductUnit,
    BranchTransfer,
    StockEntry,
    StockAlert
)

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    """Branch Admin"""
    list_display = ['name', 'code', 'branch_type', 'is_main_branch', 'is_active', 'phone', 'email']
    list_filter = ['branch_type', 'is_main_branch', 'is_active', 'tenant']
    search_fields = ['name', 'code', 'address', 'city', 'phone', 'email']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'code', 'branch_type', 'is_main_branch')
        }),
        ('Contact Information', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code', 'phone', 'email')
        }),
        ('Operational Hours', {
            'fields': ('opening_time', 'closing_time', 'is_24_hours')
        }),
        ('Additional Info', {
            'fields': ('manager_name', 'notes', 'is_active')
        }),
        ('Coordinates', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_by', 'last_modified_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """Supplier Admin"""
    list_display = ['name', 'contact_person', 'phone', 'email', 'product_count', 'is_active']
    list_filter = ['is_active', 'tenant']
    search_fields = ['name', 'contact_person', 'phone', 'email']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'contact_person', 'phone', 'email')
        }),
        ('Address & Tax', {
            'fields': ('address', 'tax_id', 'payment_terms')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    @admin.display(description='Products')
    def product_count(self, obj):
        count = obj.products.count()
        return format_html('<span class="badge bg-primary">{}</span>', count)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Category Admin"""
    list_display = ['name', 'category_code', 'item_type', 'identifier_type', 'product_count', 'is_active']
    list_filter = ['item_type', 'identifier_type', 'is_active', 'tenant']
    search_fields = ['name', 'category_code', 'description']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'name', 'category_code', 'item_type', 'identifier_type')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    @admin.display(description='Products')
    def product_count(self, obj):
        count = obj.products.count()
        return format_html('<span class="badge bg-primary">{}</span>', count)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Product Admin"""
    list_display = ['sku_code', 'name', 'brand', 'model', 'category', 'selling_price', 'available_quantity', 'is_active']
    list_filter = ['category', 'brand', 'is_active', 'is_discontinued', 'tenant']
    search_fields = ['sku_code', 'name', 'brand', 'model', 'barcode']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'branch', 'sku_code', 'barcode', 'name', 'brand', 'model', 'category')
        }),
        ('Specifications', {
            'fields': ('specifications',)
        }),
        ('Pricing', {
            'fields': ('buying_price', 'selling_price', 'best_price')
        }),
        ('Stock Management', {
            'fields': ('total_quantity', 'available_quantity', 'reserved_quantity', 'damaged_quantity', 'bulk_quantity')
        }),
        ('Supplier & Reorder', {
            'fields': ('supplier', 'reorder_level', 'last_restocked', 'warranty_months')
        }),
        ('Image', {
            'fields': ('image',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_discontinued', 'description')
        }),
        ('Audit', {
            'fields': ('created_by', 'last_modified_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()


@admin.register(ProductUnit)
class ProductUnitAdmin(admin.ModelAdmin):
    """Product Unit Admin"""
    list_display = ['product', 'imei_number', 'serial_number', 'status', 'condition', 'branch', 'current_owner']
    list_filter = ['status', 'condition', 'tenant', 'branch']
    search_fields = ['imei_number', 'serial_number', 'product__name', 'product__sku_code']
    
    fieldsets = (
        ('Product Information', {
            'fields': ('tenant', 'product', 'branch')
        }),
        ('Unique Identifiers', {
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
        ('Location', {
            'fields': ('warehouse_location', 'shelf_location')
        }),
        ('Theft/Loss', {
            'fields': ('loss_type', 'loss_reported_date', 'loss_reported_by', 'loss_notes', 'police_report_number'),
            'classes': ('collapse',)
        }),
        ('Insurance', {
            'fields': ('insurance_claim_filed', 'insurance_claim_number', 'insurance_claim_amount', 'insurance_payout_amount', 'insurance_payout_date'),
            'classes': ('collapse',)
        }),
        ('Recovery', {
            'fields': ('recovered_date', 'recovered_by', 'recovery_notes'),
            'classes': ('collapse',)
        }),
        ('Notes & Audit', {
            'fields': ('notes', 'created_by', 'last_modified_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()


@admin.register(BranchTransfer)
class BranchTransferAdmin(admin.ModelAdmin):
    """Branch Transfer Admin"""
    list_display = ['product_unit', 'from_branch', 'to_branch', 'status', 'transfer_date']
    list_filter = ['status', 'tenant']
    search_fields = ['product_unit__imei_number', 'product_unit__serial_number']
    
    fieldsets = (
        ('Transfer Details', {
            'fields': ('tenant', 'product_unit', 'from_branch', 'to_branch', 'quantity', 'status')
        }),
        ('Transfer Information', {
            'fields': ('transferred_by', 'received_by', 'transfer_date', 'received_date')
        }),
        ('Notes', {
            'fields': ('reason', 'notes')
        }),
    )
    readonly_fields = ['transfer_date']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()


@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    """Stock Entry Admin"""
    list_display = ['entry_type', 'product_sku', 'product_unit', 'quantity', 'unit_price', 'total_amount', 'created_at']
    list_filter = ['entry_type', 'tenant']
    search_fields = ['product_sku__name', 'product_sku__sku_code', 'product_unit__imei_number']
    
    fieldsets = (
        ('Entry Details', {
            'fields': ('tenant', 'branch', 'product_sku', 'product_unit', 'entry_type', 'quantity')
        }),
        ('Pricing', {
            'fields': ('unit_price', 'total_amount')
        }),
        ('Reference', {
            'fields': ('reference_id', 'notes')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    """Stock Alert Admin"""
    list_display = ['product', 'alert_type', 'severity_badge', 'current_stock', 'threshold', 'is_active']
    list_filter = ['alert_type', 'severity', 'is_active', 'tenant']
    search_fields = ['product__name', 'product__sku_code']
    
    fieldsets = (
        ('Alert Details', {
            'fields': ('tenant', 'product', 'alert_type', 'severity')
        }),
        ('Stock Information', {
            'fields': ('current_stock', 'threshold')
        }),
        ('Status', {
            'fields': ('is_active', 'is_dismissed', 'dismissed_by', 'dismissed_at')
        }),
        ('Audit', {
            'fields': ('created_at',)
        }),
    )
    readonly_fields = ['created_at']
    
    @admin.display(description='Severity')
    def severity_badge(self, obj):
        """Display severity as colored badge"""
        colors = {
            'warning': 'warning',
            'danger': 'danger',
            'critical': 'danger',
        }
        color = colors.get(obj.severity, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_severity_display()
        )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()


@admin.register(BranchStock)
class BranchStockAdmin(admin.ModelAdmin):
    """Branch Stock Admin"""
    list_display = ['branch', 'product', 'quantity', 'updated_at']
    list_filter = ['branch', 'tenant']
    search_fields = ['product__name', 'product__sku_code']
    
    fieldsets = (
        ('Stock Details', {
            'fields': ('tenant', 'branch', 'product', 'quantity')
        }),
        ('Timestamps', {
            'fields': ('updated_at',)
        }),
    )
    readonly_fields = ['updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()