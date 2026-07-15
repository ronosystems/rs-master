# apps/shared/permissions/management/commands/assign_project_types.py

from django.core.management.base import BaseCommand
from apps.shared.permissions.models import Role
from apps.shared.tenants.models import ProjectType


class Command(BaseCommand):
    help = 'Assign project types to roles'

    def handle(self, *args, **options):
        self.stdout.write('🔄 Assigning project types to roles...')
        
        # Get project types
        tronic_master = ProjectType.objects.filter(code='TRONIC_MASTER').first()
        hotel_master = ProjectType.objects.filter(code='HOTEL_MASTER').first()
        food_master = ProjectType.objects.filter(code='FOOD_MASTER').first()
        retail_master = ProjectType.objects.filter(code='RETAIL_MASTER').first()
        health_master = ProjectType.objects.filter(code='HEALTH_MASTER').first()
        fashion_master = ProjectType.objects.filter(code='FASHION_MASTER').first()
        
        # Define which roles belong to which project type
        role_project_mapping = {
            # Tech Master Roles
            'cashier': tronic_master,
            'manager': None,  # None = All projects
            'sales_agent': tronic_master,
            'viewer': None,  # Viewer is global
            
            # Hotel Master Roles
            'receptionist': hotel_master,
            'hotel_manager': hotel_master,
            
            # Food Master Roles
            'waiter': food_master,
            'kitchen': food_master,
            'chef': food_master,
            
            # Retail Master Roles
            'retail_sales': retail_master,
            
            # Health Master Roles
            'pharmacist': health_master,
            'nurse': health_master,
            'doctor': health_master,
            
            # Fashion Master Roles
            'fashion_sales': fashion_master,
            'stylist': fashion_master,
            
            # Global Roles (apply to all projects)
            'tenant_admin': None,  # Tenant Admin is global
        }
        
        updated_count = 0
        for role_codename, project_type in role_project_mapping.items():
            try:
                role = Role.objects.get(codename=role_codename)
                # Clear existing project types
                role.project_types.clear()
                
                if project_type:
                    role.project_types.add(project_type)
                    self.stdout.write(f'  ✅ Assigned {project_type.name} to {role.name}')
                else:
                    self.stdout.write(f'  ✅ {role.name} applies to all projects')
                updated_count += 1
            except Role.DoesNotExist:
                self.stdout.write(f'  ⚠️ Role "{role_codename}" not found')
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Updated {updated_count} roles'))