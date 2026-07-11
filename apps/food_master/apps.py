# apps/food_master/apps.py

from django.apps import AppConfig


class FoodMasterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.food_master'
    label = 'food_master'
    verbose_name = 'Food Master'