# apps/tronic_master/apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class TechMasterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tronic_master'
    verbose_name = 'Tech Master'

    def ready(self):
        """Auto-setup default roles when app starts"""
        self.setup_default_roles()
        logger.info("Tech Master app ready!")

    def setup_default_roles(self):
        """Create default roles for all tenants"""
        try:
            from apps.shared.roles.models import ProjectRole
            from apps.shared.tenants.models import Tenant
            from apps.tronic_master.permissions import TRONIC_MASTER_PERMISSIONS
            
            # ✅ Get ALL tenants, not just the first one
            tenants = Tenant.objects.filter(status='active')
            
            if not tenants.exists():
                logger.warning("No active tenants found, skipping role creation")
                return
            
            default_roles = {
                'Administrator': {
                    'description': 'Full access to Tech Master',
                    'permissions': list(TRONIC_MASTER_PERMISSIONS.keys()),
                    'is_system_role': True
                },
                'Manager': {
                    'description': 'Manage operations and staff',
                    'permissions': [
                        'can_view_report',
                        'can_view_sale',
                        'can_view_low_stock',
                        'can_create_sale',
                        'can_process_payment',
                        'can_view_staff',
                        'can_add_staff',
                        'can_manage_staff',
                        'can_view_staff_attendance',
                        'can_view_staff_leave',
                        'can_view_roles',
                        'can_create_role',
                        'can_assign_role',
                        'can_view_branch',
                        'can_add_branch',
                        'can_manage_branch',
                        'can_view_branch_stock',
                        'can_transfer_stock',
                        'can_view_category',
                        'can_add_category',
                        'can_edit_category',
                        'can_manage_categories',
                        'can_view_product',
                        'can_add_product',
                        'can_edit_product',
                        'can_manage_products',
                        'can_view_damaged_units',
                        'can_transfer_items',
                        'can_bulk_print_labels',
                        'can_view_product_barcodes',
                        'can_import_products',
                        'can_view_stock',
                        'can_manage_stock',
                        'can_view_stock_report',
                        'can_view_stock_history',
                        'can_assign_to_agent',
                        'can_view_agent_sale',
                        'can_view_sales_history',
                        'can_search_sales',
                        'can_view_returns',
                        'can_view_receipt',
                        'can_view_receipt_search',
                        'can_view_supplier',
                        'can_add_supplier',
                        'can_edit_supplier',
                        'can_manage_suppliers',
                        'can_view_report_dashboard',
                        'can_view_sales_reports',
                        'can_view_expenses',
                        'can_view_expense_report',
                        'can_view_inventory_report',
                        'can_export_report',
                        'can_view_settings',
                        'can_manage_settings',
                        'can_view_receipt_settings',
                        'can_view_payment_settings',
                        'can_view_company_settings',
                        'can_view_my_stock',
                        'can_view_my_sales',
                        'can_view_agent_sale_form',
                        'can_view_price_check',
                        'can_view_product_search',
                    ],
                    'is_system_role': False
                },
                'Cashier': {
                    'description': 'Process sales at the counter',
                    'permissions': [
                        'can_view_price_check',
                        'can_create_sale',
                        'can_process_payment',
                        'can_view_receipt',
                        'can_view_receipt_search',
                        'can_view_product_search',
                    ],
                    'is_system_role': False
                },
                'Sales Agent': {
                    'description': 'Create sales from assigned stock',
                    'permissions': [
                        'can_view_my_stock',
                        'can_view_agent_sale_form',
                        'can_view_my_sales',
                        'can_view_price_check',
                        'can_view_receipt',
                    ],
                    'is_system_role': False
                },
                'Stock Controller': {
                    'description': 'Manage inventory and stock',
                    'permissions': [
                        'can_view_product',
                        'can_add_product',
                        'can_edit_product',
                        'can_manage_products',
                        'can_view_category',
                        'can_add_category',
                        'can_edit_category',
                        'can_manage_categories',
                        'can_view_branch',
                        'can_view_branch_stock',
                        'can_transfer_stock',
                        'can_view_stock',
                        'can_manage_stock',
                        'can_view_stock_report',
                        'can_view_stock_history',
                        'can_view_damaged_units',
                        'can_transfer_items',
                        'can_bulk_print_labels',
                        'can_view_product_barcodes',
                        'can_import_products',
                        'can_view_supplier',
                        'can_add_supplier',
                        'can_edit_supplier',
                        'can_manage_suppliers',
                        'can_view_inventory_report',
                        'can_export_report',
                        'can_view_low_stock',
                        'can_assign_to_agent',
                    ],
                    'is_system_role': False
                },
            }
            
            total_created = 0
            total_updated = 0
            
            # ✅ Loop through all tenants
            for tenant in tenants:
                for role_name, role_data in default_roles.items():
                    role, created = ProjectRole.objects.get_or_create(
                        tenant=tenant,
                        project_type='tronic_master',
                        name=role_name,
                        defaults={
                            'description': role_data['description'],
                            'permissions': role_data['permissions'],
                            'is_system_role': role_data['is_system_role'],
                        }
                    )
                    if created:
                        total_created += 1
                    else:
                        # Update existing role permissions if needed
                        if role.permissions != role_data['permissions']:
                            role.permissions = role_data['permissions']
                            role.save()
                            total_updated += 1
            
            if total_created > 0:
                logger.info(f"Created {total_created} default Tech Master roles across {tenants.count()} tenants")
            if total_updated > 0:
                logger.info(f"Updated {total_updated} existing Tech Master roles")
                
        except Exception as e:
            logger.error(f"Error setting up default roles: {e}")