# apps/rental_master/apps.py

from django.apps import AppConfig


class RentalMasterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.rental_master'
    verbose_name = 'Rental Master'
    label = 'rental_master'