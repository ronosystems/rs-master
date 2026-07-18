from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    """Linquor Master Dashboard"""
    tenant = request.user.tenant
    
    context = {
        'tenant': tenant,
        'active_tab': 'dashboard',
        'project_type': 'LINQUOR_MASTER',
    }
    return render(request, 'linquor_master/dashboard.html', context)