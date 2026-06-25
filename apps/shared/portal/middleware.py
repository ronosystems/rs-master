# apps/shared/portal/middleware.py

from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache


class MaintenanceModeMiddleware(MiddlewareMixin):
    """Middleware to handle maintenance mode"""
    
    # URL patterns that should be accessible
    ALLOWED_PATHS = [
        '/login/',
        '/logout/',
        '/maintenance/',
        '/admin/',
        '/static/',
        '/media/',
        '/favicon.ico',
    ]
    
    def process_request(self, request):
        # Skip if user is super admin
        if request.user and request.user.is_authenticated and request.user.is_superuser:
            return None
        
        # Check if maintenance mode is enabled
        if self.is_maintenance_mode():
            # Skip allowed URLs
            if self.is_allowed_path(request.path):
                return None
            
            # Redirect to maintenance page
            try:
                return redirect(reverse('portal:maintenance'))
            except NoReverseMatch:
                return redirect('/maintenance/')
        
        return None
    
    def is_maintenance_mode(self):
        """Check if maintenance mode is enabled"""
        # Check cache first
        maintenance_mode = cache.get('maintenance_mode', False)
        
        # If not in cache, check database
        if not maintenance_mode:
            try:
                from apps.shared.settings.models import SystemSetting
                db_value = SystemSetting.get('maintenance_mode', 'False')
                maintenance_mode = db_value == 'True'
                if maintenance_mode:
                    # Update cache
                    cache.set('maintenance_mode', True, timeout=None)
            except Exception:
                pass
        
        return maintenance_mode
    
    def is_allowed_path(self, path):
        """Check if path is allowed during maintenance"""
        for allowed in self.ALLOWED_PATHS:
            if path.startswith(allowed):
                return True
        return False