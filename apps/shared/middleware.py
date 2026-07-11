# apps/shared/middleware.py

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class TenantMiddleware:
    """
    Middleware to set tenant on request.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("✅ TenantMiddleware initialized")
    
    def __call__(self, request):
        # ✅ Skip tenant detection for certain paths
        skip_paths = [
            '/admin/',
            '/login/',
            '/logout/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/robots.txt',
            '/chats/api/',
            '/api/',
            '/select-tenant/',
            '/no-tenant/',
            '/super-admin/', 
            '/profile/',       
        ]
        
        path = request.path
        for skip_path in skip_paths:
            if path.startswith(skip_path):
                response = self.get_response(request)
                return response
        
        # ✅ Also skip if user is super admin (they don't need tenant)
        if request.user.is_authenticated and request.user.is_superuser:
            # Super admins don't need tenant, but we still set request.tenant = None
            request.tenant = None
            response = self.get_response(request)
            return response
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if tenant:
            request.tenant = tenant
            if hasattr(request, 'session'):
                request.session['tenant_id'] = tenant.id
            logger.debug(f"✅ Tenant set: {tenant.company_name} (ID: {tenant.id})")
        else:
            # ✅ Only log warning for non-API paths and non-super-admin paths
            if not path.startswith('/chats/') and not path.startswith('/api/') and not request.user.is_superuser:
                logger.warning(f"⚠️ No tenant found for request: {path}")
        
        response = self.get_response(request)
        return response
    
    def get_tenant_from_request(self, request):
        """Extract tenant from request using multiple methods"""
        try:
            from apps.shared.tenants.models import Tenant
        except ImportError:
            try:
                from .tenants.models import Tenant
            except ImportError:
                logger.error("❌ Could not import Tenant model")
                return None
        
        # Method 1: From subdomain (e.g., tenant1.localhost:8000)
        host = request.get_host()
        parts = host.split('.')
        if len(parts) >= 3:
            subdomain = parts[0]
            try:
                tenant = Tenant.objects.get(code=subdomain)
                logger.debug(f"✅ Found tenant by subdomain: {subdomain}")
                return tenant
            except Tenant.DoesNotExist:
                pass
            except Exception as e:
                logger.error(f"❌ Error finding tenant by subdomain: {e}")
        
        # Method 2: From header (X-Tenant-ID)
        tenant_header = request.headers.get('X-Tenant-ID')
        if tenant_header:
            try:
                tenant = Tenant.objects.get(id=tenant_header)
                logger.debug(f"✅ Found tenant by header: {tenant_header}")
                return tenant
            except (Tenant.DoesNotExist, ValueError):
                pass
            except Exception as e:
                logger.error(f"❌ Error finding tenant by header: {e}")
        
        # Method 3: From session
        if hasattr(request, 'session'):
            tenant_id = request.session.get('tenant_id')
            if tenant_id:
                try:
                    tenant = Tenant.objects.get(id=tenant_id)
                    logger.debug(f"✅ Found tenant by session: {tenant_id}")
                    return tenant
                except (Tenant.DoesNotExist, ValueError):
                    pass
                except Exception as e:
                    logger.error(f"❌ Error finding tenant by session: {e}")
        
        # Method 4: From URL parameter (for testing)
        tenant_param = request.GET.get('tenant_id')
        if tenant_param:
            try:
                tenant = Tenant.objects.get(id=tenant_param)
                logger.debug(f"✅ Found tenant by URL param: {tenant_param}")
                return tenant
            except (Tenant.DoesNotExist, ValueError):
                pass
            except Exception as e:
                logger.error(f"❌ Error finding tenant by URL param: {e}")
        
        # Method 5: From user's tenant (skip for super admins)
        if request.user.is_authenticated and not request.user.is_superuser:
            if hasattr(request.user, 'tenant'):
                tenant = request.user.tenant
                if tenant:
                    logger.debug(f"✅ Found tenant from user: {tenant.company_name}")
                    return tenant
        
        return None


class OfflineSyncMiddleware:
    """
    Middleware to handle offline/online mode switching.
    Simple middleware without MiddlewareMixin.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("✅ OfflineSyncMiddleware initialized")
    
    def __call__(self, request):
        # Add offline mode to request
        request.offline_mode = getattr(settings, 'OFFLINE_MODE', False)
        
        response = self.get_response(request)
        return response
    
    def process_request(self, request):
        """Process request - check connection status"""
        # Check if we're online
        is_online = self.check_connection()
        
        # Update offline mode based on connection status
        if is_online and getattr(settings, 'OFFLINE_MODE', False):
            settings.OFFLINE_MODE = False
            logger.info("🔄 Connection restored - switching to online mode")
            
        elif not is_online and not getattr(settings, 'OFFLINE_MODE', False):
            settings.OFFLINE_MODE = True
            logger.warning("📴 Connection lost - switching to offline mode")
        
        # Add offline mode to request
        request.offline_mode = getattr(settings, 'OFFLINE_MODE', False)
    
    def check_connection(self):
        """Check if we can connect to the database"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.debug(f"Connection check failed: {e}")
            return False


# Alias for backward compatibility
OfflineMiddleware = OfflineSyncMiddleware