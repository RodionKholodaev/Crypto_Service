from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import User

from bots.models import ExchangeAccount

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

class EmailConfirmationForm(forms.Form):
    code = forms.CharField(label="Код", max_length=6)

# обновление данных в профиле
class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['name', 'avatar', 'theme']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = False



#форма для ввода api ключей
class ExchangeAccountForm(forms.ModelForm):
    class Meta:
        model = ExchangeAccount
        fields = ['name', 'api_key', 'api_secret']
        widgets = {
            'api_key': forms.PasswordInput(render_value=True),
            'api_secret': forms.PasswordInput(render_value=True),
        }
        labels = {
            'name': 'Название ключа',
            'api_key': 'API Key',
            'api_secret': 'API Secret',
        }


#форма для редактирования api ключей
class EditExchangeAccountForm(forms.ModelForm):
    class Meta:
        model = ExchangeAccount
        fields = ['name']  # Только поле названия
        labels = {
            'name': 'Новое название ключа',
        }

class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваш email',
            'id': 'email',
        })
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("Почта не найдена")
        return email

class PasswordResetVerifyForm(forms.Form):
    code = forms.CharField(label="Код", max_length=6)

class SetNewPasswordForm(forms.Form):
    password1 = forms.CharField(
        label="Новый пароль",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите новый пароль',
            'id': 'password1',
        }),
        min_length=8
    )
    password2 = forms.CharField(
        label="Повторите пароль",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Повторите новый пароль',
            'id': 'password2',
        }),
        min_length=8
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Пароли не совпадают")
