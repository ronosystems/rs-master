# apps/tronic_master/utils.py

from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

def generate_invoice_number(tenant, prefix="SALE"):
    """
    Generate a unique sequential invoice number for a specific tenant.
    Each tenant has their own counter starting from 1.
    
    Format: {prefix}-{YYYYMMDD}-{sequential_number:06d}
    Example: SALE-20260101-000001, SALE-20260101-000002
    
    Args:
        tenant: The tenant object
        prefix: Invoice prefix (e.g., 'SALE', 'POS', 'INV')
    
    Returns:
        str: Unique invoice number
    """
    from apps.tronic_master.models import InvoiceCounter, Sale
    
    with transaction.atomic():
        # Get or create counter for this specific tenant
        counter, created = InvoiceCounter.objects.select_for_update().get_or_create(
            tenant=tenant
        )
        
        # Increment counter
        counter.last_number += 1
        counter.save()
        
        # Generate invoice number with tenant-specific format
        date_str = timezone.now().strftime('%Y%m%d')
        invoice_no = f"{prefix}-{date_str}-{counter.last_number:06d}"
        
        # Safety check - ensure uniqueness (very unlikely but just in case)
        if Sale.objects.filter(tenant=tenant, invoice_no=invoice_no).exists():
            logger.warning(f"Invoice number collision detected: {invoice_no}. Incrementing counter.")
            counter.last_number += 1
            counter.save()
            invoice_no = f"{prefix}-{date_str}-{counter.last_number:06d}"
        
        logger.debug(f"Generated invoice number: {invoice_no} for tenant {tenant.id} ({tenant.company_name})")
        return invoice_no

def get_tenant_invoice_counter(tenant):
    """Get the current invoice counter value for a tenant"""
    from apps.tronic_master.models import InvoiceCounter
    
    counter, created = InvoiceCounter.objects.get_or_create(tenant=tenant)
    return counter.last_number

def reset_tenant_invoice_counter(tenant, start_from=0):
    """Reset the invoice counter for a tenant (admin use only)"""
    from apps.tronic_master.models import InvoiceCounter
    
    counter, created = InvoiceCounter.objects.get_or_create(tenant=tenant)
    counter.last_number = start_from
    counter.save()
    return counter