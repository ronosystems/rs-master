from django.urls import path
from apps.shared.portal import views as portal_views

app_name = 'food_master'

urlpatterns = [
    path('', portal_views.food_dashboard, name='dashboard'),
    path('menu/', portal_views.food_menu, name='menu'),
    path('orders/', portal_views.food_orders, name='orders'),
    path('tables/', portal_views.food_tables, name='tables'),
    path('kitchen/', portal_views.food_kitchen, name='kitchen'),
]
