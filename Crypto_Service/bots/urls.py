from django.urls import path
from .views import create_bot, edit_bot

urlpatterns = [
    path('create/', create_bot, name='create_bot'),
    path('edit/<int:bot_id>/', edit_bot, name='edit_bot'),
]