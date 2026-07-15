# apps/shared/users/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DefaultUserManager
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class UserManager(DefaultUserManager):
    """Custom manager for User model"""
    
    use_in_migrations = True
    
    def get_tenant_users(self, tenant):
        """Get all users for a tenant"""
        return self.filter(tenant=tenant, is_active=True)
    
    def get_tenant_admins(self, tenant):
        """Get all tenant admins"""
        return self.filter(tenant=tenant, role='admin', is_active=True)
    
    def get_super_admins(self):
        """Get all super admins"""
        return self.filter(role='super_admin', is_active=True)
    
    def get_active_users_count(self, tenant):
        """Get count of active users for a tenant"""
        return self.filter(tenant=tenant, is_active=True).count()


class User(AbstractUser):
    """Custom User Model - System Roles Only"""
    
    # ============================================
    # SYSTEM ROLES - ONLY 3!
    # ============================================
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),    # Platform owner - Full system access
        ('admin', 'Admin'),                 # Company owner - Full company access
        ('user', 'User'),                   # Regular user - No system-level permissions
    ]
    
    ROLE_DISPLAY = {
        'super_admin': 'Super Admin',
        'admin': 'Admin',
        'user': 'User',
    }
    
    objects = UserManager()
    
    # ============================================
    # FIELDS
    # ============================================
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users',
        help_text="Tenant this user belongs to"
    )
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='user'
    )
    
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="User's phone number"
    )

    # ✅ Add branch field
    branch = models.ForeignKey(
        'tronic_master.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text="Branch this user is assigned to"
    )
    
    # ✅ Add hire_date field
    hire_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when the user was hired"
    )

    # ✅ Add PIN field back
    pin_code = models.CharField(
        max_length=6,
        blank=True,
        help_text="4-6 digit PIN for POS access"
    )
    
    require_pin_for_pos = models.BooleanField(
        default=True,
        help_text="Require PIN verification before accessing POS"
    )
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta(AbstractUser.Meta):
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['tenant', 'role']),
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        role_display = self.ROLE_DISPLAY.get(self.role, self.role)
        return f"{self.username} ({role_display})"
    
    # ============================================
    # PROPERTIES
    # ============================================
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username
    
    @property
    def role_display(self):
        return self.ROLE_DISPLAY.get(self.role, self.role)
    
    @property
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    @property
    def is_tenant_admin(self):
        return self.role == 'admin'
    
    @property
    def is_regular_user(self):
        return self.role == 'user'
    
    
    @property
    def has_tenant(self):
        return self.tenant is not None
    
    # ============================================
    # PERMISSION METHODS
    # ============================================
    
    def has_permission(self, codename):
        """Check if user has a specific permission"""
        # Super admin has all permissions
        if self.is_super_admin:
            return True
        
        # Admin has all permissions for their tenant
        if self.is_tenant_admin:
            return True
        
        # Regular users - check custom roles from permissions app
        from apps.shared.permissions.models import Role
        roles = Role.objects.filter(users=self, is_active=True)
        for role in roles:
            if role.has_permission(codename):
                return True
        
        return False
    
    def can_view(self, model_name):
        return self.has_permission(f'view_{model_name}')
    
    def can_add(self, model_name):
        return self.has_permission(f'add_{model_name}')
    
    def can_change(self, model_name):
        return self.has_permission(f'change_{model_name}')
    
    def can_delete(self, model_name):
        return self.has_permission(f'delete_{model_name}')
    
    def can_manage(self, model_name):
        return self.has_permission(f'manage_{model_name}')


    def check_pin(self, pin):
        """Verify if the provided PIN matches"""
        if not self.pin_code:
            return False
        if not pin:
            return False
        return self.pin_code == pin
    
    def set_pin(self, pin):
        """Set a new PIN"""
        if pin and len(pin) >= 4:
            self.pin_code = pin
            return True
        return False
    
    def has_pin(self):
        """Check if user has a PIN set"""
        return bool(self.pin_code)




# ============================================
# USER ACTIVITY LOG
# ============================================

class UserActivityLog(models.Model):
    """Track user activities for audit"""
    
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('sale', 'Sale Created'),
        ('return', 'Return Created'),
        ('stock_update', 'Stock Updated'),
        ('user_created', 'User Created'),
        ('user_updated', 'User Updated'),
        ('user_deleted', 'User Deleted'),
        ('password_change', 'Password Changed'),
        ('pin_change', 'PIN Changed'),
        ('role_change', 'Role Changed'),
        ('tenant_switch', 'Tenant Switched'),
        ('project_role_change', 'Project Role Changed'),  # ✅ New action type
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='user_activities'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['tenant', 'action']),
            models.Index(fields=['created_at']),
            models.Index(fields=['tenant', 'created_at']),
        ]
        verbose_name = 'User Activity Log'
        verbose_name_plural = 'User Activity Logs'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def log_activity(cls, user, action, details=None, request=None):
        """Helper method to log user activity"""
        if details is None:
            details = {}
        
        ip_address = None
        user_agent = ''
        
        if request:
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        return cls.objects.create(
            tenant=user.tenant,
            user=user,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )