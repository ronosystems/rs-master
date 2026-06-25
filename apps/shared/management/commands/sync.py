# apps/shared/management/commands/sync.py
from django.core.management.base import BaseCommand
from apps.shared.sync.engine import sync_push, sync_pull, sync_all


class Command(BaseCommand):
    help = 'Sync data with remote server'

    def add_arguments(self, parser):
        parser.add_argument(
            '--direction',
            choices=['push', 'pull', 'both'],
            default='both',
            help='Sync direction: push (local->remote), pull (remote->local), or both'
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
            success, failed = sync_push(tenant_id)
            if failed == 0:
                self.stdout.write(self.style.SUCCESS(f'✅ Push complete: {success} items synced'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️ Push complete: {success} success, {failed} failed'))

        if direction in ['pull', 'both']:
            self.stdout.write('📥 Pulling remote changes...')
            success, count = sync_pull(tenant_id)
            if success:
                self.stdout.write(self.style.SUCCESS(f'✅ Pull complete: {count} records pulled'))
            else:
                self.stdout.write(self.style.ERROR('❌ Pull failed'))

        self.stdout.write(self.style.SUCCESS('✅ Sync complete!'))