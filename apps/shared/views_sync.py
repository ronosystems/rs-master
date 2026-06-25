# apps/shared/views_sync.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from apps.shared.utils.powersync_sync import sync_all
import json

@login_required
@csrf_exempt
def auto_sync(request):
    """Auto-sync endpoint"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        action = data.get('action', 'auto_sync')
        
        tenant_id = None
        if hasattr(request, 'tenant'):
            tenant_id = request.tenant.id
        
        # Run sync
        result = sync_all(tenant_id)
        
        return JsonResponse({
            'status': 'success' if result else 'partial',
            'message': 'Sync completed' if result else 'Sync completed with errors'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)