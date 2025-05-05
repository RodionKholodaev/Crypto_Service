from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator

class User(AbstractUser):
    username = models.CharField(max_length=150, blank=True, null=True, unique=True)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)  # Добавлено поле name
    balance = models.DecimalField(max_digits=20, decimal_places=6, default=0.0, validators=[MinValueValidator(0.0)])
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email