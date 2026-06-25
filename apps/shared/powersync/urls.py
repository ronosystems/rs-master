from django.urls import path
from .views import PowerSyncTokenView, PowerSyncSyncView

urlpatterns = [
    path('token/', PowerSyncTokenView.as_view(), name='powersync-token'),
    path('sync/', PowerSyncSyncView.as_view(), name='powersync-sync'),
]
