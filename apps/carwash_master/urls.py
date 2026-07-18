from django.urls import path
from . import views

app_name = 'carwash_master'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Services
    path('services/', views.service_list, name='services'),
    path('services/create/', views.service_create, name='service_create'),
    
    # Vehicles
    path('vehicles/', views.vehicle_list, name='vehicles'),
    path('vehicles/create/', views.vehicle_create, name='vehicle_create'),
    
    # Bookings
    path('bookings/', views.booking_list, name='bookings'),
    path('bookings/create/', views.booking_create, name='booking_create'),
    path('bookings/<int:booking_id>/', views.booking_detail, name='booking_detail'),
    path('bookings/<int:booking_id>/update-status/', views.booking_update_status, name='booking_update_status'),
    
    # Employees
    path('employees/', views.employee_list, name='employees'),
    path('employees/create/', views.employee_create, name='employee_create'),
    
    # Inventory
    path('inventory/', views.inventory_list, name='inventory'),
    path('inventory/create/', views.inventory_create, name='inventory_create'),
]