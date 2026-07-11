from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    # Expense List & Reports
    path('', views.expense_list, name='expense_list'),
    path('report/', views.expense_report, name='expense_report'),
    
    # Expense CRUD
    path('add/', views.add_expense, name='add_expense'),
    path('<int:expense_id>/', views.expense_detail, name='expense_detail'),
    
    # Expense Actions
    path('<int:expense_id>/approve/', views.approve_expense, name='approve_expense'),
    path('<int:expense_id>/reject/', views.reject_expense, name='reject_expense'),
    path('<int:expense_id>/pay/', views.mark_expense_paid, name='mark_expense_paid'),
    
    # Expense Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.add_category, name='add_category'),
    path('categories/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('categories/<int:category_id>/delete/', views.delete_category, name='delete_category'),
]