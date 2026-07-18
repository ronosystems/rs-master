from django.contrib import admin
from .models import (
    ServiceCategory, Service, Vehicle, Booking,
    Employee, Inventory, Payment
)

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'is_active', 'service_count']
    list_filter = ['tenant', 'is_active']
    search_fields = ['name', 'description']

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'duration', 'is_active']
    list_filter = ['tenant', 'category', 'is_active']
    search_fields = ['name', 'description']

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['license_plate', 'customer_name', 'customer_phone', 'vehicle_type']
    list_filter = ['tenant', 'vehicle_type', 'is_active']
    search_fields = ['license_plate', 'customer_name', 'customer_phone']

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'vehicle', 'booking_date', 'total_amount', 'status']
    list_filter = ['tenant', 'status', 'booking_date']
    search_fields = ['vehicle__license_plate', 'vehicle__customer_name']

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'phone', 'hire_date', 'is_active']
    list_filter = ['tenant', 'role', 'is_active']
    search_fields = ['name', 'phone']

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'quantity', 'reorder_level', 'unit_price']
    list_filter = ['tenant', 'is_active', 'unit']
    search_fields = ['name', 'sku']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['booking', 'amount', 'payment_method', 'status', 'created_at']
    list_filter = ['tenant', 'payment_method', 'status']