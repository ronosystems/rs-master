from django.urls import path
from . import views

urlpatterns = [
    path('open/', views.open_drawer, name='open_drawer'),
    path('history/', views.drawer_history, name='drawer_history'),
    path('<int:drawer_id>/', views.drawer_detail, name='drawer_detail'),
    path('<int:drawer_id>/close/', views.close_drawer, name='close_drawer'),
    path('<int:drawer_id>/add-transaction/', views.add_transaction, name='add_transaction'),
]
