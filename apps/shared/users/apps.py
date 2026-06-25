# apps/shared/users/apps.py

from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.shared.users'
    label = 'users'  # ✅ ADD THIS - allows 'users.User'