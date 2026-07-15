# apps/shared/powersync/sync_manager.py

import logging
from django.db import transaction
from django.utils import timezone
from apps.shared.tenants.models import SyncQueue
from apps.tronic_master.models import Product, ProductUnit, BranchTransfer, StockEntry

logger = logging.getLogger(__name__)

class SyncManager:
    """Central manager for all offline sync operations"""
    
    MODEL_MAP = {
        'Product': Product,
        'ProductUnit': ProductUnit,
        'BranchTransfer': BranchTransfer,
        'StockEntry': StockEntry,
        # Add other models as needed
    }
    
    @classmethod
    def process_pending_operations(cls, tenant_id=None, limit=50):
        """Process pending sync operations"""
        queryset = SyncQueue.objects.filter(status='PENDING')
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        # Process highest priority first
        operations = queryset.order_by('-priority', 'created_at')[:limit]
        
        results = {
            'synced': 0,
            'failed': 0,
            'conflicts': 0,
            'skipped': 0
        }
        
        for operation in operations:
            try:
                success = cls._process_operation(operation)
                if success:
                    results['synced'] += 1
                else:
                    results['failed'] += 1
            except Exception as e:
                logger.error(f"Error processing operation {operation.id}: {e}")
                operation.mark_failed(str(e))
                results['failed'] += 1
        
        return results
    
    @classmethod
    def _process_operation(cls, operation):
        """Process a single sync operation"""
        model = cls.MODEL_MAP.get(operation.model_name)
        if not model:
            logger.error(f"Unknown model: {operation.model_name}")
            operation.mark_failed(f"Unknown model: {operation.model_name}")
            return False
        
        # For deletes
        if operation.operation == 'DELETE':
            return cls._process_delete(model, operation)
        
        # For creates/updates
        data = operation.data
        
        with transaction.atomic():
            try:
                # Try to find existing object
                obj = model.objects.filter(id=data.get('id')).first()
                
                if obj and operation.operation == 'CREATE':
                    # This is a conflict - object already exists
                    operation.mark_conflict(obj)
                    logger.warning(f"Conflict: {operation.model_name} {data.get('id')} already exists")
                    return False
                
                if not obj and operation.operation == 'UPDATE':
                    # This is a conflict - object doesn't exist
                    # Create it anyway (remote data wins)
                    obj = model()
                
                # Prepare data (remove non-model fields)
                clean_data = cls._clean_data_for_model(model, data)
                
                # For updates, check for conflicts
                if obj and operation.operation == 'UPDATE':
                    # Check if there's a conflict
                    if obj.updated_at > operation.created_at:
                        # Object was modified locally after this sync was queued
                        # This is a conflict
                        operation.mark_conflict(obj)
                        logger.warning(f"Conflict: {operation.model_name} {data.get('id')} was modified locally")
                        return False
                
                # Update object fields
                for field, value in clean_data.items():
                    setattr(obj, field, value)
                
                # Set audit fields
                if hasattr(obj, 'updated_at'):
                    obj.updated_at = timezone.now()
                
                obj.save()
                
                # Mark operation as synced
                operation.mark_synced()
                
                logger.info(f"✅ Synced {operation.operation} {operation.model_name} #{operation.object_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error saving {operation.model_name}: {e}")
                operation.mark_failed(str(e))
                return False
    
    @classmethod
    def _clean_data_for_model(cls, model, data):
        """Remove fields that don't exist on the model"""
        model_fields = {f.name for f in model._meta.fields}
        clean_data = {}
        
        for field, value in data.items():
            if field in model_fields:
                clean_data[field] = value
        
        # Remove 'id' if it's a create operation
        if not data.get('id'):
            clean_data.pop('id', None)
        
        return clean_data
    
    @classmethod
    def _process_delete(cls, model, operation):
        """Process a delete operation"""
        try:
            obj = model.objects.get(id=operation.object_id)
            obj.delete()
            operation.mark_synced()
            logger.info(f"✅ Deleted {operation.model_name} #{operation.object_id}")
            return True
        except model.DoesNotExist:
            operation.mark_synced()  # Already deleted
            return True
        except Exception as e:
            logger.error(f"Error deleting {operation.model_name}: {e}")
            operation.mark_failed(str(e))
            return False
    
    @classmethod
    def resolve_conflict(cls, operation_id, resolution_data, resolved_by):
        """Manually resolve a conflict"""
        operation = SyncQueue.objects.get(id=operation_id, status='CONFLICT')
        
        with transaction.atomic():
            model = cls.MODEL_MAP.get(operation.model_name)
            if not model:
                return False
            
            try:
                obj = model.objects.get(id=operation.object_id)
                
                # Apply resolution data
                for field, value in resolution_data.items():
                    setattr(obj, field, value)
                
                obj.save()
                
                # Mark as resolved
                operation.resolved_data = resolution_data
                operation.conflict_resolved = True
                operation.resolved_by = resolved_by
                operation.resolved_at = timezone.now()
                operation.status = 'SYNCED'
                operation.save()
                
                logger.info(f"✅ Resolved conflict for {operation.model_name} #{operation.object_id}")
                return True
                
            except Exception as e:
                logger.error(f"Error resolving conflict: {e}")
                return False