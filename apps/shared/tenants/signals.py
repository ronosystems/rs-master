# apps/shared/tenants/signals.py

from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import ProjectType

@receiver(post_migrate)
def auto_sync_project_types(sender, **kwargs):
    """Auto-sync project types after migrations"""
    if sender.name == 'apps.shared.tenants':
        ProjectType.sync_from_settings()