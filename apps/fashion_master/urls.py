from django.urls import path
from apps.shared.portal import views as portal_views

app_name = 'fashion_master'

urlpatterns = [
    path('', portal_views.fashion_dashboard, name='dashboard'),
]
