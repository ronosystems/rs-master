# apps/shared/portal/middleware.py

from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache


class ProjectTypeMiddleware:
    """
    Middleware to detect and store the user's project type in session.
    This runs on every request to ensure the correct project is loaded.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip for login, logout, admin, and static paths
        path = request.path
        skip_paths = ['/login/', '/logout/', '/admin/', '/static/', '/media/']
        if any(path.startswith(skip) for skip in skip_paths):
            return self.get_response(request)
        
        # If user is authenticated, detect their project
        if request.user and request.user.is_authenticated:
            tenant = getattr(request.user, 'tenant', None)
            
            if tenant:
                project_type = getattr(tenant, 'project_type', None)
                
                if project_type:
                    project_code = project_type.code.upper()
                    
                    # Store in session if not already set
                    if request.session.get('project_code') != project_code:
                        request.session['project_code'] = project_code
                        request.session['project_name'] = project_type.name
                        request.session['project_template_dir'] = project_type.code.lower()
                        
                        # Also set a cookie for JavaScript
                        request.session['user_project'] = {
                            'code': project_code,
                            'name': project_type.name,
                            'template_dir': project_type.code.lower(),
                        }
                        
                        # ✅ Check if user is on the correct project and redirect if needed
                        redirect_response = self._redirect_to_correct_project(request, project_code)
                        if redirect_response:
                            return redirect_response
        
        return self.get_response(request)
    
    def _redirect_to_correct_project(self, request, project_code):
        """Redirect user to the correct project if they're on the wrong one"""
        current_path = request.path
        
        # Define the correct base path for each project
        project_paths = {
            'TECH_MASTER': '/tech/',
            'HOTEL_MASTER': '/hotel/',
            'FOOD_MASTER': '/food/',
            'RETAIL_MASTER': '/retail/',
            'HEALTH_MASTER': '/health/',
            'FASHION_MASTER': '/fashion/',
            'RENTAL_MASTER': '/rental/',  # ✅ ADD RENTAL MASTER
        }
        
        correct_path = project_paths.get(project_code, '/')
        
        # ✅ Don't redirect if already on the correct path
        if current_path.startswith(correct_path):
            return None
        
        # ✅ Don't redirect if on shared paths
        shared_paths = ['/users/', '/permissions/', '/settings/', '/tenants/']
        if any(current_path.startswith(path) for path in shared_paths):
            return None
        
        # ✅ Don't redirect if on admin or login
        if current_path.startswith('/admin/') or current_path.startswith('/login/'):
            return None
        
        # ✅ Check if user is on a different project path
        for code, path_prefix in project_paths.items():
            if code != project_code and current_path.startswith(path_prefix):
                # Redirect from wrong project to correct one
                new_path = current_path.replace(path_prefix, correct_path)
                return redirect(new_path)
        
        # ✅ If user is on root or unknown path, redirect to their project dashboard
        if current_path == '/' or current_path == '':
            return redirect(correct_path)
        
        return None


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