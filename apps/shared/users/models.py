# apps/shared/users/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DefaultUserManager
from django.conf import settings
from django.utils import timezone
import logging

# ✅ Import for sync queue
from apps.shared.tenants.models import SyncQueue

logger = logging.getLogger(__name__)


class UserManager(DefaultUserManager):
    """Custom manager for User model extending Django's default UserManager"""
    
    use_in_migrations = True
    
    def get_tenant_users(self, tenant):
        """Get all users for a tenant"""
        return self.filter(tenant=tenant, is_active=True)
    
    def get_by_role(self, tenant, role):
        """Get users by role for a tenant"""
        return self.filter(tenant=tenant, role=role, is_active=True)
    
    def get_sales_agents(self, tenant):
        """Get all sales agents for a tenant"""
        return self.filter(tenant=tenant, role='sales_agent', is_active=True)
    
    def get_cashiers(self, tenant):
        """Get all cashiers for a tenant"""
        return self.filter(tenant=tenant, role='cashier', is_active=True)
    
    def get_managers(self, tenant):
        """Get all managers for a tenant"""
        return self.filter(tenant=tenant, role='manager', is_active=True)
    
    def get_tenant_admins(self, tenant):
        """Get all tenant admins for a tenant"""
        return self.filter(tenant=tenant, role='admin', is_active=True)
    
    def get_active_users_count(self, tenant):
        """Get count of active users for a tenant"""
        return self.filter(tenant=tenant, is_active=True).count()
    
    def get_users_without_pin(self, tenant):
        """Get users without PIN set"""
        return self.filter(
            tenant=tenant,
            is_active=True,
            require_pin_for_pos=True,
            pin_code=''
        )
    
    def get_users_by_project_type(self, project_type_code):
        """Get users by project type"""
        return self.filter(
            tenant__project_type__code__iexact=project_type_code,
            is_active=True
        )


class User(AbstractUser):
    """Custom User Model with Roles"""
    
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Tenant Admin'),
        ('manager', 'Manager'),
        ('cashier', 'Cashier'),
        ('sales_agent', 'Sales Agent'),
    ]
    
    ROLE_DISPLAY = {
        'super_admin': 'Super Admin',
        'admin': 'Tenant Admin',
        'manager': 'Manager',
        'cashier': 'Cashier',
        'sales_agent': 'Sales Agent',
    }
    
    # ✅ Use the custom manager that extends Django's DefaultUserManager
    objects = UserManager()
    
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
        default='cashier'
    )
    
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="User's phone number"
    )
    
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
    
    def save(self, *args, **kwargs):
        """Save user and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id if self.tenant_id else None
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync (only for tenant users)
        if getattr(settings, 'OFFLINE_MODE', False) and tenant_id:
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='User',
                    object_id=str(self.id),
                    operation='CREATE' if is_new else 'UPDATE',
                    data={
                        'id': self.id,
                        'username': self.username,
                        'email': self.email,
                        'first_name': self.first_name,
                        'last_name': self.last_name,
                        'role': self.role,
                        'phone_number': self.phone_number,
                        'pin_code': self.pin_code,
                        'require_pin_for_pos': self.require_pin_for_pos,
                        'is_active': self.is_active,
                        'is_superuser': self.is_superuser,
                        'is_staff': self.is_staff,
                        'tenant_id': tenant_id,
                        'last_login': self.last_login.isoformat() if self.last_login else None,
                        'date_joined': self.date_joined.isoformat() if self.date_joined else None,
                    },
                    priority=7  # User changes are important
                )
                logger.debug(f"✅ Queued User sync: {self.username}")
            except Exception as e:
                logger.error(f"Failed to queue User sync: {e}")
    
    def delete(self, *args, **kwargs):
        """Queue deletion for sync, then delete the object"""
        
        tenant_id = self.tenant_id if self.tenant_id else None
        
        # ✅ Queue deletion sync if offline
        if getattr(settings, 'OFFLINE_MODE', False) and tenant_id:
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='User',
                    object_id=str(self.id),
                    operation='DELETE',
                    data={
                        'id': self.id,
                        'username': self.username,
                        'email': self.email,
                        'tenant_id': tenant_id,
                    },
                    priority=7
                )
                logger.debug(f"✅ Queued User deletion sync: {self.username}")
            except Exception as e:
                logger.error(f"Failed to queue User deletion sync: {e}")
        
        return super().delete(*args, **kwargs)
    
    def set_password(self, raw_password):
        """Override set_password to track password changes"""
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)
        self._password = raw_password
        
        # ✅ Queue password change sync
        tenant_id = self.tenant_id if self.tenant_id else None
        if getattr(settings, 'OFFLINE_MODE', False) and tenant_id:
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='User',
                    object_id=str(self.id),
                    operation='UPDATE',
                    data={
                        'id': self.id,
                        'username': self.username,
                        'password_changed_at': timezone.now().isoformat(),
                        'tenant_id': tenant_id,
                    },
                    priority=9  # High priority - security
                )
                logger.debug(f"✅ Queued User password change sync: {self.username}")
            except Exception as e:
                logger.error(f"Failed to queue User password change sync: {e}")
        
        # Save with update_fields to avoid triggering save() twice
        self.save(update_fields=['password'])
    
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
    def is_manager(self):
        return self.role == 'manager'
    
    @property
    def is_cashier(self):
        return self.role == 'cashier'
    
    @property
    def is_sales_agent(self):
        return self.role == 'sales_agent'
    
    @property
    def has_tenant(self):
        return self.tenant is not None
    
    @property
    def has_pin(self):
        return bool(self.pin_code)
    
    def has_project_access(self, project_type_code):
        if self.is_super_admin:
            return True
        if self.tenant and self.tenant.project_type:
            return self.tenant.project_type.code.upper() == project_type_code.upper()
        return False
    
    def get_project_type(self):
        if self.tenant and self.tenant.project_type:
            return self.tenant.project_type
        return None
    
    def get_dashboard_url(self):
        if self.is_super_admin:
            return 'super_admin_dashboard'
        
        project_type = self.get_project_type()
        if not project_type:
            return 'admin_dashboard'
        
        if self.is_tenant_admin:
            return 'admin_dashboard'
        elif self.is_manager:
            return 'manager_dashboard'
        elif self.is_cashier:
            return 'cashier_dashboard'
        elif self.is_sales_agent:
            return 'sales_agent_dashboard'
        
        return 'admin_dashboard'
    
    def verify_pin(self, pin):
        """Verify user's PIN"""
        if not self.require_pin_for_pos:
            return True
        if not self.pin_code:
            return False
        return self.pin_code == pin
    
    def set_pin(self, pin):
        """Set user's PIN"""
        if len(pin) < 4 or len(pin) > 6:
            raise ValueError("PIN must be 4-6 digits")
        if not pin.isdigit():
            raise ValueError("PIN must contain only digits")
        
        self.pin_code = pin
        self.save(update_fields=['pin_code', 'updated_at'])
        
        # ✅ Queue PIN change sync
        tenant_id = self.tenant_id if self.tenant_id else None
        if getattr(settings, 'OFFLINE_MODE', False) and tenant_id:
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='User',
                    object_id=str(self.id),
                    operation='UPDATE',
                    data={
                        'id': self.id,
                        'username': self.username,
                        'pin_changed_at': timezone.now().isoformat(),
                        'tenant_id': tenant_id,
                    },
                    priority=8
                )
                logger.debug(f"✅ Queued User PIN change sync: {self.username}")
            except Exception as e:
                logger.error(f"Failed to queue User PIN change sync: {e}")


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