# apps/tronic_master/signals.py
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps
import logging

logger = logging.getLogger(__name__)

@receiver(post_migrate)
def setup_default_roles_after_migration(sender, **kwargs):
    """
    Create default roles after migrations are complete.
    This runs only when migrations are run, not on every app startup.
    """
    if sender.name == 'apps.tronic_master':
        # Import here to avoid circular imports
        from .apps import TechMasterConfig
        
        # Create an instance of the config to use its method
        config = TechMasterConfig('tronic_master', apps.get_app_config('tronic_master'))
        config.setup_default_roles()