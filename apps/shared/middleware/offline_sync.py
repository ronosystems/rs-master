# apps/shared/middleware/offline_sync.py
import threading
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class OfflineSyncMiddleware(MiddlewareMixin):
    """Automatically sync when connection is restored"""
    
    def process_request(self, request):
        # Check if we're online
        is_online = self.check_connection()
        
        # Store current state
        was_offline = getattr(settings, 'OFFLINE_MODE', False)
        
        if is_online:
            settings.OFFLINE_MODE = False
            # If we were offline, trigger auto-sync
            if was_offline:
                logger.info("🔄 Connection restored - Auto-syncing...")
                # Start sync in background
                self.trigger_auto_sync(request)
        else:
            settings.OFFLINE_MODE = True
            logger.info("📴 Offline mode activated")
        
        # Add to request for templates
        request.offline_mode = settings.OFFLINE_MODE
    
    def check_connection(self):
        """Check if we can connect to Neon"""
        try:
            import socket
            import os
            db_host = os.getenv('PGHOST', '')
            if db_host:
                socket.gethostbyname(db_host)
            return True
        except:
            return False
    
    def trigger_auto_sync(self, request):
        """Trigger auto-sync in background thread"""
        try:
            # Get tenant ID from request
            tenant_id = None
            if hasattr(request, 'tenant'):
                tenant_id = request.tenant.id
            
            # Start sync in background
            thread = threading.Thread(
                target=self.run_sync,
                args=(tenant_id,)
            )
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.error(f"❌ Failed to start auto-sync: {e}")
    
    def run_sync(self, tenant_id):
        """Run the sync process"""
        try:
            from apps.shared.utils.powersync_sync import sync_all
            
            # Sync all data
            result = sync_all(tenant_id)
            
            if result:
                logger.info("✅ Auto-sync completed successfully")
            else:
                logger.warning("⚠️ Auto-sync completed with errors")
                
        except Exception as e:
            logger.error(f"❌ Auto-sync error: {e}")