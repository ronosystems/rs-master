# apps/shared/settings/urls.py

from django.urls import path
from . import views

app_name = 'settings'

urlpatterns = [
    path('company/', views.company_settings, name='company_settings'),
    path('receipt/', views.receipt_settings, name='receipt_settings'),
    path('profile/', views.profile_settings, name='profile_settings'),
    path('change-pin/', views.change_pin, name='change_pin'),
    path('system/', views.system_settings, name='system_settings'),
    path('system/update/', views.update_system_settings, name='update_system_settings'),
    path('system/export/', views.system_settings_export, name='system_settings_export'),
    # Payment Settings
    path('payment-settings/', views.payment_settings_view, name='payment_settings'),
    path('api/payment-settings/', views.api_payment_settings, name='api_payment_settings'),
    path('api/payment-settings/update/', views.api_update_payment_settings, name='api_update_payment_settings'),
    path('api/payment-methods/', views.api_payment_methods, name='api_payment_methods'),
]