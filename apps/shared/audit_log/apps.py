# apps/shared/audit_log/apps.py

from django.apps import AppConfig


class AuditLogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.shared.audit_log'
    label = 'audit_log'