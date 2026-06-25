# apps/shared/management/commands/sync_powersync.py
from django.core.management.base import BaseCommand
from apps.shared.tenants.models import SyncQueue
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync offline data with PowerSync'

    def add_arguments(self, parser):
        parser.add_argument(
            '--direction',
            choices=['push', 'pull', 'both'],
            default='both',
            help='Sync direction: push, pull, or both'
        )
        parser.add_argument(
            '--tenant',
            type=int,
            help='Tenant ID to sync (optional)'
        )

    def handle(self, *args, **options):
        direction = options['direction']
        tenant_id = options.get('tenant')

        self.stdout.write('🔄 Starting PowerSync sync...')

        if direction in ['push', 'both']:
            self.stdout.write('📤 Pushing local changes...')
            self.sync_push(tenant_id)

        if direction in ['pull', 'both']:
            self.stdout.write('📥 Pulling remote changes...')
            self.sync_pull(tenant_id)

        self.stdout.write(self.style.SUCCESS('✅ Sync complete!'))

    def sync_push(self, tenant_id=None):
        """Push queued items to PowerSync"""
        items = SyncQueue.objects.filter(synced=False)
        if tenant_id:
            items = items.filter(tenant_id=tenant_id)

        count = items.count()
        if count == 0:
            self.stdout.write('✅ No items to push')
            return

        self.stdout.write(f'📤 Pushing {count} items...')

        processed = 0
        for item in items:
            try:
                # Process the item
                item.process()
                item.synced = True
                item.synced_at = timezone.now()
                item.save()
                processed += 1
                self.stdout.write(f'  ✅ Synced: {item.model_name} #{item.object_id}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Failed: {item.model_name} #{item.object_id} - {e}'))
                item.error = str(e)
                item.retry_count += 1
                item.save()

        self.stdout.write(f'✅ Processed {processed}/{count} items')

    def sync_pull(self, tenant_id=None):
        """Pull changes from PowerSync (placeholder)"""
        self.stdout.write('📥 Pull functionality coming soon...')


# Import timezone for the sync_push method
from django.utils import timezone