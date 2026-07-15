# apps/shared/permissions/management/commands/sync_permissions.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from apps.shared.permissions.models import Role, SystemPermission, UserRoleAssignment
from apps.shared.tenants.models import ProjectType
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Sync system permissions and create default project roles'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔄 Syncing permissions and project roles...'))
        
        # ============================================
        # 1. CREATE DJANGO PERMISSIONS
        # ============================================
        self.stdout.write('\n📋 Creating Django permissions...')
        
        models_with_permissions = [
            ('product', 'Product'),
            ('category', 'Category'),
            ('sale', 'Sale'),
            ('saleitem', 'Sale Item'),
            ('customer', 'Customer'),
            ('supplier', 'Supplier'),
            ('branch', 'Branch'),
            ('expense', 'Expense'),
            ('room', 'Room'),
            ('booking', 'Booking'),
            ('guest', 'Guest'),
            ('user', 'User'),
            ('role', 'Role'),
            ('settings', 'Settings'),
            ('receiptsetting', 'Receipt Setting'),
            ('paymentsetting', 'Payment Setting'),
            ('report', 'Report'),
            ('property', 'Property'),      # Rental Master
            ('unit', 'Unit'),              # Rental Master
            ('tenant', 'Tenant'),          # Rental Master
            ('payment', 'Payment'),        # Rental Master
        ]
        
        permission_actions = ['view', 'add', 'change', 'delete']
        created_count = 0
        
        for model_name, model_label in models_with_permissions:
            content_type, created = ContentType.objects.get_or_create(
                app_label='shared',
                model=model_name
            )
            
            for action in permission_actions:
                codename = f"{action}_{model_name}"
                name = f"Can {action} {model_label}"
                
                perm, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=content_type,
                    defaults={'name': name}
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f"  ✅ Created: {codename}")
        
        self.stdout.write(f"  Created {created_count} new permissions")
        
        # ============================================
        # 2. CREATE SYSTEM PERMISSIONS
        # ============================================
        self.stdout.write('\n📋 Creating SystemPermissions...')
        
        system_perms_created = 0
        for perm in Permission.objects.all():
            sp, created = SystemPermission.objects.get_or_create(
                django_permission=perm,
                defaults={
                    'action': perm.codename.split('_')[0] if '_' in perm.codename else 'view',
                    'description': perm.name,
                    'category': perm.content_type.model if perm.content_type else 'other',
                    'is_active': True,
                }
            )
            if created:
                system_perms_created += 1
        
        self.stdout.write(f"  Created {system_perms_created} SystemPermissions")
        
        # ============================================
        # 3. CREATE DEFAULT PROJECT ROLES (No System Roles)
        # ============================================
        self.stdout.write('\n📋 Creating default project roles...')
        
        # ============================================
        # NOTE: System roles (super_admin, admin, user) are NOT created here
        # They are only in the User model's ROLE_CHOICES
        # ============================================
        
        role_definitions = [
            # ============================================
            # TECH MASTER ROLES
            # ============================================
            {
                'codename': 'cashier',
                'name': 'Cashier',
                'description': 'Can create sales and view products',
                'permissions': [
                    'view_product', 'view_category', 'view_sale', 'view_customer',
                    'add_sale', 'add_customer',
                    'change_sale',
                ],
                'project_type': 'TRONIC_MASTER'
            },
            {
                'codename': 'sales_agent',
                'name': 'Sales Agent',
                'description': 'Can manage sales and customers',
                'permissions': [
                    'view_product', 'view_sale', 'view_customer',
                    'add_sale', 'add_customer',
                    'change_sale', 'change_customer',
                ],
                'project_type': 'TRONIC_MASTER'
            },
            {
                'codename': 'manager',
                'name': 'Manager',
                'description': 'Can manage most operations',
                'permissions': [
                    'view_product', 'add_product', 'change_product', 'delete_product',
                    'view_category', 'add_category', 'change_category', 'delete_category',
                    'view_sale', 'change_sale',
                    'view_customer', 'add_customer', 'change_customer',
                    'view_room', 'add_room', 'change_room',
                    'view_booking', 'add_booking', 'change_booking',
                    'view_user', 'add_user', 'change_user',
                    'view_expense', 'add_expense', 'change_expense',
                    'view_branch', 'add_branch', 'change_branch',
                ],
                'project_type': None  # All projects
            },
            
            # ============================================
            # HOTEL MASTER ROLES
            # ============================================
            {
                'codename': 'receptionist',
                'name': 'Receptionist',
                'description': 'Can manage hotel bookings and guests',
                'permissions': [
                    'view_room', 'view_booking', 'view_guest',
                    'add_booking', 'add_guest',
                    'change_booking', 'change_guest',
                ],
                'project_type': 'HOTEL_MASTER'
            },
            {
                'codename': 'manager',
                'name': 'Manager',
                'description': 'Can manage hotel operations and staff',
                'permissions': [
                    'view_room', 'add_room', 'change_room', 'delete_room',
                    'view_booking', 'add_booking', 'change_booking', 'delete_booking',
                    'view_guest', 'add_guest', 'change_guest', 'delete_guest',
                    'view_user', 'add_user', 'change_user',
                    'view_expense', 'add_expense', 'change_expense',
                    'view_branch', 'add_branch', 'change_branch',
                ],
                'project_type': 'HOTEL_MASTER'
            },
            
            # ============================================
            # FOOD MASTER ROLES
            # ============================================
            {
                'codename': 'waiter',
                'name': 'Waiter',
                'description': 'Can take orders and serve customers',
                'permissions': [
                    'view_product', 'view_sale',
                    'add_sale', 'change_sale',
                ],
                'project_type': 'FOOD_MASTER'
            },
            {
                'codename': 'kitchen',
                'name': 'Kitchen Staff',
                'description': 'Can manage kitchen operations',
                'permissions': [
                    'view_product', 'change_product',
                    'view_sale', 'change_sale',
                ],
                'project_type': 'FOOD_MASTER'
            },
            {
                'codename': 'chef',
                'name': 'Chef',
                'description': 'Can manage kitchen and menu',
                'permissions': [
                    'view_product', 'add_product', 'change_product', 'delete_product',
                    'view_sale', 'change_sale',
                ],
                'project_type': 'FOOD_MASTER'
            },
            
            # ============================================
            # RETAIL MASTER ROLES
            # ============================================
            {
                'codename': 'retail_sales',
                'name': 'Retail Sales',
                'description': 'Can manage retail sales',
                'permissions': [
                    'view_product', 'view_sale', 'view_customer',
                    'add_sale', 'add_customer',
                    'change_sale', 'change_customer',
                ],
                'project_type': 'RETAIL_MASTER'
            },
            
            # ============================================
            # HEALTH MASTER ROLES
            # ============================================
            {
                'codename': 'pharmacist',
                'name': 'Pharmacist',
                'description': 'Can manage pharmacy operations',
                'permissions': [
                    'view_product', 'add_product', 'change_product',
                    'view_sale', 'add_sale', 'change_sale',
                    'view_customer', 'add_customer', 'change_customer',
                ],
                'project_type': 'HEALTH_MASTER'
            },
            {
                'codename': 'nurse',
                'name': 'Nurse',
                'description': 'Can manage patient care',
                'permissions': [
                    'view_customer', 'add_customer', 'change_customer',
                    'view_sale', 'add_sale',
                ],
                'project_type': 'HEALTH_MASTER'
            },
            {
                'codename': 'doctor',
                'name': 'Doctor',
                'description': 'Can manage patient care and prescriptions',
                'permissions': [
                    'view_customer', 'add_customer', 'change_customer',
                    'view_sale', 'add_sale', 'change_sale',
                    'view_product', 'change_product',
                ],
                'project_type': 'HEALTH_MASTER'
            },
            
            # ============================================
            # FASHION MASTER ROLES
            # ============================================
            {
                'codename': 'fashion_sales',
                'name': 'Fashion Sales',
                'description': 'Can manage fashion sales',
                'permissions': [
                    'view_product', 'view_sale', 'view_customer',
                    'add_sale', 'add_customer',
                    'change_sale', 'change_customer',
                ],
                'project_type': 'FASHION_MASTER'
            },
            {
                'codename': 'stylist',
                'name': 'Stylist',
                'description': 'Can manage styling and consultations',
                'permissions': [
                    'view_customer', 'add_customer', 'change_customer',
                    'view_sale', 'add_sale',
                    'view_product', 'change_product',
                ],
                'project_type': 'FASHION_MASTER'
            },
            
            # ============================================
            # RENTAL MASTER ROLES
            # ============================================
            {
                'codename': 'caretaker',
                'name': 'Caretaker',
                'description': 'Can manage property maintenance and tenants',
                'permissions': [
                    'view_property', 'view_unit', 'view_tenant', 'view_payment',
                    'add_tenant', 'change_tenant',
                    'add_payment', 'change_payment',
                ],
                'project_type': 'RENTAL_MASTER'
            },
            {
                'codename': 'property_manager',
                'name': 'Property Manager',
                'description': 'Can manage properties and tenants',
                'permissions': [
                    'view_property', 'add_property', 'change_property',
                    'view_unit', 'add_unit', 'change_unit',
                    'view_tenant', 'add_tenant', 'change_tenant',
                    'view_payment', 'add_payment', 'change_payment',
                ],
                'project_type': 'RENTAL_MASTER'
            },
            {
                'codename': 'maintenance',
                'name': 'Maintenance',
                'description': 'Can manage maintenance requests',
                'permissions': [
                    'view_property', 'view_unit',
                    'view_tenant',
                ],
                'project_type': 'RENTAL_MASTER'
            },
            
            # ============================================
            # VIEWER ROLE (All Projects)
            # ============================================
            {
                'codename': 'viewer',
                'name': 'Viewer',
                'description': 'Can only view data',
                'permissions': [
                    'view_product', 'view_category', 'view_sale', 
                    'view_customer', 'view_room', 'view_booking',
                    'view_property', 'view_unit', 'view_tenant'
                ],
                'project_type': None  # All projects
            },
        ]
        
        roles_created = 0
        for role_def in role_definitions:
            role, created = Role.objects.get_or_create(
                codename=role_def['codename'],
                defaults={
                    'name': role_def['name'],
                    'description': role_def['description'],
                    'role_type': 'custom',          # NOT system
                    'is_system_role': False,        # NOT system
                    'is_active': True,
                }
            )
            
            if created:
                roles_created += 1
                self.stdout.write(f"  ✅ Created project role: {role_def['name']}")
            else:
                # Update existing role
                role.name = role_def['name']
                role.description = role_def['description']
                role.role_type = 'custom'
                role.is_system_role = False
                role.save()
                self.stdout.write(f"  🔄 Updated project role: {role_def['name']}")
            
            # Add permissions
            permission_codenames = role_def.get('permissions', [])
            permissions = Permission.objects.filter(codename__in=permission_codenames)
            role.permissions.set(permissions)
            role.save()
        
        self.stdout.write(f"  Created/Updated {roles_created} project roles")
        
        # ============================================
        # 4. ASSIGN PROJECT TYPES TO ROLES
        # ============================================
        self.stdout.write('\n📋 Assigning project types to project roles...')
        
        # Get project types
        tronic_master = ProjectType.objects.filter(code='TRONIC_MASTER').first()
        hotel_master = ProjectType.objects.filter(code='HOTEL_MASTER').first()
        food_master = ProjectType.objects.filter(code='FOOD_MASTER').first()
        retail_master = ProjectType.objects.filter(code='RETAIL_MASTER').first()
        health_master = ProjectType.objects.filter(code='HEALTH_MASTER').first()
        fashion_master = ProjectType.objects.filter(code='FASHION_MASTER').first()
        rental_master = ProjectType.objects.filter(code='RENTAL_MASTER').first()
        
        # Map roles to project types
        role_project_mapping = {}
        for role_def in role_definitions:
            role_project_mapping[role_def['codename']] = role_def.get('project_type')
        
        assigned_count = 0
        for role_codename, project_code in role_project_mapping.items():
            try:
                role = Role.objects.get(codename=role_codename)
                role.project_types.clear()
                
                if project_code:
                    project_type = ProjectType.objects.filter(code=project_code).first()
                    if project_type:
                        role.project_types.add(project_type)
                        self.stdout.write(f"  ✅ Assigned {project_type.name} to {role.name}")
                    else:
                        self.stdout.write(f"  ⚠️ Project type '{project_code}' not found for {role.name}")
                else:
                    self.stdout.write(f"  ✅ {role.name} applies to all projects")
                assigned_count += 1
            except Role.DoesNotExist:
                self.stdout.write(f"  ⚠️ Role '{role_codename}' not found")
        
        self.stdout.write(f"  Assigned project types to {assigned_count} roles")
        
        # ============================================
        # 5. ASSIGN PROJECT ROLES TO USERS (Optional)
        # ============================================
        self.stdout.write('\n📋 Assigning project roles to users...')
        
        # First, clear all existing role assignments
        UserRoleAssignment.objects.all().delete()
        self.stdout.write("  ✅ Cleared existing role assignments")
        
        # Assign cashier role to users with role='cashier' (if any)
        try:
            cashier_role = Role.objects.get(codename='cashier')
            # Users who have 'cashier' as system role (old data) - convert to project role
            cashier_users = User.objects.filter(role='cashier', is_active=True)
            count = 0
            for user in cashier_users:
                # Update system role to 'user'
                user.role = 'user'
                user.save()
                # Assign project role
                UserRoleAssignment.objects.create(
                    user=user,
                    role=cashier_role,
                    assigned_by=None,
                    is_active=True,
                    notes='Converted from system role'
                )
                count += 1
            if count > 0:
                self.stdout.write(f"  ✅ Assigned 'cashier' to {count} users")
        except Role.DoesNotExist:
            self.stdout.write("  ⚠️ Role 'cashier' not found")
        
        # Assign sales_agent role to users with role='sales_agent' (old data)
        try:
            sales_agent_role = Role.objects.get(codename='sales_agent')
            sales_agent_users = User.objects.filter(role='sales_agent', is_active=True)
            count = 0
            for user in sales_agent_users:
                user.role = 'user'
                user.save()
                UserRoleAssignment.objects.create(
                    user=user,
                    role=sales_agent_role,
                    assigned_by=None,
                    is_active=True,
                    notes='Converted from system role'
                )
                count += 1
            if count > 0:
                self.stdout.write(f"  ✅ Assigned 'sales_agent' to {count} users")
        except Role.DoesNotExist:
            self.stdout.write("  ⚠️ Role 'sales_agent' not found")
        
        # Assign manager role to users with role='manager' (old data)
        try:
            manager_role = Role.objects.get(codename='manager')
            manager_users = User.objects.filter(role='manager', is_active=True)
            count = 0
            for user in manager_users:
                user.role = 'user'
                user.save()
                UserRoleAssignment.objects.create(
                    user=user,
                    role=manager_role,
                    assigned_by=None,
                    is_active=True,
                    notes='Converted from system role'
                )
                count += 1
            if count > 0:
                self.stdout.write(f"  ✅ Assigned 'manager' to {count} users")
        except Role.DoesNotExist:
            self.stdout.write("  ⚠️ Role 'manager' not found")
        
        self.stdout.write(self.style.SUCCESS('\n✅ Permissions sync completed successfully!'))