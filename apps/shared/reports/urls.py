
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Tech Master Reports
    path('tronic/dashboard/', views.tech_report_dashboard, name='tech_dashboard'),
    path('tronic/inventory/', views.tech_inventory_report, name='tech_inventory_report'),
    path('tronic/sales/', views.tech_sales_report, name='tech_sales_report'),
    
    # Hotel Master Reports (if you want to consolidate)
    path('hotel/occupancy/', views.hotel_occupancy_report, name='hotel_occupancy_report'),
    path('hotel/revenue/', views.hotel_revenue_report, name='hotel_revenue_report'),
]