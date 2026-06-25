# config/db_routers.py
from django.conf import settings

class OfflineRouter:
    """
    A router to control which database to use based on online/offline mode.
    """
    
    # Models that should be cached offline
    OFFLINE_MODELS = [
        'Product', 'Category', 'Branch', 'Sale', 'SaleItem',
        'Customer', 'User', 'Tenant', 'Inventory', 'PriceList'
    ]
    
    def db_for_read(self, model, **hints):
        """Use offline cache if in offline mode"""
        if getattr(settings, 'OFFLINE_MODE', False):
            if model.__name__ in self.OFFLINE_MODELS:
                return 'offline_cache'
        return 'default'
    
    def db_for_write(self, model, **hints):
        """Always write to default, queue for sync if offline"""
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations between default and offline_cache"""
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Allow migrations on both databases"""
        if db == 'offline_cache':
            return model_name in self.OFFLINE_MODELS
        return db == 'default'