from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import User

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    name = forms.CharField(max_length=100, required=True)

    class Meta: # meta позволяет создать связь с моделью и указать дополнительные параметры
        model = User
        fields = ('name', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("Пользователь с таким email уже существует")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.name = self.cleaned_data['name']  # Сохраняем имя
        if commit:
            user.save()
        return user


# обновление данных в профиле
class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['name', 'avatar', 'theme']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = False