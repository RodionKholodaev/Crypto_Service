from django.db import models
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator

class User(AbstractUser):
    username = models.CharField(max_length=150, blank=True, null=True, unique=True)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)  
    balance = models.DecimalField(max_digits=20, decimal_places=6, default=0.0, validators=[MinValueValidator(0.0)])
    
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
        return self.email