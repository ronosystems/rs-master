# apps/shared/users/management/commands/create_super_admin.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.shared.tenants.models import Tenant, ProjectType
from apps.shared.permissions.models import Role, UserRoleAssignment
import getpass

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a super admin user with full system access'

    def add_arguments(self, parser):
        parser.add_argument('--username', help='Username for super admin')
        parser.add_argument('--email', help='Email for super admin')
        parser.add_argument('--password', help='Password for super admin')

    def handle(self, *args, **options):
        self.stdout.write('🔄 Creating Super Admin...')
        
        username = options.get('username') or input('Username: ')
        email = options.get('email') or input('Email: ')
        password = options.get('password') or getpass.getpass('Password: ')
        
        # Check if super admin already exists
        if User.objects.filter(role='super_admin').exists():
            self.stdout.write(self.style.WARNING('⚠️ Super Admin already exists!'))
            confirm = input('Do you want to create another super admin? (y/n): ')
            if confirm.lower() != 'y':
                return
        
        # Check if username exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f'❌ Username "{username}" already exists.'))
            return
        
        # Create super admin
        try:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                role='super_admin',
                is_active=True,
                is_staff=True,
                is_superuser=True,
            )
            
            self.stdout.write(self.style.SUCCESS(f'✅ Super Admin "{username}" created successfully!'))
            self.stdout.write(f'   Email: {email}')
            self.stdout.write(f'   Role: Super Admin (Full system access)')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error creating super admin: {str(e)}'))
