from django.urls import path
from apps.shared.portal import views as portal_views

app_name = 'retail_master'

urlpatterns = [
    path('', portal_views.retail_dashboard, name='dashboard'),
]
