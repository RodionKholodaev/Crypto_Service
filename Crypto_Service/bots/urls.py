from django.urls import path,include
from . import views

urlpatterns = [
    path('', views.bot_conf, name='bot_creation'),
    path(),
]

