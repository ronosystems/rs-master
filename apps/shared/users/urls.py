# apps/shared/users/urls.py

from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Super Admin Dashboard
    path('super-admin/', views.super_admin_dashboard, name='super_admin_dashboard'),
    
    # Tenant Management (Super Admin only)
    path('tenants/', views.tenant_list, name='tenant_list'),
    path('tenants/create/', views.tenant_create, name='tenant_create'),
    path('tenants/<int:tenant_id>/edit/', views.tenant_edit, name='tenant_edit'),
    path('tenants/<int:tenant_id>/delete/', views.tenant_delete, name='tenant_delete'),
    path('tenants/<int:tenant_id>/assign-project/', views.tenant_assign_project, name='tenant_assign_project'),
    path('tenants/<int:tenant_id>/assign-subscription/', views.tenant_assign_subscription, name='tenant_assign_subscription'),
    
    # User Management (Super Admin & Tenant Admin)
    path('', views.user_list, name='user_list'),
    path('create/', views.user_create, name='user_create'),
    path('<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('<int:user_id>/delete/', views.user_delete, name='user_delete'),
    path('<int:user_id>/toggle-status/', views.user_toggle_status, name='user_toggle_status'),
    
    # Role Management (Tenant Admin only)
    path('roles/', views.role_list, name='role_list'),
]