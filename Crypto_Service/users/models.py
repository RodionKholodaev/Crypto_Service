from django.db import models
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import timedelta

class User(AbstractUser):
    username = models.CharField(max_length=150, blank=True, null=True, unique=True)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)  
    balance = models.DecimalField(max_digits=20, decimal_places=6, default=100.0, validators=[MinValueValidator(0.0)])

    trc20_address = models.CharField(max_length=50, null=True, blank=True)
    erc20_address = models.CharField(max_length=50, null=True, blank=True)
    
    avatar = models.ImageField(
        upload_to='avatars/',
        validators=[
        FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])
        ],
        blank=True,
        null=True
    )
    theme = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email # если вывести {{user}}, то выйдет не <User: User object (1)>, а нормальный email

class PasswordResetCode(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return timezone.now() < self.created_at + timedelta(minutes=10)

    def __str__(self):
        return f"{self.email} - {self.code}"

class EmailConfirmationCode(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return timezone.now() < self.created_at + timedelta(minutes=10)

    def __str__(self):
        return f"{self.email} - {self.code}"
    

