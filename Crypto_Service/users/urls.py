from django.urls import path,include
from . import views

urlpatterns = [
    path('register/', views.register_view,name='register'),
    path('login/', views.login_view,name='login'),
    path('home/', views.home_view, name='home'),
    path('profile/',views.profile,name='profile'),
    path('bot_conf/',include('bots.urls'), name='bot_creation'),
    
]

