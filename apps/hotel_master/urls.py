# apps/hotel_master/urls.py
from django.urls import path
from . import views

app_name = 'hotel_master'

urlpatterns = [
    # ============================================
    # DASHBOARD
    # ============================================
    path('', views.dashboard, name='dashboard'),
    path('pos/', views.pos, name='pos'),
    
    # ============================================
    # ROOMS
    # ============================================
    path('rooms/', views.rooms, name='rooms'),
    path('rooms/status/', views.room_status, name='room_status'),
    path('rooms/add/', views.add_room, name='add_room'),
    path('rooms/<int:room_id>/edit/', views.edit_room_view, name='edit_room'),
    
    # ============================================
    # BOOKINGS
    # ============================================
    path('bookings/', views.bookings, name='bookings'),
    path('bookings/new/', views.new_booking, name='new_booking'),
    
    # ============================================
    # GUESTS
    # ============================================
    path('guests/', views.guests, name='guests'),
    
    # ============================================
    # CHECK IN / CHECK OUT
    # ============================================
    path('checkin/', views.checkin, name='checkin'),
    path('checkin/quick/', views.quick_checkin, name='quick_checkin'), 
    path('checkout/', views.checkout, name='checkout'),

    # ============================================
    # API ENDPOINTS
    # ============================================
    # Booking APIs
    path('api/booking/<int:booking_id>/', views.api_booking_detail, name='api_booking_detail'),
    path('api/booking/<int:booking_id>/edit/', views.api_edit_booking, name='api_edit_booking'),
    path('api/booking/<int:booking_id>/cancel/', views.api_cancel_booking, name='api_cancel_booking'),
    
    # Room APIs
    path('api/rooms/', views.api_rooms, name='api_rooms'),
    path('api/room/<int:room_id>/', views.api_room_detail, name='api_room_detail'),
    path('api/room/<int:room_id>/delete/', views.api_delete_room, name='api_delete_room'),
    path('api/room/<int:room_id>/edit/', views.api_edit_room, name='api_edit_room'),
    
    # Customer & Payment APIs
    path('api/search-customer/', views.api_search_customer, name='api_search_customer'),
    path('api/process-payment/', views.api_process_payment, name='api_process_payment'),
    path('api/assign-guest/', views.api_assign_guest, name='api_assign_guest'),

    # Guest/Booking action APIs
    path('api/booking/<int:booking_id>/checkin/', views.api_guest_checkin, name='api_guest_checkin'),
    path('api/booking/<int:booking_id>/checkout/', views.api_guest_checkout, name='api_guest_checkout'),
    path('api/booking/<int:booking_id>/delete/', views.api_delete_booking, name='api_delete_booking'),

    # ============================================
    # REPORTS - ADD THESE URLS
    # ============================================
    path('reports/occupancy/', views.occupancy_report, name='occupancy_report'),
    path('reports/revenue/', views.revenue_report, name='revenue_report'),
    path('reports/expenses/', views.expense_list, name='expense_list'),
    path('reports/dashboard/', views.report_dashboard, name='report_dashboard'),

    # ============================================
    # SETTINGS
    # ============================================
    path('settings/hotel/', views.hotel_settings, name='hotel_settings'), 
    path('settings/receipt/', views.receipt_settings, name='receipt_settings'),
    path('settings/profile/', views.profile_settings, name='profile_settings'),
]