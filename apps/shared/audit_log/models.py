# apps/shared/audit_log/models.py

from django.db import models
from django.conf import settings
import logging

from apps.shared.tenants.models import Tenant

# ✅ ADD THIS IMPORT FOR SYNC QUEUE
from apps.shared.tenants.models import SyncQueue

logger = logging.getLogger(__name__)


class AuditLog(models.Model):
    """Audit log for tracking all user actions"""
    
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('failed_login', 'Failed Login'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('assign', 'Assign'),
        ('unassign', 'Unassign'),
        ('process', 'Process'),
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('print', 'Print'),
        ('download', 'Download'),
        ('system', 'System'),
        ('other', 'Other'),
    ]
    
    # Create a mapping for action display
    ACTION_DISPLAY = dict(ACTION_CHOICES)
    
    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    
    # Action details
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    
    # Changes (JSON format)
    changes = models.JSONField(default=dict, blank=True)
    
    # Request details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    method = models.CharField(max_length=10, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['action']),
            models.Index(fields=['model_name', 'object_id']),
        ]
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
    
    def __str__(self):
        user_name = self.user.username if self.user else 'Anonymous'
        action_display = self.ACTION_DISPLAY.get(self.action, self.action)
        return f"{user_name} - {action_display} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def action_display(self):
        """Get the display name for the action"""
        return self.ACTION_DISPLAY.get(self.action, self.action)
    
    @classmethod
    def log_action(
        cls,
        user,
        action,
        model_name='',
        object_id='',
        object_repr='',
        description='',
        changes=None,
        ip_address=None,
        user_agent=None,
        url=None,
        method=None,
        tenant=None
    ):
        """Log an action"""
        
        # If tenant is not provided, try to get from user
        if not tenant and user:
            tenant = getattr(user, 'tenant', None)
        
        return cls.objects.create(
            user=user,
            tenant=tenant,
            action=action,
            model_name=model_name,
            object_id=str(object_id) if object_id else '',
            object_repr=object_repr[:200],
            description=description,
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent,
            url=url,
            method=method
        )


class AuditLogSettings(models.Model):
    """Settings for audit logging"""
    
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='audit_settings'
    )
    
    enabled = models.BooleanField(default=True)
    log_all_actions = models.BooleanField(default=True)
    log_reads = models.BooleanField(default=False)  # Log view actions
    log_writes = models.BooleanField(default=True)   # Log create, update, delete
    log_auth = models.BooleanField(default=True)     # Log login, logout
    
    # Retention
    retention_days = models.PositiveIntegerField(default=30)
    auto_cleanup = models.BooleanField(default=True)
    
    # Excluded models (comma separated)
    excluded_models = models.TextField(
        blank=True,
        help_text="Comma separated list of models to exclude (e.g., auth.User, auth.Group)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Audit Log Settings'
        verbose_name_plural = 'Audit Log Settings'
        indexes = [
            models.Index(fields=['tenant']),
        ]
    
    def __str__(self):
        return f"Audit Settings for {self.tenant.company_name}"
    
    def save(self, *args, **kwargs):
        """Save audit settings and queue for sync"""
        is_new = self.pk is None
        tenant_id = self.tenant_id
        
        super().save(*args, **kwargs)
        
        # ✅ If offline, queue for sync
        if getattr(settings, 'OFFLINE_MODE', False):
            try:
                SyncQueue.objects.create(
                    tenant_id=tenant_id,
                    model_name='AuditLogSettings',
                    object_id=self.id,
                    operation='create' if is_new else 'update',
                    data={
                        'id': self.id,
                        'tenant_id': tenant_id,
                        'enabled': self.enabled,
                        'log_all_actions': self.log_all_actions,
                        'log_reads': self.log_reads,
                        'log_writes': self.log_writes,
                        'log_auth': self.log_auth,
                        'retention_days': self.retention_days,
                        'auto_cleanup': self.auto_cleanup,
                        'excluded_models': self.excluded_models,
                    }
                )
                logger.debug(f"✅ Queued AuditLogSettings sync for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Failed to queue AuditLogSettings sync: {e}")
    
    @classmethod
    def get_for_tenant(cls, tenant):
        """Get or create settings for a tenant"""
        obj, created = cls.objects.get_or_create(tenant=tenant)
        return obj