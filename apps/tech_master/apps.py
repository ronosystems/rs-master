# apps/tech_master/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class TechMasterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tech_master'
    verbose_name = 'Tech Master'

    def ready(self):
        """Auto-setup default roles when app starts"""
        self.setup_default_roles()
        logger.info("Tech Master app ready!")

    def setup_default_roles(self):
        """Create default roles if they don't exist"""
        try:
            from apps.shared.roles.models import ProjectRole
            from apps.shared.tenants.models import Tenant
            from apps.tech_master.permissions import TECH_MASTER_PERMISSIONS
            
            tenant = Tenant.objects.first()
            if not tenant:
                logger.warning("No tenant found, skipping role creation")
                return
            
            default_roles = {
                'Administrator': {
                    'description': 'Full access to Tech Master',
                    'permissions': list(TECH_MASTER_PERMISSIONS.keys()),
                    'is_system_role': True
                },
                'Manager': {
                    'description': 'Manage operations and staff',
                    'permissions': [
                        'can_view_dashboard',
                        'can_view_product', 'can_add_product', 'can_edit_product',
                        'can_view_category', 'can_add_category', 'can_edit_category',
                        'can_view_branch', 'can_add_branch', 'can_edit_branch',
                        'can_view_stock', 'can_manage_stock', 'can_adjust_stock',
                        'can_view_sale', 'can_create_sale', 'can_process_payment',
                        'can_view_staff', 'can_manage_staff',
                        'can_view_report', 'can_export_report',
                        'can_view_settings',
                    ],
                    'is_system_role': False
                },
                'Cashier': {
                    'description': 'Process sales',
                    'permissions': [
                        'can_view_product',
                        'can_view_stock',
                        'can_view_sale', 'can_create_sale', 'can_process_payment',
                        'can_view_receipt',
                    ],
                    'is_system_role': False
                },
                'Sales Agent': {
                    'description': 'Create sales',
                    'permissions': [
                        'can_view_product',
                        'can_view_stock',
                        'can_view_sale', 'can_create_sale',
                    ],
                    'is_system_role': False
                },
                'Stock Controller': {
                    'description': 'Manage inventory',
                    'permissions': [
                        'can_view_product', 'can_add_product', 'can_edit_product',
                        'can_view_category', 'can_add_category', 'can_edit_category',
                        'can_view_branch',
                        'can_view_stock', 'can_manage_stock', 'can_adjust_stock',
                        'can_view_sale',
                        'can_view_report',
                    ],
                    'is_system_role': False
                },
            }
            
            created = []
            for role_name, role_data in default_roles.items():
                role, created_flag = ProjectRole.objects.get_or_create(
                    tenant=tenant,
                    project_type='tech_master',
                    name=role_name,
                    defaults={
                        'description': role_data['description'],
                        'permissions': role_data['permissions'],
                        'is_system_role': role_data['is_system_role'],
                    }
                )
                if created_flag:
                    created.append(role_name)
            
            if created:
                logger.info(f"Created default Tech Master roles: {', '.join(created)}")
                
        except Exception as e:
            logger.error(f"Error setting up default roles: {e}")