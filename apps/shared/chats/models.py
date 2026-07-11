from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.shared.tenants.models import Tenant


class ChatConversation(models.Model):
    """Chat conversation - each user gets their own private conversation with admin"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='chat_conversations'
    )
    
    # ✅ User who owns this conversation (the client)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='chat_conversations'
    )
    
    # ✅ Client info (for non-logged-in users)
    client_name = models.CharField(max_length=200, blank=True, null=True)
    client_email = models.EmailField(blank=True, null=True)
    client_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # ✅ Session ID for guest users
    client_session_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        db_index=True
    )
    
    # ✅ Admin/Owner (the logged-in user who is the platform owner)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_chats'
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_client_online = models.BooleanField(default=False)
    is_admin_online = models.BooleanField(default=False)
    last_activity = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['status', 'is_client_online']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['client_session_id']),
            models.Index(fields=['assigned_to']),
        ]
        # ✅ Ensure one conversation per user
        unique_together = ['user', 'assigned_to']  # One conversation per user-admin pair
    
    def __str__(self):
        return f"Chat #{self.id} - {self.get_client_display()} with {self.assigned_to or 'Unassigned'}"
    
    def get_client_display(self):
        """Get display name for the client"""
        if self.user:
            return self.user.get_full_name() or self.user.username
        return self.client_name or f"Guest #{self.id}"
    
    def get_client_email(self):
        """Get client email"""
        if self.user:
            return self.user.email
        return self.client_email
    
    @property
    def unread_count(self):
        return self.messages.filter(is_read=False, is_from_admin=False).count()
    
    @property
    def last_message(self):
        return self.messages.order_by('-created_at').first()
    
    @property
    def display_name(self):
        return self.get_client_display()


class ChatMessage(models.Model):
    """Individual chat messages"""
    
    conversation = models.ForeignKey(
        ChatConversation, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    
    # ✅ Sender info
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_messages'
    )
    sender_name = models.CharField(max_length=200, blank=True, null=True)
    is_from_admin = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    message = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'is_read']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_from_admin']),
        ]
    
    def __str__(self):
        return f"Message #{self.id} from {self.sender_name or 'Anonymous'}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()