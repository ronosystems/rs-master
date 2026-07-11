# apps/shared/permissions/models.py

from django.db import models
from django.contrib.auth.models import Permission as DjangoPermission
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SystemPermission(models.Model):
    """
    System-wide permissions that map to Django's permission system.
    These are the actual permissions stored in auth_permission table.
    """
    
    PERMISSION_ACTIONS = [
        ('view', 'View'),
        ('add', 'Add/Create'),
        ('change', 'Change/Edit'),
        ('delete', 'Delete'),
        ('manage', 'Manage/Full Control'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('print', 'Print'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('assign', 'Assign'),
        ('revoke', 'Revoke'),
    ]
    
    # Reference to Django's Permission
    django_permission = models.OneToOneField(
        DjangoPermission,
        on_delete=models.CASCADE,
        related_name='system_permission'
    )
    
    # Additional metadata
    action = models.CharField(max_length=20, choices=PERMISSION_ACTIONS)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # For grouping permissions
    category = models.CharField(max_length=50, blank=True, help_text="e.g., 'products', 'users', 'sales'")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'System Permission'
        verbose_name_plural = 'System Permissions'
        ordering = ['category', 'action']
        indexes = [
            models.Index(fields=['action']),
            models.Index(fields=['category']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.django_permission.name} ({self.get_action_display()})"
    
    @property
    def codename(self):
        return self.django_permission.codename
    
    @property
    def name(self):
        return self.django_permission.name
    
    @classmethod
    def create_from_django_permission(cls, django_perm):
        """Create SystemPermission from Django Permission"""
        # Extract action from codename
        action = 'manage'
        for act in cls.PERMISSION_ACTIONS:
            if django_perm.codename.startswith(f"{act[0]}_"):
                action = act[0]
                break
        
        return cls.objects.create(
            django_permission=django_perm,
            action=action,
            description=f"Allows {action} on {django_perm.content_type.model}",
        )


class Role(models.Model):
    """Custom Role model with permissions"""
    
    ROLE_TYPES = [
        ('system', 'System Role'),
        ('custom', 'Custom Role'),
    ]
    
    project_types = models.ManyToManyField(
        'tenants.ProjectType',
        related_name='roles',
        blank=True,
        help_text="Project types this role is applicable to (leave blank for all)"
    )

    name = models.CharField(max_length=100, unique=True)
    codename = models.CharField(max_length=100, unique=True)
    role_type = models.CharField(max_length=20, choices=ROLE_TYPES, default='custom')
    
    # Django permissions
    permissions = models.ManyToManyField(
        DjangoPermission,
        related_name='custom_roles',
        blank=True
    )
    
    # Users with this role
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='custom_roles',
        blank=True
    )
    
    # Parent role for inheritance
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children'
    )
    
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_system_role = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        indexes = [
            models.Index(fields=['codename']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_role_type_display()})"
    
    def get_all_permissions(self):
        """Get all permissions including inherited from parent"""
        permissions = set(self.permissions.all())
        if self.parent:
            permissions.update(self.parent.get_all_permissions())
        return permissions
    
    def has_permission(self, codename):
        """Check if role has a specific permission"""
        return self.get_all_permissions().filter(codename=codename).exists()
    
    def get_permission_codenames(self):
        """Get list of permission codenames"""
        return list(self.get_all_permissions().values_list('codename', flat=True))
    
    def get_permission_list(self):
        """Get all permissions as a list (for API responses)"""
        return list(self.get_all_permissions())
    
    def to_dict(self):
        """Convert to dictionary for API"""
        return {
            'id': self.id,
            'name': self.name,
            'codename': self.codename,
            'role_type': self.role_type,
            'permissions': list(self.get_all_permissions().values('id', 'codename', 'name')),
            'user_count': self.users.count(),
            'is_active': self.is_active,
            'is_system_role': self.is_system_role,
        }


class UserRoleAssignment(models.Model):
    """Track user role assignments"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='role_assignments'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_roles'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-assigned_at']
        verbose_name = 'User Role Assignment'
        verbose_name_plural = 'User Role Assignments'
        unique_together = ['user', 'role']
    
    def __str__(self):
        return f"{self.user.username} - {self.role.name}"