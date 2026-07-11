# apps/shared/permissions/urls.py

from django.urls import path
from . import views

app_name = 'permissions'

urlpatterns = [
    # Role Management
    path('roles/', views.role_list, name='role_list'),
    path('roles/create/', views.role_create, name='role_create'),
    path('roles/<int:role_id>/edit/', views.role_edit, name='role_edit'),
    path('roles/<int:role_id>/delete/', views.role_delete, name='role_delete'),
    
    # User Role Assignments
    path('users/<int:user_id>/roles/', views.user_roles, name='user_roles'),
    path('users/<int:user_id>/roles/assign/', views.assign_user_role, name='assign_user_role'),
    path('roles/<int:role_id>/view/', views.role_view, name='role_view'),
    path('users/<int:user_id>/roles/remove/<int:role_id>/', views.remove_user_role, name='remove_user_role'),
    
    # System Permissions
    path('system/', views.system_permissions, name='system_permissions'),
    path('system/sync/', views.sync_permissions, name='sync_permissions'),
    
    # API
    path('api/check/<str:permission_codename>/', views.check_permission, name='check_permission'),
    path('api/user/permissions/', views.get_user_permissions, name='get_user_permissions'),
    path('api/user/roles/', views.get_user_roles, name='get_user_roles'),
]