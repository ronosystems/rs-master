from django.urls import path
from . import views

urlpatterns = [
    path('', views.expense_list, name='expense_list'),
    path('add/', views.add_expense, name='add_expense'),
    path('<int:expense_id>/', views.expense_detail, name='expense_detail'),
    path('<int:expense_id>/approve/', views.approve_expense, name='approve_expense'),
    path('<int:expense_id>/reject/', views.reject_expense, name='reject_expense'),
    path('<int:expense_id>/mark-paid/', views.mark_expense_paid, name='mark_expense_paid'),
    path('report/', views.expense_report, name='expense_report'),
]
