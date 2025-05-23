from django.urls import path, include
from . import views

urlpatterns = [
    path('bots/<int:bot_id>/delete/', views.delete_bot, name='delete_bot'),
    path('my_bots/', views.my_bots, name='my_bots'),
    path('create/', views.create_bot, name='create_bot'),
    path('<int:bot_id>/edit/', views.edit_bot, name='edit_bot'),
    path('<int:bot_id>/toggle/', views.toggle_bot, name='toggle_bot'),
    path('<int:bot_id>/', views.bot_details, name='bot_details'),
]
