# apps/shared/utils/sync_helpers.py
from apps.shared.tenants.models import SyncQueue, OfflineCache
import logging
import requests
import json
from django.conf import settings
from django.utils import timezone
from apps.shared.tenants.models import SyncQueue, Tenant
import logging

logger = logging.getLogger(__name__)

POWERSYNC_URL = settings.POWERSYNC_URL

def get_powersync_token():
    """Get PowerSync token from settings"""
    # Try to get from settings first
    token = getattr(settings, 'POWERSYNC_JWT_TOKEN', None)
    if token:
        return token
    
    # Fallback: read from file
    try:
        with open('powersync_token.txt', 'r') as f:
            return f.read().strip()
    except:
        return None

def sync_all(tenant_id=None):
    """Full sync - push and pull"""
    logger.info("🔄 Starting full sync...")
    
    # First push local changes
    push_success = sync_push(tenant_id)
    
    # Then pull remote changes
    pull_success = sync_pull(tenant_id)
    
    return push_success and pull_success

def sync_push(tenant_id=None):
    """Push local changes to PowerSync"""
    token = get_powersync_token()
    if not token:
        logger.error("❌ No PowerSync token found")
        return False
    
    # Get unsynced items
    items = SyncQueue.objects.filter(synced=False)
    if tenant_id:
        items = items.filter(tenant_id=tenant_id)
    
    if not items.exists():
        logger.info("✅ No items to push")
        return True
    
    logger.info(f"📤 Pushing {items.count()} items...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    success_count = 0
    for item in items:
        try:
            data = {
                "model": item.model_name,
                "id": item.object_id,
                "operation": item.operation,
                "data": item.data,
                "tenant_id": item.tenant_id
            }
            
            response = requests.post(
                f"{POWERSYNC_URL}/sync/push",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code in [200, 201, 204]:
                item.synced = True
                item.synced_at = timezone.now()
                item.save()
                success_count += 1
                logger.debug(f"✅ Pushed: {item.model_name} #{item.object_id}")
            else:
                logger.error(f"❌ Failed to push: {item.model_name} - {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Error pushing {item.id}: {e}")
            item.error = str(e)
            item.retry_count += 1
            item.save()
    
    logger.info(f"📊 Pushed {success_count}/{items.count()} items")
    return success_count == items.count()

def sync_pull(tenant_id=None):
    """Pull remote changes from PowerSync"""
    token = get_powersync_token()
    if not token:
        logger.error("❌ No PowerSync token found")
        return False
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Get tenant info
    tenant = None
    if tenant_id:
        tenant = Tenant.objects.get(id=tenant_id)
    else:
        tenant = Tenant.objects.first()
    
    if not tenant:
        logger.warning("⚠️ No tenant found to sync")
        return False
    
    try:
        # Pull changes from PowerSync
        response = requests.get(
            f"{POWERSYNC_URL}/sync/pull",
            headers=headers,
            params={"tenant_id": tenant.id},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            count = len(data)
            logger.info(f"📥 Pulled {count} changes")
            
            # Process each change
            for change in data:
                try:
                    process_pulled_change(change, tenant)
                except Exception as e:
                    logger.error(f"❌ Failed to process change: {e}")
            
            return True
        else:
            logger.error(f"❌ Failed to pull: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error pulling data: {e}")
        return False

def process_pulled_change(change, tenant):
    """Process a change pulled from PowerSync"""
    from django.apps import apps
    
    model_name = change.get('model')
    operation = change.get('operation')
    data = change.get('data')
    object_id = change.get('id')
    
    if not model_name or not operation:
        return
    
    try:
        # Find the model
        model = None
        app_names = ['tronic_master.inventory', 'tronic_master.sales', 'shared.tenants', 'shared.users']
        for app_name in app_names:
            try:
                model = apps.get_model(app_name, model_name)
                break
            except LookupError:
                continue
        
        if not model:
            logger.warning(f"⚠️ Model {model_name} not found")
            return
        
        # Apply the change
        if operation == 'delete':
            model.objects.filter(id=object_id, tenant=tenant).delete()
            logger.debug(f"🗑️ Deleted {model_name} #{object_id}")
        elif operation in ['create', 'update']:
            obj, created = model.objects.update_or_create(
                id=object_id,
                tenant=tenant,
                defaults=data
            )
            logger.debug(f"✅ {'Created' if created else 'Updated'} {model_name} #{object_id}")
            
    except Exception as e:
        logger.error(f"❌ Error processing {model_name}: {e}")






def queue_for_sync(tenant, model_name, object_id, operation, data):
    """Queue an operation for sync when online"""
    try:
        existing = SyncQueue.objects.filter(
            tenant=tenant,
            model_name=model_name,
            object_id=object_id,
            synced=False
        ).first()
        
        if existing:
            existing.operation = operation
            existing.data = data
            existing.save()
            logger.debug(f"Updated sync queue item for {model_name} #{object_id}")
        else:
            SyncQueue.objects.create(
                tenant=tenant,
                model_name=model_name,
                object_id=object_id,
                operation=operation,
                data=data
            )
            logger.debug(f"Queued {operation} for {model_name} #{object_id}")
    except Exception as e:
        logger.error(f"Failed to queue sync item: {e}")

def cache_offline_data(tenant, model_name, object_id, data):
    """Cache data for offline use"""
    try:
        cache, created = OfflineCache.objects.update_or_create(
            tenant=tenant,
            model_name=model_name,
            object_id=object_id,
            defaults={
                'data': data,
                'version': 1,
            }
        )
        if not created:
            cache.version += 1
            cache.save()
        logger.debug(f"Cached {model_name} #{object_id} for offline use")
    except Exception as e:
        logger.error(f"Failed to cache offline data: {e}")

def get_offline_data(tenant, model_name, object_id):
    """Get cached offline data"""
    try:
        cache = OfflineCache.objects.get(
            tenant=tenant,
            model_name=model_name,
            object_id=object_id
        )
        return cache.data
    except OfflineCache.DoesNotExist:
        return None