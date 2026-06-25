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
    
    # ============================================
    # SETTINGS
    # ============================================
    path('settings/', include('apps.shared.settings.urls', namespace='settings')),
    
    # ============================================
    # TECH MASTER (Main app for Tech Master)
    # ============================================
    path('tech/', include('apps.tech_master.urls', namespace='tech_master')),
    
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