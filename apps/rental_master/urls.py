# apps/rental_master/urls.py

from django.urls import path
from . import views

app_name = 'rental_master'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Branches
    path('branches/', views.branches, name='branches'),
    path('branches/add/', views.add_branch, name='add_branch'),
    path('branches/<int:branch_id>/', views.branch_detail, name='branch_detail'),
    
    # Properties
    path('properties/', views.properties, name='properties'),
    path('properties/add/', views.add_property, name='add_property'),
    path('properties/<int:property_id>/', views.property_detail, name='property_detail'),
    
    # Units
    path('units/', views.units, name='units'),
    path('units/add/', views.add_unit, name='add_unit'),
    path('units/<int:unit_id>/', views.unit_detail, name='unit_detail'),
    path('api/units-data/', views.get_units_data, name='units_data'),
    
    # Tenants
    path('tenants/', views.tenants_list, name='tenants'),
    path('tenants/add/', views.add_tenant, name='add_tenant'),
    path('tenants/<int:tenant_id>/', views.tenant_detail, name='tenant_detail'),
    path('tenants/<int:tenant_id>/vacate/', views.vacate_tenant, name='vacate_tenant'),
    
    # Leases
    path('leases/', views.leases, name='leases'),
    path('leases/create/', views.create_lease, name='create_lease'),
    
    # Payments
    path('payments/', views.payments, name='payments'),
    path('payments/record/', views.record_payment, name='record_payment'),
    
    # Deposits
    path('deposits/', views.deposits, name='deposits'),
    
    # Reports
    path('reports/occupancy/', views.occupancy_report, name='occupancy_report'),
    path('reports/revenue/', views.revenue_report, name='revenue_report'),
    path('reports/rent-collection/', views.rent_collection, name='rent_collection'),
    path('reports/export/', views.export_reports, name='export_reports'),
    
    # Settings
    path('settings/room-sizes/', views.room_sizes, name='room_sizes'),
    path('settings/property-types/', views.property_types, name='property_types'),
    
    # Maintenance (Caretaker)
    path('maintenance/requests/', views.maintenance_requests, name='maintenance_requests'),
    path('maintenance/new/', views.new_request, name='new_request'),
    path('maintenance/tasks/', views.task_list, name='task_list'),
    path('maintenance/<int:request_id>/', views.maintenance_detail, name='maintenance_detail'),
    path('maintenance/<int:request_id>/update-status/', views.update_maintenance_status, name='update_maintenance_status'),
]