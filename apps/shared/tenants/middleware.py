# apps/shared/tenants/middleware.py

from django.utils.deprecation import MiddlewareMixin
from apps.shared.tenants.models import Tenant
import logging

logger = logging.getLogger(__name__)

class TenantMiddleware(MiddlewareMixin):
    """
    Middleware to handle tenant switching for super admins.
    Also ensures tenant is set on the request for all users.
    """
    
    def process_request(self, request):
        """Process request before view is called"""
        
        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return None
        
        # ✅ SUPER ADMIN: Handle tenant switching
        if request.user.is_super_admin:
            # Check if super admin is in preview mode
            if request.session.get('tenant_id'):
                try:
                    tenant = Tenant.objects.get(id=request.session['tenant_id'])
                    request.tenant = tenant
                    request.user.tenant = tenant
                except (Tenant.DoesNotExist, AttributeError) as e:
                    logger.warning(f"Super admin preview tenant not found: {e}")
                    request.session.pop('tenant_id', None)
            # Super admin doesn't need a tenant assigned
            return None
        
        # ✅ REGULAR USER: Check tenant assignment
        if hasattr(request.user, 'tenant') and request.user.tenant:
            request.tenant = request.user.tenant
        else:
            # No tenant assigned - will be handled by decorators
            pass
        
        return None
    
    def process_response(self, request, response):
        """Process response after view is called"""
        return response