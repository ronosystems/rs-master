from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import jwt
from django.conf import settings
import json

class PowerSyncTokenView(APIView):
    """Generate JWT token for PowerSync client"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        token = jwt.encode(
            {
                'user_id': str(request.user.id),
                'tenant_id': str(request.user.tenant_id),
                'username': request.user.username,
                'exp': 3600  # 1 hour
            },
            settings.SECRET_KEY,
            algorithm='HS256'
        )
        return Response({'token': token})

class PowerSyncSyncView(APIView):
    """Handle sync data from PowerSync client"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        data = request.data
        operations = data.get('operations', [])
        
        results = []
        for op in operations:
            # Process each operation
            result = self.process_operation(op)
            results.append(result)
        
        return Response({'status': 'ok', 'results': results})
    
    def process_operation(self, op):
        # You'll implement this based on your models
        return {'status': 'received', 'operation': op}
