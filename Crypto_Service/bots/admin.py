from django.contrib import admin
from .models import ExchangeAccount
from .models import Bot
from .models import Indicator
from .models import Deal

admin.site.register(ExchangeAccount)
admin.site.register(Bot)
admin.site.register(Indicator)
admin.site.register(Deal)
