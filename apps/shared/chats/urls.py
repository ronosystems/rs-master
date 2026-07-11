from django.urls import path
from . import views

app_name = 'chats'

urlpatterns = [
    # ============================================
    # CLIENT VIEWS
    # ============================================
    path('client/', views.client_chat, name='client_chat'),
    path('client/guest/', views.client_chat_guest, name='client_chat_guest'),
    
    # ============================================
    # ADMIN VIEWS (Require login)
    # ============================================
    path('admin/', views.admin_chat, name='admin_chat'),
    path('admin/conversation/<int:conversation_id>/', views.admin_chat_conversation, name='admin_conversation'),
    
    # ============================================
    # PUBLIC API ENDPOINTS (No authentication required)
    # ============================================
    path('api/client/send/', views.chat_client_message, name='client_message'),
    path('api/messages/<int:conversation_id>/', views.chat_get_messages, name='get_messages'),
    path('api/check-new/', views.chat_check_new_messages, name='check_new_messages'),
    path('api/status/', views.chat_get_status, name='get_status'),
    
    # ============================================
    # ADMIN API ENDPOINTS (Require login)
    # ============================================
    path('api/conversations/', views.chat_get_conversations, name='get_conversations'),
    path('api/admin/send/', views.chat_send_message, name='send_message'),
    path('api/unread/', views.chat_get_unread_count, name='get_unread_count'), 

    # ============================================
    # DELETE OPERATIONS (Require login)
    # ============================================
    path('api/message/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('api/conversation/<int:conversation_id>/clear/', views.clear_conversation, name='clear_conversation'),
    path('api/conversation/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
    path('api/conversations/clear-all/', views.clear_all_conversations, name='clear_all_conversations'),
]