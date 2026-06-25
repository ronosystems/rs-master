# apps/shared/customers/admin.py

from django.contrib import admin
from django.contrib.auth.models import AbstractUser
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Customer Admin - Shared across ALL projects"""
    
    list_display = [
        'name', 
        'phone', 
        'email', 
        'tenant', 
        'total_spent', 
        'loyalty_points', 
        'created_at'
    ]
    
    list_filter = ['tenant']
    search_fields = ['name', 'phone', 'email', 'id_number']
    list_per_page = 25
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('name', 'phone', 'email', 'address', 'id_number')
        }),
        ('Next of Kin', {
            'fields': ('next_of_kin_name', 'next_of_kin_phone', 'next_of_kin_relationship'),
            'classes': ('collapse',)
        }),
        ('Stats', {
            'fields': ('total_spent', 'loyalty_points')
        }),
        ('Metadata', {
            'fields': ('tenant', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        """Filter customers by tenant"""
        qs = super().get_queryset(request)
        
        # Super Admin sees all
        if request.user.is_superuser:
            return qs
        
        # ✅ Fix: Use getattr to safely access tenant
        tenant = getattr(request.user, 'tenant', None)
        if tenant:
            return qs.filter(tenant=tenant)
        
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        """Auto-set created_by and tenant"""
        if not change:
            obj.created_by = request.user
            # ✅ Fix: Use getattr to safely access tenant
            tenant = getattr(request.user, 'tenant', None)
            if tenant:
                obj.tenant = tenant
        super().save_model(request, obj, form, change)