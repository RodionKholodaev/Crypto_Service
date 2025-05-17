from django.urls import path,include
from . import views

urlpatterns = [
    path('register/', views.register_view,name='register'),
    path('login/', views.login_view,name='login'),
    path('home/', views.home_view, name='home'),
    path('profile/',views.profile,name='profile'),
    path('bot_conf/',include('bots.urls'), name='bot_creation'),
    path('password-reset/', views.password_reset_request_view, name='password_reset'),
    path('verify-reset-code/', views.password_reset_verify_view, name='verify_reset_code'),
    path('set-new-password/', views.set_new_password_view, name='set_new_password'),
    path('confirm-email/', views.confirm_email_view, name='confirm_email'),
]

