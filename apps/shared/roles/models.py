# apps/shared/roles/models.py

from django.db import models
from django.conf import settings

class ProjectRole(models.Model):
    """
    Project-specific roles created by Company Admin
    """
    
    PROJECT_CHOICES = [
        ('tronic_master', 'Tech Master'),
        ('food_master', 'Food Master'),
        ('hotel_master', 'Hotel Master'),
        ('retail_master', 'Retail Master'),
        ('health_master', 'Health Master'),
        ('fashion_master', 'Fashion Master'),
        ('rental_master', 'Rental_Master')
    ]
    
    # Which company owns this role
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='project_roles')
    
    # Which project this role belongs to
    project_type = models.CharField(max_length=20, choices=PROJECT_CHOICES, default='tronic_master')
    
    # Role details
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # ✅ Simple ManyToMany WITHOUT through model
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='project_roles',
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
        related_name='created_roles'
    )
    
    class Meta:
        unique_together = [['tenant', 'project_type', 'name']]
        ordering = ['tenant', 'project_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_project_type_display()})"
    
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