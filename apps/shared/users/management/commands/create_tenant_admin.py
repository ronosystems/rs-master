# apps/shared/users/management/commands/create_tenant_admin.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.shared.tenants.models import Tenant, ProjectType
from apps.shared.permissions.models import Role, UserRoleAssignment
import getpass

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a tenant admin (company owner) with full company access'

    def add_arguments(self, parser):
        parser.add_argument('--username', help='Username for tenant admin')
        parser.add_argument('--email', help='Email for tenant admin')
        parser.add_argument('--password', help='Password for tenant admin')
        parser.add_argument('--tenant', help='Tenant ID or company name to assign')
        parser.add_argument('--project', help='Project type code (e.g., TECH_MASTER, HOTEL_MASTER)')

    def handle(self, *args, **options):
        self.stdout.write('🔄 Creating Tenant Admin...')
        
        username = options.get('username') or input('Username: ')
        email = options.get('email') or input('Email: ')
        password = options.get('password') or getpass.getpass('Password: ')
        tenant_input = options.get('tenant') or input('Tenant ID or Company Name: ')
        project_code = options.get('project') or input('Project Type (e.g., TECH_MASTER): ')
        
        # Find tenant
        tenant = None
        try:
            if tenant_input.isdigit():
                tenant = Tenant.objects.get(id=int(tenant_input))
            else:
                tenant = Tenant.objects.get(company_name__icontains=tenant_input)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Tenant "{tenant_input}" not found.'))
            return
        
        # Find project type
        project_type = None
        if project_code:
            try:
                project_type = ProjectType.objects.get(code__iexact=project_code)
                tenant.project_type = project_type
                tenant.save()
                self.stdout.write(f'   ✅ Project type set to: {project_type.name}')
            except ProjectType.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'⚠️ Project type "{project_code}" not found.'))
        
        # Check if username exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f'❌ Username "{username}" already exists.'))
            return
        
        # Create tenant admin
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                tenant=tenant,
                role='admin',
                is_active=True,
                is_staff=True,
            )
            
            # Assign Tenant Admin role
            try:
                admin_role = Role.objects.get(codename='tenant_admin')
                UserRoleAssignment.objects.create(
                    user=user,
                    role=admin_role,
                    assigned_by=user,
                    is_active=True,
                    notes='Tenant Admin (Company Owner)'
                )
                self.stdout.write('   ✅ Assigned Tenant Admin role')
            except Role.DoesNotExist:
                self.stdout.write(self.style.WARNING('⚠️ Role "tenant_admin" not found. Please run sync_permissions first.'))
            
            self.stdout.write(self.style.SUCCESS(f'✅ Tenant Admin "{username}" created successfully!'))
            self.stdout.write(f'   Email: {email}')
            self.stdout.write(f'   Tenant: {tenant.company_name}')
            self.stdout.write(f'   Project: {tenant.project_type.name if tenant.project_type else "Not set"}')
            self.stdout.write(f'   Role: Tenant Admin (Full company access)')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error creating tenant admin: {str(e)}'))
