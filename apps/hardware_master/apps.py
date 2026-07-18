from django.apps import AppConfig

class HardwareMasterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.hardware_master'
    label = 'hardware_master'
    verbose_name = 'Hardware Master'