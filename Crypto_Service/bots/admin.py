from django.contrib import admin
from .models import ExchangeAccount, Bot, Indicator, Deal

admin.site.register(ExchangeAccount)
admin.site.register(Bot)
admin.site.register(Indicator)
admin.site.register(Deal)