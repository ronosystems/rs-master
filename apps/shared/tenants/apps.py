# apps/shared/tenants/apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.shared.tenants'
    label = 'tenants'  # ✅ ADD THIS - allows 'tenants.Tenant'
    
    def ready(self):
        """Auto-sync project types on app ready"""
        import sys
        
        # Skip during migrations, testing, or shell
        if any(cmd in sys.argv for cmd in ['migrate', 'makemigrations', 'test']):
            return
        
        try:
            from .models import ProjectType
            result = ProjectType.sync_from_settings()
            logger.info(f"✅ Project types synced: {result['created']} created, {result['updated']} updated")
            print(f"✅ Project types synced: {result['created']} created, {result['updated']} updated")
        except Exception as e:
            logger.warning(f"⚠️ Could not sync project types: {e}")