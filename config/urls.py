# config/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.http import JsonResponse

urlpatterns = [
    # ============================================
    # ADMIN
    # ============================================
    path('admin/', admin.site.urls),

    # ============================================
    # PORTAL (Main entry point)
    # ============================================
    path('', include('apps.shared.portal.urls', namespace='portal')),

    # ============================================
    # TENANTS (Separate app for tenant management)
    # ============================================
    path('tenants/', include('apps.shared.tenants.urls', namespace='tenants')),

    # ============================================
    # USERS (Separate app for user management)
    # ============================================
    path('users/', include('apps.shared.users.urls', namespace='users')),
    path('permissions/', include('apps.shared.permissions.urls', namespace='permissions')),

    # ============================================
    # CHAT
    # ============================================
    path('chats/', include('apps.shared.chats.urls', namespace='chats')),

    # ============================================
    # SETTINGS
    # ============================================
    path('settings/', include('apps.shared.settings.urls', namespace='settings')),

    # ============================================
    # PROJECTS
    # ============================================
    path('tronic/', include('apps.tronic_master.urls', namespace='tronic_master')),
    path('hotel/', include('apps.hotel_master.urls', namespace='hotel_master')),
    path('food/', include('apps.food_master.urls', namespace='food_master')),
    path('retail/', include('apps.retail_master.urls', namespace='retail_master')),
    path('health/', include('apps.health_master.urls', namespace='health_master')),
    path('fashion/', include('apps.fashion_master.urls', namespace='fashion_master')),
    path('rental/', include('apps.rental_master.urls', namespace='rental_master')),

    # ============================================
    # FAVICON
    # ============================================
    path('favicon.ico', lambda request: HttpResponse(status=204)),

    path('api/powersync/', include('apps.shared.powersync.urls')),


    # Handle Chrome DevTools well-known endpoint
    path('.well-known/appspecific/com.chrome.devtools.json',
         lambda request: JsonResponse({}),
         name='chrome_devtools'),
]

# ============================================
# STATIC & MEDIA FILES (Development only)
# ============================================
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)