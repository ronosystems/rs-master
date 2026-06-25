# apps/shared/notifications/services.py

from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Notification, NotificationPreference


def send_notification(recipient, title, message, notification_type='info', link=None, created_by=None, tenant=None):
    """
    Send notification to a user
    
    Args:
        recipient: User object
        title: Notification title
        message: Notification message
        notification_type: info, success, warning, error, system, sale, stock, booking, payment
        link: Optional URL to link to
        created_by: User who created the notification
        tenant: Tenant for tenant-scoped notifications
    """
    
    # Create notification in database
    notification = Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        type=notification_type,
        link=link,
        created_by=created_by,
        tenant=tenant
    )
    
    # Check preferences and send email if enabled
    try:
        prefs = NotificationPreference.objects.get(user=recipient)
        if prefs.email_notifications:
            send_email_notification(recipient, title, message, notification_type, link)
    except NotificationPreference.DoesNotExist:
        # Default to sending email if no preferences exist
        send_email_notification(recipient, title, message, notification_type, link)
    
    return notification


def send_email_notification(user, title, message, notification_type, link=None):
    """Send email notification to user"""
    subject = f"[{notification_type.upper()}] {title}"
    
    html_message = f"""
    <html>
        <body>
            <h3>{title}</h3>
            <p>{message}</p>
            {f'<a href="{link}">View Details</a>' if link else ''}
            <br><br>
            <small>Sent from RS Master Platform</small>
        </body>
    </html>
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True
        )
    except Exception:
        pass


def get_unread_notifications(user, limit=10):
    """Get unread notifications for a user"""
    return Notification.objects.filter(
        recipient=user,
        is_read=False
    ).order_by('-created_at')[:limit]


def get_all_notifications(user, limit=50):
    """Get all notifications for a user"""
    return Notification.objects.filter(
        recipient=user
    ).order_by('-created_at')[:limit]


def mark_all_as_read(user):
    """Mark all notifications as read for a user"""
    count = Notification.objects.filter(
        recipient=user,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())
    return count


def create_notification_preferences(user):
    """Create default notification preferences for a user"""
    from .models import NotificationPreference
    return NotificationPreference.get_or_create_for_user(user)