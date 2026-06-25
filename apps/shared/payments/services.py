# apps/shared/payments/services.py

from decimal import Decimal
from django.db import models
from django.utils import timezone
from .models import Payment, Refund, PaymentMethod


def process_payment(
    tenant, 
    amount, 
    payment_method, 
    user=None, 
    customer=None, 
    sale_id=None,
    invoice_number=None,
    metadata=None
):
    """
    Process a payment
    
    Args:
        tenant: Tenant object
        amount: Decimal amount
        payment_method: cash, card, mobile, bank, mpesa
        user: User who processed the payment
        customer: Customer object (optional)
        sale_id: Sale ID (optional)
        invoice_number: Invoice number (optional)
        metadata: Additional metadata (dict)
    
    Returns:
        Payment object
    """
    
    # Create payment record
    payment = Payment.objects.create(
        tenant=tenant,
        amount=amount,
        payment_method=payment_method,
        status='processing',
        user=user,
        customer=customer,
        sale_id=sale_id,
        invoice_number=invoice_number,
        metadata=metadata or {}
    )
    
    # Process payment
    payment.process_payment()
    
    return payment


def refund_payment(payment, amount, reason, requested_by):
    """
    Process a refund for a payment
    
    Args:
        payment: Payment object
        amount: Decimal amount to refund
        reason: Reason for refund
        requested_by: User requesting the refund
    
    Returns:
        Refund object
    """
    
    if amount > payment.amount:
        raise ValueError("Refund amount cannot exceed payment amount")
    
    if payment.status != 'completed':
        raise ValueError("Only completed payments can be refunded")
    
    refund = Refund.objects.create(
        payment=payment,
        amount=amount,
        reason=reason,
        status='pending'
    )
    
    return refund


def get_payment_summary(tenant, start_date=None, end_date=None):
    """
    Get payment summary for a tenant
    
    Args:
        tenant: Tenant object
        start_date: Optional start date
        end_date: Optional end date
    
    Returns:
        dict: Summary data
    """
    
    payments = Payment.objects.filter(tenant=tenant)
    
    if start_date:
        payments = payments.filter(payment_date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__lte=end_date)
    
    total_payments = payments.count()
    total_amount = payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    # Payment method breakdown
    method_breakdown = {}
    for method in Payment.PAYMENT_METHODS:
        count = payments.filter(payment_method=method[0]).count()
        amount = payments.filter(payment_method=method[0]).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        if count > 0:
            method_breakdown[method[1]] = {
                'count': count,
                'amount': amount
            }
    
    # Status breakdown
    status_breakdown = {}
    for status in Payment.PAYMENT_STATUS:
        count = payments.filter(status=status[0]).count()
        if count > 0:
            status_breakdown[status[1]] = count
    
    return {
        'total_payments': total_payments,
        'total_amount': total_amount,
        'method_breakdown': method_breakdown,
        'status_breakdown': status_breakdown,
    }


def get_default_payment_methods(tenant):
    """Get or create default payment methods for a tenant"""
    
    default_methods = [
        {'name': 'Cash', 'code': 'CASH'},
        {'name': 'Card', 'code': 'CARD'},
        {'name': 'M-Pesa', 'code': 'MPESA'},
        {'name': 'Bank Transfer', 'code': 'BANK'},
        {'name': 'Mobile Money', 'code': 'MOBILE'},
    ]
    
    created = []
    for method_data in default_methods:
        obj, is_created = PaymentMethod.objects.get_or_create(
            tenant=tenant,
            code=method_data['code'],
            defaults={
                'name': method_data['name'],
                'is_active': True,
                'is_available': True
            }
        )
        if is_created:
            created.append(obj)
    
    return created


def get_tenant_payment_stats(tenant):
    """Get payment statistics for a tenant"""
    
    total_payments = Payment.objects.filter(tenant=tenant).count()
    total_amount = Payment.objects.filter(
        tenant=tenant, 
        status='completed'
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    pending_refunds = Refund.objects.filter(
        payment__tenant=tenant,
        status='pending'
    ).count()
    
    return {
        'total_payments': total_payments,
        'total_amount': total_amount,
        'pending_refunds': pending_refunds,
    }