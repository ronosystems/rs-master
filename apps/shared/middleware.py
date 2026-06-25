# apps/shared/middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class OfflineSyncMiddleware(MiddlewareMixin):
    """Handle offline/online mode switching and sync"""
    
    def process_request(self, request):
        # Check if we're online by pinging the database
        is_online = self.check_connection()
        
        # Update offline mode based on connection status
        if is_online and getattr(settings, 'OFFLINE_MODE', False):
            # We just came online
            settings.OFFLINE_MODE = False
            logger.info("🔄 Connection restored - switching to online mode")
            
            # Trigger sync if we were offline
            if hasattr(request, 'session') and request.session.get('was_offline', False):
                self.trigger_sync(request)
                request.session['was_offline'] = False
                
        elif not is_online and not getattr(settings, 'OFFLINE_MODE', False):
            # We just went offline
            settings.OFFLINE_MODE = True
            logger.warning("📴 Connection lost - switching to offline mode")
            if hasattr(request, 'session'):
                request.session['was_offline'] = True
        
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
    
    def trigger_sync(self, request):
        """Trigger PowerSync sync when coming online"""
        try:
            import requests
        except ImportError:
            logger.warning("⚠️ requests library not installed. Install with: pip install requests")
            return
        
        try:
            logger.info("🔄 Triggering sync...")
            
            tenant_id = None
            if hasattr(request, 'tenant'):
                tenant_id = request.tenant.id
            
            powersync_url = getattr(settings, 'POWERSYNC_URL', None)
            powersync_api_key = getattr(settings, 'POWERSYNC_API_KEY', None)
            
            if not powersync_url or not powersync_api_key:
                logger.warning("⚠️ PowerSync URL or API key not configured")
                return
            
            response = requests.post(
                f"{powersync_url}/sync",
                headers={
                    'Authorization': f'Bearer {powersync_api_key}',
                    'Content-Type': 'application/json'
                },
                json={'tenant_id': tenant_id} if tenant_id else {},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("✅ PowerSync sync triggered successfully")
                self.process_sync_queue(request)
            else:
                logger.error(f"❌ PowerSync sync failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Sync error: {e}")
    
    def process_sync_queue(self, request):
        """Process queued sync operations"""
        try:
            from apps.shared.models import SyncQueue
            from django.utils import timezone
            
            tenant_id = None
            if hasattr(request, 'tenant'):
                tenant_id = request.tenant.id
            
            if not tenant_id:
                return
            
            items = SyncQueue.objects.filter(
                tenant_id=tenant_id,
                synced=False
            ).order_by('created_at')[:getattr(settings, 'SYNC_BATCH_SIZE', 100)]
            
            for item in items:
                try:
                    item.process()
                    item.synced = True
                    item.synced_at = timezone.now()
                    item.save()
                except Exception as e:
                    item.error = str(e)
                    item.retry_count += 1
                    item.save()
            
            logger.info(f"✅ Processed sync queue")
            
        except Exception as e:
            logger.error(f"❌ Error processing sync queue: {e}")