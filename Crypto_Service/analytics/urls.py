from django.urls import path
from . import views
from .views import ExportDealsView 

urlpatterns = [
    path('', views.dashboard_view, name='analytics'),
    path('export_deals/', ExportDealsView.as_view(), name='export_deals'),
]