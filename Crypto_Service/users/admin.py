from django.contrib import admin
from .models import User
from .models import PasswordResetCode
from .models import EmailConfirmationCode

admin.site.register(User)
admin.site.register(PasswordResetCode)
admin.site.register(EmailConfirmationCode)