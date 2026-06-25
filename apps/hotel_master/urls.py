from django.urls import path
from apps.shared.portal import views as portal_views

app_name = 'hotel_master'

urlpatterns = [
    path('', portal_views.hotel_dashboard, name='dashboard'),
    path('rooms/', portal_views.hotel_rooms, name='rooms'),
    path('rooms/add/', portal_views.hotel_add_room, name='add_room'),
    path('bookings/', portal_views.hotel_bookings, name='bookings'),
    path('bookings/new/', portal_views.hotel_new_booking, name='new_booking'),
    path('guests/', portal_views.hotel_guests, name='guests'),
    path('checkin/', portal_views.hotel_checkin, name='checkin'),
    path('checkout/', portal_views.hotel_checkout, name='checkout'),
]
