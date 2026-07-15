# apps/shared/tenants/management/commands/seed_offline_cache.py
from django.core.management.base import BaseCommand
from apps.shared.tenants.models import OfflineCache, Tenant

class Command(BaseCommand):
    help = 'Seed offline cache with essential data'

    def handle(self, *args, **options):
        self.stdout.write('🌱 Seeding offline cache...')
        
        tenant = Tenant.objects.first()
        if not tenant:
            self.stdout.write(self.style.ERROR('❌ No tenant found'))
            return
        
        # Clear existing cache for this tenant
        OfflineCache.objects.filter(tenant=tenant).delete()
        
        # Try to import models - some may not exist yet
        try:
            from apps.tronic_master.inventory.models import Category
            categories = Category.objects.filter(tenant=tenant)
            for category in categories:
                OfflineCache.objects.create(
                    tenant=tenant,
                    model_name='Category',
                    object_id=category.id,
                    data={
                        'id': category.id,
                        'name': category.name,
                        'description': getattr(category, 'description', ''),
                        'tenant_id': category.tenant_id,
                    }
                )
            self.stdout.write(f'✅ Cached {categories.count()} categories')
        except ImportError:
            self.stdout.write('⚠️  Category model not found - skipping')
        
        try:
            from apps.tronic_master.inventory.models import Product
            products = Product.objects.filter(tenant=tenant)
            for product in products:
                OfflineCache.objects.create(
                    tenant=tenant,
                    model_name='Product',
                    object_id=product.id,
                    data={
                        'id': product.id,
                        'name': product.name,
                        'price': str(product.price) if hasattr(product, 'price') and product.price else '0',
                        'sku': getattr(product, 'sku', ''),
                        'category_id': getattr(product, 'category_id', None),
                        'tenant_id': product.tenant_id,
                        'stock_quantity': getattr(product, 'stock_quantity', 0),
                    }
                )
            self.stdout.write(f'✅ Cached {products.count()} products')
        except ImportError:
            self.stdout.write('⚠️  Product model not found - skipping')
        
        try:
            from apps.tronic_master.inventory.models import Branch
            branches = Branch.objects.filter(tenant=tenant)
            for branch in branches:
                OfflineCache.objects.create(
                    tenant=tenant,
                    model_name='Branch',
                    object_id=branch.id,
                    data={
                        'id': branch.id,
                        'name': branch.name,
                        'address': getattr(branch, 'address', ''),
                        'phone': getattr(branch, 'phone', ''),
                        'tenant_id': branch.tenant_id,
                    }
                )
            self.stdout.write(f'✅ Cached {branches.count()} branches')
        except ImportError:
            self.stdout.write('⚠️  Branch model not found - skipping')
        
        self.stdout.write(self.style.SUCCESS('✅ Offline cache seeded successfully!'))