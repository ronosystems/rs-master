# apps/food_master/urls.py

from django.urls import path
from . import views

app_name = 'food_master'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Branches
    path('branches/', views.branches, name='branches'),
    path('branches/add/', views.add_branch, name='add_branch'),
    path('branches/<int:branch_id>/', views.branch_detail, name='branch_detail'),
    path('branches/<int:branch_id>/toggle/', views.toggle_branch, name='toggle_branch'),
    
    # Categories
    path('categories/', views.categories, name='categories'),
    path('categories/add/', views.add_category, name='add_category'),
    path('categories/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('categories/<int:category_id>/delete/', views.delete_category, name='delete_category'),
    
    # Menu Management
    path('menu/', views.menu_list, name='menu_list'),
    path('menu/add/', views.add_menu_item, name='add_menu_item'),
    path('menu/<int:item_id>/edit/', views.edit_menu_item, name='edit_menu_item'),
    path('menu/<int:item_id>/toggle/', views.toggle_menu_item, name='toggle_menu_item'),
    path('menu/<int:item_id>/delete/', views.delete_menu_item, name='delete_menu_item'),
    
    # Orders Management
    path('orders/', views.orders, name='orders'),
    path('orders/create/', views.create_order, name='create_order'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('menu-order/', views.menu_order, name='menu_order'),
    path('api/pos/place-order/', views.pos_place_order, name='pos_place_order'),
    path('order-receipt/<int:order_id>/', views.order_receipt, name='order_receipt'),

    
    # Tables
    path('tables/', views.tables, name='tables'),
    path('tables/add/', views.add_table, name='add_table'),
    
    # Reservations
    path('reservations/', views.reservations, name='reservations'),
    path('reservations/create/', views.create_reservation, name='create_reservation'),
    
    # Customers
    path('customers/', views.customers, name='customers'),
    path('customers/add/', views.add_customer, name='add_customer'),
    
    # Reports
    path('reports/', views.reports, name='reports'),

    # Purchases
    path('purchases/', views.purchases, name='purchases'),
    path('purchases/add/', views.add_purchase, name='add_purchase'),
    path('purchases/<int:purchase_id>/', views.purchase_detail, name='purchase_detail'),
    path('purchases/<int:purchase_id>/edit/', views.edit_purchase, name='edit_purchase'),
    path('purchases/<int:purchase_id>/delete/', views.delete_purchase, name='delete_purchase'),

    # PIN Verification
    path('verify-pin/', views.verify_pin_access, name='verify_pin_access'),
    path('logout-pin-session/', views.logout_pin_session, name='logout_pin_session'),
    path('api/pos/verify-pin/', views.verify_waiter_pin, name='verify_waiter_pin'),
    path('pos/waiter-login/', views.waiter_login, name='waiter_login'),
    path('pos/waiter-logout/', views.waiter_logout, name='waiter_logout'),
    path('pos/create-order/', views.create_order, name='create_order'),

    # Payment Management
    path('payment/', views.payment_dashboard, name='payment_dashboard'),
    path('api/payment/search-order/', views.payment_search_order, name='payment_search_order'),
    path('api/payment/search-suggestions/', views.payment_search_suggestions, name='payment_search_suggestions'),
    path('api/payment/confirm-payment/', views.payment_confirm, name='payment_confirm'),
  

    # Role & Permission Management
    path('roles/', views.role_list, name='role_list'),
    path('roles/create/', views.create_role, name='create_role'),
    path('roles/<int:role_id>/edit/', views.edit_role, name='edit_role'),
    path('roles/<int:role_id>/delete/', views.delete_role, name='delete_role'),
    path('roles/assign/', views.assign_role_to_user, name='assign_role'),
    path('roles/remove/<int:assignment_id>/', views.remove_user_role, name='remove_user_role'),
    path('roles/user/<int:user_id>/', views.user_roles, name='user_roles'),
]