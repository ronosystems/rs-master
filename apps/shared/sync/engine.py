# apps/shared/sync/engine.py
import os
import json
import requests
from django.conf import settings
from django.utils import timezone
from django.apps import apps
import logging

logger = logging.getLogger(__name__)

# ============================================
# SYNC ENGINE - PUSH & PULL
# ============================================

def get_sync_token():
    """Get the sync authentication token"""
    # Try to get from environment
    token = os.getenv('POWERSYNC_JWT_TOKEN', '')
    if token:
        return token
    
    # Try to read from file
    try:
        with open('powersync_token.txt', 'r') as f:
            return f.read().strip()
    except:
        return None

def get_sync_url():
    """Get the PowerSync URL"""
    return os.getenv('POWERSYNC_URL', 'https://6a38344d0ef84ed671a39215.powersync.journeyapps.com')


def sync_push(tenant_id=None):
    """
    Push all pending changes from SyncQueue to the server
    Returns: (success_count, failed_count)
    """
    from apps.shared.tenants.models import SyncQueue
    
    print("🔄 Starting PUSH sync...")
    logger.info("Starting PUSH sync...")
    
    # Get pending items
    items = SyncQueue.objects.filter(synced=False)
    if tenant_id:
        items = items.filter(tenant_id=tenant_id)
    
    count = items.count()
    if count == 0:
        print("✅ No pending items to sync")
        logger.info("✅ No pending items to sync")
        return 0, 0
    
    print(f"📤 Pushing {count} items...")
    logger.info(f"📤 Pushing {count} items...")
    
    success = 0
    failed = 0
    
    # Get token
    token = get_sync_token()
    if not token:
        print("❌ No sync token found! Please set POWERSYNC_JWT_TOKEN")
        logger.error("❌ No sync token found!")
        return 0, count
    
    # PowerSync endpoint
    sync_url = f"{get_sync_url()}/sync"
    
    for item in items:
        try:
            # Prepare data
            data = {
                'model': item.model_name,
                'id': item.object_id,
                'operation': item.operation,
                'data': item.data,
                'tenant_id': item.tenant_id,
                'timestamp': timezone.now().isoformat()
            }
            
            # Send to PowerSync
            response = requests.post(
                sync_url,
                json=data,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            
            if response.status_code in [200, 201, 202, 204]:
                # Mark as synced
                item.synced = True
                item.synced_at = timezone.now()
                item.save()
                success += 1
                print(f"  ✅ Synced: {item.model_name} #{item.object_id}")
                logger.debug(f"✅ Synced: {item.model_name} #{item.object_id}")
            else:
                failed += 1
                item.error = f"HTTP {response.status_code}: {response.text[:200]}"
                item.retry_count += 1
                item.save()
                print(f"  ❌ Failed: {item.model_name} #{item.object_id} - {response.status_code}")
                logger.warning(f"❌ Failed: {item.model_name} #{item.object_id} - {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            failed += 1
            item.error = "Connection error - no internet?"
            item.retry_count += 1
            item.save()
            print(f"  ❌ Connection error: {item.model_name} #{item.object_id}")
            
        except Exception as e:
            failed += 1
            item.error = str(e)
            item.retry_count += 1
            item.save()
            print(f"  ❌ Error: {item.model_name} #{item.object_id} - {e}")
    
    print(f"📊 PUSH complete: {success} success, {failed} failed")
    logger.info(f"📊 PUSH complete: {success} success, {failed} failed")
    return success, failed


def sync_pull(tenant_id=None):
    """
    Pull latest data from the server to local cache
    Returns: (success, records_count)
    """
    print("🔄 Starting PULL sync...")
    logger.info("Starting PULL sync...")
    
    token = get_sync_token()
    if not token:
        print("❌ No sync token found!")
        logger.error("❌ No sync token found!")
        return False, 0
    
    sync_url = f"{get_sync_url()}/sync/pull"
    
    try:
        response = requests.get(
            sync_url,
            params={'tenant_id': tenant_id} if tenant_id else {},
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            records = data.get('records', [])
            count = len(records)
            print(f"📥 Pulled {count} records")
            logger.info(f"📥 Pulled {count} records")
            
            # Process each record
            for record in records:
                try:
                    save_remote_record(record)
                except Exception as e:
                    print(f"  ❌ Failed to save record: {e}")
                    logger.error(f"Failed to save record: {e}")
            
            return True, count
        else:
            print(f"❌ Pull failed: {response.status_code} - {response.text[:200]}")
            logger.error(f"❌ Pull failed: {response.status_code}")
            return False, 0
            
    except Exception as e:
        print(f"❌ Pull error: {e}")
        logger.error(f"❌ Pull error: {e}")
        return False, 0


def sync_all(tenant_id=None):
    """
    Full sync: push then pull
    Returns: (push_success, pull_success)
    """
    print("🔄 Starting FULL sync...")
    logger.info("🔄 Starting FULL sync...")
    
    # Push local changes
    push_success, push_failed = sync_push(tenant_id)
    push_ok = push_failed == 0
    
    # Pull remote changes
    pull_ok, pull_count = sync_pull(tenant_id)
    
    print(f"📊 FULL sync complete: Push={'OK' if push_ok else 'Failed'}, Pull={'OK' if pull_ok else 'Failed'}")
    logger.info(f"📊 FULL sync complete: Push={'OK' if push_ok else 'Failed'}, Pull={'OK' if pull_ok else 'Failed'}")
    
    return push_ok, pull_ok


def save_remote_record(record):
    """
    Save a record pulled from the server to local database
    """
    from django.apps import apps
    
    model_name = record.get('model')
    data = record.get('data')
    object_id = record.get('id')
    operation = record.get('operation', 'update')
    
    if not model_name or not data:
        print(f"  ⚠️ Invalid record: missing model or data")
        return
    
    try:
        # Try to find the model
        model = None
        
        # Try common app names
        app_names = [
            'tronic_master.inventory',
            'tronic_master.sales',
            'tronic_master.cashier',
            'tronic_master.expenses',
            'shared.tenants',
            'shared.users'
        ]
        
        for app_name in app_names:
            try:
                model = apps.get_model(app_name, model_name)
                break
            except LookupError:
                continue
        
        if model is None:
            print(f"  ⚠️ Model {model_name} not found")
            return
        
        # Apply operation
        if operation == 'delete':
            model.objects.filter(id=object_id).delete()
            print(f"  🗑️ Deleted: {model_name} #{object_id}")
            
        elif operation in ['create', 'update']:
            # Remove id from data if it exists
            if 'id' in data:
                del data['id']
            
            obj, created = model.objects.update_or_create(
                id=object_id,
                defaults=data
            )
            print(f"  {'✅ Created' if created else '🔄 Updated'}: {model_name} #{object_id}")
            
    except Exception as e:
        print(f"  ❌ Error saving {model_name} #{object_id}: {e}")
        logger.error(f"Error saving {model_name} #{object_id}: {e}")