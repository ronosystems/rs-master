from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
import uuid

from .models import ChatConversation, ChatMessage


# ============================================
# CLIENT VIEWS - Each user sees their own chat
# ============================================

@login_required
def client_chat(request):
    """Client chat page - logged in users see their own conversation with admin"""
    user = request.user
    tenant = user.tenant
    
    # Get or create conversation for this user with the admin
    # Find admin (superuser or platform owner)
    admin_user = None
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # Get the first superuser or admin
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.filter(role='super_admin').first()
    except:
        pass
    
    # Get or create conversation
    conversation = None
    if admin_user:
        conversation = ChatConversation.objects.filter(
            user=user,
            assigned_to=admin_user,
            status__in=['active', 'pending']
        ).first()
        
        if not conversation:
            conversation = ChatConversation.objects.create(
                user=user,
                tenant=tenant,
                client_name=user.get_full_name() or user.username,
                client_email=user.email,
                assigned_to=admin_user,
                is_client_online=True,
                status='active'
            )
    
    context = {
        'conversation_id': conversation.id if conversation else None,
        'user': user,
        'tenant': tenant,
        'is_logged_in': True,
        'client_name': user.get_full_name() or user.username,
        'client_email': user.email,
    }
    return render(request, 'shared/client_chat.html', context)


@login_required
def client_chat_guest(request):
    """Guest chat page - for non-logged in users"""
    # Get or create session ID
    if 'guest_session_id' not in request.session:
        request.session['guest_session_id'] = str(uuid.uuid4())
    
    session_id = request.session['guest_session_id']
    
    # Find admin
    admin_user = None
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.filter(role='super_admin').first()
    except:
        pass
    
    # Get or create conversation for guest
    conversation = None
    if admin_user:
        conversation = ChatConversation.objects.filter(
            client_session_id=session_id,
            assigned_to=admin_user,
            status__in=['active', 'pending']
        ).first()
        
        if not conversation:
            conversation = ChatConversation.objects.create(
                client_name='Guest',
                client_session_id=session_id,
                assigned_to=admin_user,
                is_client_online=True,
                status='active'
            )
    
    context = {
        'conversation_id': conversation.id if conversation else None,
        'is_logged_in': False,
        'session_id': session_id,
    }
    return render(request, 'shared/client_chat.html', context)


# ============================================
# ADMIN VIEWS - See all chats separately
# ============================================

@login_required
def admin_chat(request):
    """Admin chat dashboard - combined view with conversation list and chat"""
    if not request.user.is_superuser and request.user.role != 'super_admin':
        messages.error(request, 'Access denied. Only Super Admins can access live chat.')
        return redirect('portal:dashboard')
    
    # Get all active conversations
    conversations = ChatConversation.objects.filter(
        status='active'
    ).select_related('user', 'assigned_to').order_by('-last_activity')
    
    # Stats
    total_conversations = conversations.count()
    online_count = conversations.filter(is_client_online=True).count()
    unread_count = ChatMessage.objects.filter(
        is_read=False,
        is_from_admin=False,
        conversation__status='active'
    ).count()
    
    # Get selected conversation
    conversation_id = request.GET.get('conversation')
    conversation = None
    messages_list = []
    
    if conversation_id:
        try:
            conversation = ChatConversation.objects.get(id=conversation_id)
            # Mark messages as read
            conversation.messages.filter(is_read=False, is_from_admin=False).update(
                is_read=True,
                read_at=timezone.now()
            )
            # Update admin online status
            conversation.is_admin_online = True
            conversation.save()
            messages_list = conversation.messages.all().order_by('created_at')
        except ChatConversation.DoesNotExist:
            pass
    
    context = {
        'conversations': conversations,
        'total_conversations': total_conversations,
        'online_count': online_count,
        'unread_count': unread_count,
        'conversation': conversation,
        'messages': messages_list,
        'is_super_admin': True,
    }
    return render(request, 'shared/admin_chat.html', context)


@login_required
def admin_chat_conversation(request, conversation_id):
    """View a specific conversation"""
    if not request.user.is_superuser and request.user.role != 'super_admin':
        messages.error(request, 'Access denied.')
        return redirect('portal:dashboard')
    
    conversation = get_object_or_404(ChatConversation, id=conversation_id)
    
    # Mark messages as read
    conversation.messages.filter(is_read=False, is_from_admin=False).update(
        is_read=True,
        read_at=timezone.now()
    )
    
    # Update admin online status
    conversation.is_admin_online = True
    conversation.save()
    
    context = {
        'conversation': conversation,
        'messages': conversation.messages.all().order_by('created_at'),
    }
    return render(request, 'shared/admin_conversation.html', context)


# ============================================
# PUBLIC API ENDPOINTS (No authentication)
# ============================================

@csrf_exempt
def chat_client_message(request):
    """API: Client sends a message"""
    try:
        data = json.loads(request.body)
        client_name = data.get('name', 'Visitor')
        client_email = data.get('email', '')
        client_phone = data.get('phone', '')
        message = data.get('message', '').strip()
        session_id = data.get('session_id', '')
        user_id = data.get('user_id', None)
        
        print(f"📩 CLIENT MESSAGE:")
        print(f"  - Name: {client_name}")
        print(f"  - User ID: {user_id}")
        print(f"  - Session ID: {session_id}")
        print(f"  - Message: {message[:50]}...")
        
        if not message:
            return JsonResponse({'success': False, 'error': 'Message is required'})
        
        # Find admin user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.filter(role='super_admin').first()
        
        if not admin_user:
            return JsonResponse({'success': False, 'error': 'No admin found'}, status=404)
        
        # Get or create conversation
        conv = None
        
        # If user is logged in, use user ID
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                conv, created = ChatConversation.objects.get_or_create(
                    user=user,
                    assigned_to=admin_user,
                    defaults={
                        'client_name': user.get_full_name() or user.username,
                        'client_email': user.email,
                        'is_client_online': True,
                        'status': 'active',
                    }
                )
            except User.DoesNotExist:
                pass
        
        # If no conversation found, use session ID
        if not conv and session_id:
            conv, created = ChatConversation.objects.get_or_create(
                client_session_id=session_id,
                assigned_to=admin_user,
                defaults={
                    'client_name': client_name,
                    'client_email': client_email,
                    'client_phone': client_phone,
                    'is_client_online': True,
                    'status': 'active',
                }
            )
        
        if not conv:
            return JsonResponse({'success': False, 'error': 'Could not create conversation'}, status=500)
        
        # Update client info
        if client_name:
            conv.client_name = client_name
        if client_email:
            conv.client_email = client_email
        if client_phone:
            conv.client_phone = client_phone
        conv.is_client_online = True
        conv.save()
        
        # Create message
        msg = ChatMessage.objects.create(
            conversation=conv,
            sender_name=client_name,
            message=message,
            is_from_admin=False,
            is_read=False,
        )
        
        conv.last_activity = timezone.now()
        conv.save()
        
        return JsonResponse({
            'success': True,
            'conversation_id': conv.id,
            'message_id': msg.id,
            'message': 'Your message has been sent. Support will respond shortly!'
        })
        
    except Exception as e:
        print(f"❌ Error in chat_client_message: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def chat_get_messages(request, conversation_id=None):
    """API: Get messages for a conversation"""
    try:
        if not conversation_id:
            conversation_id = request.GET.get('conversation_id')
        
        session_id = request.GET.get('session_id')
        user_id = request.GET.get('user_id')
        
        conv = None
        
        # Try to find conversation by ID first
        if conversation_id:
            conv = get_object_or_404(ChatConversation, id=conversation_id)
        elif user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
                conv = ChatConversation.objects.filter(
                    user=user,
                    status__in=['active', 'pending']
                ).first()
            except User.DoesNotExist:
                pass
        elif session_id:
            conv = ChatConversation.objects.filter(
                client_session_id=session_id,
                status__in=['active', 'pending']
            ).first()
        
        if not conv:
            return JsonResponse({
                'success': True,
                'messages': [],
                'conversation_id': None,
                'is_admin_online': False
            })
        
        # Get all messages
        messages = conv.messages.all().order_by('created_at')
        
        # If admin is viewing, mark messages as read
        if request.user.is_authenticated and request.user.is_superuser:
            unread_count = messages.filter(is_from_admin=False, is_read=False).count()
            if unread_count > 0:
                messages.filter(is_from_admin=False, is_read=False).update(
                    is_read=True,
                    read_at=timezone.now()
                )
        
        # Build response
        data = []
        for msg in messages:
            data.append({
                'id': msg.id,
                'sender': 'admin' if msg.is_from_admin else 'client',
                'sender_name': msg.sender_name or ('Support' if msg.is_from_admin else conv.get_client_display()),
                'text': msg.message,
                'time': msg.created_at.strftime('%H:%M'),
                'is_read': msg.is_read,
                'is_from_admin': msg.is_from_admin,
                'created_at': msg.created_at.isoformat(),
            })
        
        return JsonResponse({
            'success': True, 
            'messages': data,
            'conversation_id': conv.id,
            'is_admin_online': conv.is_admin_online,
            'status': conv.status,
            'client_name': conv.get_client_display(),
            'client_email': conv.get_client_email(),
        })
        
    except Exception as e:
        print(f"❌ Error in chat_get_messages: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def chat_check_new_messages(request):
    """API: Check for new messages since last check"""
    try:
        session_id = request.GET.get('session_id')
        user_id = request.GET.get('user_id')
        last_id = request.GET.get('last_id', 0)
        
        conv = None
        
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
                conv = ChatConversation.objects.filter(
                    user=user,
                    status__in=['active', 'pending']
                ).first()
            except User.DoesNotExist:
                pass
        
        if not conv and session_id:
            conv = ChatConversation.objects.filter(
                client_session_id=session_id,
                status__in=['active', 'pending']
            ).first()
        
        if not conv:
            return JsonResponse({
                'success': True, 
                'messages': [], 
                'is_admin_online': False,
                'has_conversation': False
            })
        
        # Get new messages
        try:
            last_id = int(last_id)
            new_messages = conv.messages.filter(id__gt=last_id)
        except ValueError:
            new_messages = conv.messages.all()
        
        # Format messages
        messages_data = []
        for msg in new_messages:
            messages_data.append({
                'id': msg.id,
                'message': msg.message,
                'is_from_admin': msg.is_from_admin,
                'sender_name': msg.sender_name or ('Support' if msg.is_from_admin else conv.get_client_display()),
                'created_at': msg.created_at.isoformat(),
                'is_read': msg.is_read,
            })
        
        # Mark admin messages as read
        if new_messages.filter(is_from_admin=True, is_read=False).exists():
            new_messages.filter(is_from_admin=True, is_read=False).update(is_read=True)
        
        return JsonResponse({
            'success': True,
            'messages': messages_data,
            'is_admin_online': conv.is_admin_online,
            'has_conversation': True,
            'conversation_id': conv.id,
        })
        
    except Exception as e:
        print(f"❌ Error checking new messages: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def chat_get_status(request):
    """API: Get admin online status and conversation info"""
    try:
        session_id = request.GET.get('session_id')
        user_id = request.GET.get('user_id')
        conversation_id = request.GET.get('conversation_id')
        
        conv = None
        
        if conversation_id:
            conv = ChatConversation.objects.filter(id=conversation_id).first()
        elif user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
                conv = ChatConversation.objects.filter(
                    user=user,
                    status__in=['active', 'pending']
                ).first()
            except User.DoesNotExist:
                pass
        elif session_id:
            conv = ChatConversation.objects.filter(
                client_session_id=session_id,
                status__in=['active', 'pending']
            ).first()
        
        if not conv:
            return JsonResponse({
                'success': True,
                'is_admin_online': False,
                'is_client_online': False,
                'has_conversation': False
            })
        
        return JsonResponse({
            'success': True,
            'is_admin_online': conv.is_admin_online,
            'is_client_online': conv.is_client_online,
            'has_conversation': True,
            'conversation_id': conv.id,
            'status': conv.status,
            'created_at': conv.created_at.isoformat(),
            'client_name': conv.get_client_display(),
            'client_email': conv.get_client_email(),
        })
        
    except Exception as e:
        print(f"❌ Error getting status: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============================================
# ADMIN API ENDPOINTS
# ============================================

@csrf_exempt
def chat_get_conversations(request):
    """API: Get all conversations for admin"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    conversations = ChatConversation.objects.filter(
        status='active'
    ).select_related('user', 'assigned_to').order_by('-last_activity')
    
    data = []
    for conv in conversations:
        last_msg = conv.last_message
        data.append({
            'id': conv.id,
            'user_id': conv.user_id,
            'client_name': conv.get_client_display(),
            'client_email': conv.get_client_email(),
            'client_phone': conv.client_phone,
            'is_client_online': conv.is_client_online,
            'is_admin_online': conv.is_admin_online,
            'unread': conv.unread_count,
            'last_message': last_msg.message[:100] if last_msg else 'No messages',
            'time': last_msg.created_at.strftime('%H:%M') if last_msg else 'Just now',
            'created_at': conv.created_at.isoformat(),
            'message_count': conv.messages.count(),
        })
    
    return JsonResponse({'success': True, 'conversations': data})


@csrf_exempt
def chat_send_message(request):
    """API: Send a message from admin to client"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        conversation_id = data.get('conversation_id')
        message = data.get('message', '').strip()
        
        if not conversation_id or not message:
            return JsonResponse({'success': False, 'error': 'Invalid data'})
        
        conv = get_object_or_404(ChatConversation, id=conversation_id)
        
        # Create message from admin
        msg = ChatMessage.objects.create(
            conversation=conv,
            sender=request.user,
            sender_name=request.user.get_full_name() or request.user.username,
            message=message,
            is_from_admin=True,
            is_read=False,
        )
        
        # Update conversation
        conv.last_activity = timezone.now()
        conv.is_admin_online = True
        conv.save()
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': msg.id,
                'sender': 'admin',
                'sender_name': msg.sender_name,
                'text': msg.message,
                'time': msg.created_at.strftime('%H:%M'),
                'is_read': msg.is_read,
                'is_from_admin': msg.is_from_admin,
                'created_at': msg.created_at.isoformat(),
            }
        })
        
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)




@csrf_exempt
def chat_get_unread_count(request):
    """API: Get unread message count for admin"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Count unread messages from clients (not from admin)
    unread_count = ChatMessage.objects.filter(
        is_read=False,
        is_from_admin=False,
        conversation__status='active'
    ).count()
    
    return JsonResponse({'success': True, 'unread_count': unread_count})



    
# ============================================
# DELETE OPERATIONS
# ============================================

@csrf_exempt
def delete_message(request, message_id):
    """Delete a single message"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        msg = ChatMessage.objects.get(id=message_id)
        msg.delete()
        return JsonResponse({'success': True})
    except ChatMessage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Message not found'}, status=404)


@csrf_exempt
def clear_conversation(request, conversation_id):
    """Clear all messages in a conversation"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        conv = ChatConversation.objects.get(id=conversation_id)
        conv.messages.all().delete()
        return JsonResponse({'success': True})
    except ChatConversation.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Conversation not found'}, status=404)


@csrf_exempt
def delete_conversation(request, conversation_id):
    """Delete an entire conversation"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        conv = ChatConversation.objects.get(id=conversation_id)
        conv.delete()
        return JsonResponse({'success': True})
    except ChatConversation.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Conversation not found'}, status=404)


@csrf_exempt
def clear_all_conversations(request):
    """Clear all conversations"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        ChatConversation.objects.all().delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)