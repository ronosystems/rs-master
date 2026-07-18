from django.apps import AppConfig

class CarwashMasterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.carwash_master'
    label = 'carwash_master'
    verbose_name = 'Carwash Master'