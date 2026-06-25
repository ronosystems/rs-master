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
    path('platform-settings/', views.platform_settings, name='platform_settings'),
    path('platform-settings/stats/', views.platform_settings_stats, name='platform_settings_stats'),
    
    # ============================================
    # MAINTENANCE MODE
    # ============================================
    path('maintenance/', views.maintenance_page, name='maintenance'),
    path('toggle-maintenance/', views.toggle_maintenance_mode, name='toggle_maintenance'),
    
    # ============================================
    # PROJECT MASTER DASHBOARDS
    # ============================================
    path('tech/dashboard/', views.tech_dashboard, name='tech_dashboard'),
    path('tech/pos/', views.tech_pos, name='tech_pos'),
    path('tech/reports/', views.report_dashboard, name='report_dashboard'),
    path('analytics/', views.platform_analytics, name='platform_analytics'),
    
    # ============================================
    # HOTEL MASTER
    # ============================================
    path('hotel/dashboard/', views.hotel_dashboard, name='hotel_dashboard'),
    path('hotel/rooms/', views.hotel_rooms, name='hotel_rooms'),
    path('hotel/rooms/add/', views.hotel_add_room, name='hotel_add_room'),
    path('hotel/bookings/', views.hotel_bookings, name='hotel_bookings'),
    path('hotel/bookings/new/', views.hotel_new_booking, name='hotel_new_booking'),
    path('hotel/guests/', views.hotel_guests, name='hotel_guests'),
    path('hotel/checkin/', views.hotel_checkin, name='hotel_checkin'),
    path('hotel/checkout/', views.hotel_checkout, name='hotel_checkout'),
    
    # ============================================
    # FOOD MASTER
    # ============================================
    path('food/dashboard/', views.food_dashboard, name='food_dashboard'),
    path('food/menu/', views.food_menu, name='food_menu'),
    path('food/orders/', views.food_orders, name='food_orders'),
    path('food/tables/', views.food_tables, name='food_tables'),
    path('food/kitchen/', views.food_kitchen, name='food_kitchen'),
    
    # ============================================
    # RETAIL MASTER
    # ============================================
    path('retail/dashboard/', views.retail_dashboard, name='retail_dashboard'),
    
    # ============================================
    # HEALTH MASTER
    # ============================================
    path('health/dashboard/', views.health_dashboard, name='health_dashboard'),
    
    # ============================================
    # FASHION MASTER
    # ============================================
    path('fashion/dashboard/', views.fashion_dashboard, name='fashion_dashboard'),
    
    # ============================================
    # USER MANAGEMENT (Portal)
    # ============================================
    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.add_user, name='add_user'),
    
    # ============================================
    # MANAGER DASHBOARD
    # ============================================
    path('manager-dashboard/', views.manager_dashboard, name='manager_dashboard'),
]