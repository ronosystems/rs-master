# apps/fashion_master/apps.py
from django.apps import AppConfig
from django.db.models.signals import post_migrate
import logging

logger = logging.getLogger(__name__)

class FashionMasterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.fashion_master'
    verbose_name = 'Fashion Master'

    def ready(self):
        """Connect signals when app is ready"""
        # Connect the post_migrate signal
        post_migrate.connect(self.setup_default_categories, sender=self)
        logger.info("Fashion Master app ready!")

    def setup_default_categories(self, **kwargs):
        """Create default fashion categories if they don't exist"""
        try:
            from apps.shared.tenants.models import Tenant
            from .models import FashionCategory
            
            tenant = Tenant.objects.first()
            if not tenant:
                logger.warning("No tenant found, skipping category creation")
                return
            
            default_categories = [
                # Clothing
                {'name': "Men's Shirts", 'category_type': 'clothing', 'gender': 'men', 'size_type': 'clothing'},
                {'name': "Men's Trousers", 'category_type': 'clothing', 'gender': 'men', 'size_type': 'clothing'},
                {'name': "Men's Jackets", 'category_type': 'clothing', 'gender': 'men', 'size_type': 'clothing'},
                {'name': "Women's Dresses", 'category_type': 'clothing', 'gender': 'women', 'size_type': 'clothing'},
                {'name': "Women's Tops", 'category_type': 'clothing', 'gender': 'women', 'size_type': 'clothing'},
                {'name': "Women's Skirts", 'category_type': 'clothing', 'gender': 'women', 'size_type': 'clothing'},
                {'name': "Women's Jackets", 'category_type': 'clothing', 'gender': 'women', 'size_type': 'clothing'},
                {'name': "Kids Clothing", 'category_type': 'clothing', 'gender': 'kids', 'size_type': 'clothing'},
                {'name': "Baby Onesies", 'category_type': 'babyshop', 'gender': 'babies', 'size_type': 'baby'},
                {'name': "Baby Sleepsuits", 'category_type': 'babyshop', 'gender': 'babies', 'size_type': 'baby'},
                {'name': "Boutique Dresses", 'category_type': 'boutique', 'gender': 'women', 'size_type': 'clothing'},
                {'name': "Boutique Evening Wear", 'category_type': 'boutique', 'gender': 'women', 'size_type': 'clothing'},
                
                # Shoes
                {'name': "Men's Shoes", 'category_type': 'shoes', 'gender': 'men', 'size_type': 'shoes'},
                {'name': "Men's Sneakers", 'category_type': 'shoes', 'gender': 'men', 'size_type': 'shoes'},
                {'name': "Women's Heels", 'category_type': 'shoes', 'gender': 'women', 'size_type': 'shoes'},
                {'name': "Women's Flats", 'category_type': 'shoes', 'gender': 'women', 'size_type': 'shoes'},
                {'name': "Women's Sneakers", 'category_type': 'shoes', 'gender': 'women', 'size_type': 'shoes'},
                {'name': "Kids Shoes", 'category_type': 'shoes', 'gender': 'kids', 'size_type': 'shoes'},
                {'name': "Baby Booties", 'category_type': 'babyshop', 'gender': 'babies', 'size_type': 'baby'},
                
                # Bedding
                {'name': 'Bed Sheets', 'category_type': 'bedding', 'gender': 'unisex', 'size_type': 'bedding'},
                {'name': 'Comforters', 'category_type': 'bedding', 'gender': 'unisex', 'size_type': 'bedding'},
                {'name': 'Pillows', 'category_type': 'bedding', 'gender': 'unisex', 'size_type': 'none'},
                {'name': 'Duvet Covers', 'category_type': 'bedding', 'gender': 'unisex', 'size_type': 'bedding'},
                {'name': 'Blankets', 'category_type': 'bedding', 'gender': 'unisex', 'size_type': 'bedding'},
                
                # Cosmetics
                {'name': 'Hair Care', 'category_type': 'cosmetics', 'gender': 'unisex', 'size_type': 'none'},
                {'name': 'Hair Styling', 'category_type': 'cosmetics', 'gender': 'unisex', 'size_type': 'none'},
                {'name': 'Skincare', 'category_type': 'cosmetics', 'gender': 'unisex', 'size_type': 'none'},
                {'name': 'Makeup', 'category_type': 'cosmetics', 'gender': 'women', 'size_type': 'none'},
                {'name': 'Fragrances', 'category_type': 'cosmetics', 'gender': 'unisex', 'size_type': 'none'},
                
                # Accessories
                {'name': 'Handbags', 'category_type': 'bags', 'gender': 'women', 'size_type': 'none'},
                {'name': 'Backpacks', 'category_type': 'bags', 'gender': 'unisex', 'size_type': 'none'},
                {'name': 'Jewelry', 'category_type': 'jewelry', 'gender': 'unisex', 'size_type': 'none'},
                {'name': 'Watches', 'category_type': 'watches', 'gender': 'unisex', 'size_type': 'none'},
                {'name': 'Scarves', 'category_type': 'accessories', 'gender': 'unisex', 'size_type': 'none'},
                {'name': 'Belts', 'category_type': 'accessories', 'gender': 'unisex', 'size_type': 'none'},
                {'name': 'Hats', 'category_type': 'accessories', 'gender': 'unisex', 'size_type': 'none'},
                {'name': 'Sunglasses', 'category_type': 'accessories', 'gender': 'unisex', 'size_type': 'none'},
            ]
            
            created = []
            for cat_data in default_categories:
                category, created_flag = FashionCategory.objects.get_or_create(
                    tenant=tenant,
                    name=cat_data['name'],
                    defaults={
                        'category_type': cat_data['category_type'],
                        'gender': cat_data['gender'],
                        'size_type': cat_data['size_type'],
                        'is_active': True,
                    }
                )
                if created_flag:
                    created.append(cat_data['name'])
            
            if created:
                logger.info(f"Created default fashion categories: {', '.join(created)}")
                
        except Exception as e:
            logger.error(f"Error setting up default categories: {e}")