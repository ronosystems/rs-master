
from django.urls import path
from . import views

app_name = 'tenants'

urlpatterns = [
    # ============================================
    # TENANT MANAGEMENT
    # ============================================
    path('', views.tenant_list, name='tenant_list'),
    path('super-admin-dashboard/', views.super_admin_dashboard, name='super_admin_dashboard'),
    path('register/', views.register_tenant, name='register_tenant'),
    path('<int:tenant_id>/', views.tenant_detail, name='tenant_detail'),
    path('<int:tenant_id>/edit/', views.edit_tenant, name='edit_tenant'),
    path('<int:tenant_id>/delete/', views.delete_tenant, name='delete_tenant'),
    path('<int:tenant_id>/approve/', views.approve_tenant, name='approve_tenant'),
    path('<int:tenant_id>/reject/', views.reject_tenant, name='reject_tenant'),
    path('<int:tenant_id>/assign-owner/', views.assign_owner, name='assign_owner'),
    path('<int:tenant_id>/edit-owner/', views.edit_tenant_owner, name='edit_tenant_owner'),

    # ============================================
    # 🔥 Tenant switching (preview)
    # ============================================
    path('switch-tenant/<int:tenant_id>/', views.switch_tenant, name='switch_tenant'),
    path('exit-preview/', views.exit_preview, name='exit_preview'),
    
    # ============================================
    # PROJECT TYPE
    # ============================================
    path('project-types/', views.project_type_list, name='project_type_list'),
    path('project-types/create/', views.project_type_create, name='project_type_create'),
    path('project-types/<int:pk>/edit/', views.project_type_edit, name='project_type_edit'),
    path('project-types/<int:pk>/delete/', views.project_type_delete, name='project_type_delete'),
    path('project-type/<int:pk>/toggle/', views.project_type_toggle, name='project_type_toggle'),
    
    # ============================================
    # SUBSCRIPTION PLANS
    # ============================================
    path('upgrade-subscription/', views.upgrade_subscription, name='upgrade_subscription'),
    path('subscription-plans/', views.subscription_plans, name='subscription_plans'),
    path('subscription-plans/', views.subscription_plans_list, name='subscription_plans_list'),
    path('subscription-plans/create/', views.subscription_plan_create, name='subscription_plan_create'),
    path('subscription-plans/<int:pk>/edit/', views.subscription_plan_edit, name='subscription_plan_edit'),
    path('subscription-plans/<int:pk>/delete/', views.subscription_plan_delete, name='subscription_plan_delete'),
    
    # ============================================
    # SUBSCRIPTIONS
    # ============================================
    path('subscription-users/', views.subscription_users, name='subscription_users'),
    path('subscription/<int:tenant_id>/', views.tenant_subscription, name='tenant_subscription'),
    path('subscription/<int:tenant_id>/renew/', views.renew_subscription, name='renew_subscription'),
    path('my-subscription/<int:tenant_id>/', views.my_subscription, name='my_subscription'),
]