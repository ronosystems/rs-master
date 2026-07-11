# apps/shared/portal/urls.py

from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    # ============================================
    # AUTHENTICATION
    # ============================================
    path('login/', views.portal_login, name='login'),
    path('logout/', views.portal_logout, name='logout'),
    path('debug/', views.debug_redirect, name='debug'), 
    
    # ============================================
    # USER PROFILE
    # ============================================
    path('profile/', views.profile, name='profile'),
    path('change-password/', views.change_password, name='change_password'),
    
    # ============================================
    # DASHBOARD ROUTER
    # ============================================
    path('', views.project_dashboard, name='dashboard'),
    
    # ============================================
    # SUPER ADMIN
    # ============================================
    path('super-admin/', views.super_admin_dashboard, name='super_admin_dashboard'),
    
    # ============================================
    # PLATFORM SETTINGS
    # ============================================
    path('analytics/', views.platform_analytics, name='analytics'),
    path('platform-analytics/', views.platform_analytics, name='platform_analytics'),
    path('platform-settings/', views.platform_settings, name='platform_settings'),
    path('platform-settings/stats/', views.platform_settings_stats, name='platform_settings_stats'),
    
    # ============================================
    # MAINTENANCE MODE
    # ============================================
    path('maintenance/', views.maintenance_page, name='maintenance'),
    path('toggle-maintenance/', views.toggle_maintenance_mode, name='toggle_maintenance'),
    path('support/', views.support, name='support'),
    
    # ============================================
    # MANAGER DASHBOARD
    # ============================================
    path('manager-dashboard/', views.manager_dashboard, name='manager_dashboard'),

    # ============================================
    # FALLBACK PAGE
    # ============================================
    path('no-project/', views.no_project_assigned, name='no_project_assigned'),

    # ============================================
    # LIVE CHAT
    # ============================================
    path('live-chat/', views.live_chat, name='live_chat'),

    # Support Pages
    path('support/', views.support, name='support'),
    path('docs/', views.documentation, name='documentation'),
    path('tutorials/', views.tutorials, name='tutorials'),
    path('support/tickets/', views.support_tickets, name='support_tickets'),
]