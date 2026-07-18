# apps/shared/apps.py
from django.apps import AppConfig
from django.db.models.signals import post_migrate
import logging

logger = logging.getLogger(__name__)

class SharedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.shared'
    verbose_name = 'Shared'

    def ready(self):
        """Connect signals when app is ready"""
        # Connect post_migrate signal for syncing project types
        post_migrate.connect(self.sync_project_types, sender=self)
        logger.info("Shared app ready!")

    def sync_project_types(self, **kwargs):
        """Sync project types to database after migrations"""
        try:
            from apps.shared.tenants.models import ProjectType
            from django.conf import settings
            
            created_count = 0
            updated_count = 0
            
            for key, data in settings.PROJECT_TYPES.items():
                obj, created = ProjectType.objects.update_or_create(
                    code=data['code'],
                    defaults={
                        'name': data['name'],
                        'icon': data.get('icon', ''),
                        'color': data.get('color', '#000000'),
                        'is_active': data.get('active', True),
                        'description': data.get('description', ''),
                    }
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            
            logger.info(f"✅ Project types synced: {created_count} created, {updated_count} updated")
            
        except Exception as e:
            logger.error(f"Error syncing project types: {e}")