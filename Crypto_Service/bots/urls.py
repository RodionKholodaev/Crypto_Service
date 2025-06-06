from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.create_bot, name='create_bot'),
    path('edit/<int:bot_id>/', views.edit_bot, name='edit_bot'),
    path('my-bots/', views.my_bots, name='my_bots'),
    path('bots/<int:bot_id>/delete/', views.delete_bot, name='delete_bot'),
    path('toggle/<int:bot_id>/', views.toggle_bot, name='toggle_bot'),
    path('details/<int:bot_id>/', views.bot_details, name='bot_details'),
    path('statistics/<int:bot_id>/', views.statistics, name='bot_statistics'),
]


