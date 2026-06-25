# apps/shared/settings/urls.py

from django.urls import path
from . import views

app_name = 'settings'

urlpatterns = [
    path('receipt/', views.receipt_settings, name='receipt_settings'),
    path('profile/', views.profile_settings, name='profile_settings'),
    path('system/', views.system_settings, name='system_settings'),
    path('system/update/', views.update_system_settings, name='update_system_settings'),
    path('system/export/', views.system_settings_export, name='system_settings_export'),
]