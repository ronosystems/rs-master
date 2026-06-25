# apps/shared/users/urls.py

from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('', views.user_list, name='user_list'),
    path('add/', views.add_user, name='add_user'),
    path('<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('<int:user_id>/toggle/', views.toggle_user_status, name='toggle_user_status'),
    path('<int:user_id>/profile/', views.user_profile, name='user_profile'),
    path('profile/', views.user_profile, name='my_profile'),
]