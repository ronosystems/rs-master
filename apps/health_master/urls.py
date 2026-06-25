from django.urls import path
from apps.shared.portal import views as portal_views

app_name = 'health_master'

urlpatterns = [
    path('', portal_views.health_dashboard, name='dashboard'),
]
