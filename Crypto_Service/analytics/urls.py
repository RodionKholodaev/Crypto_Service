# analytics/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('statistics/', views.statistics_view, name='statistics'),
    path('api/deals-stats/', views.get_deals_stats, name='deals_stats'),
]