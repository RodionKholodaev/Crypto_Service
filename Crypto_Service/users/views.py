from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .forms import RegisterForm, ProfileForm
from django.contrib import messages

from bots.models import ExchangeAccount
from .forms import ExchangeAccountForm, EditExchangeAccountForm

from .forms import PasswordResetRequestForm, PasswordResetVerifyForm
from .models import PasswordResetCode
from .utils import generate_reset_code
from django.core.mail import send_mail

from .forms import SetNewPasswordForm
from .models import User
from .forms import EmailConfirmationForm
from .models import EmailConfirmationCode


def register_view(request):
    if request.method == 'POST': # отправляется когда пользователь отправляет форму
        form = RegisterForm(request.POST)
        if form.is_valid(): # метод UserCreationForm
            request.session['reg_data'] = form.cleaned_data
            # cleaned_data словарь {'email': 'user@example.com','name': 'Иван','password1': 'securepassword123','password2': 'securepassword123'}
            # cleaned_data - общий механизм django форм
            # также у каждой формы есть поля form.errors, form.fields, form.initial
            code = generate_reset_code()

            EmailConfirmationCode.objects.create(email=form.cleaned_data['email'], code=code)

            send_mail(
                'Подтверждение регистрации',
                f'Ваш код подтверждения: {code}',
                None,
                [form.cleaned_data['email']],
                fail_silently=False,
            )

            request.session['confirm_email'] = form.cleaned_data['email']
            return redirect('confirm_email')
    else:
        form = RegisterForm()
    return render(request, 'users/register.html', {'form': form})

def confirm_email_view(request):
    email = request.session.get('confirm_email')
    if not email:
        return redirect('register')

    if request.method == 'POST':
        form = EmailConfirmationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            try:
                entry = EmailConfirmationCode.objects.filter(email=email, code=code).latest('created_at')
                if entry.is_valid():
                    # Восстанавливаем данные формы из сессии
                    data = request.session.get('reg_data')
                    if data:
                        reg_form = RegisterForm(data)
                        if reg_form.is_valid():
                            user = reg_form.save()  # ← Сохраняем через форму, как в обычной регистрации
                            login(request, user)

                            # Очистка
                            EmailConfirmationCode.objects.filter(email=email).delete()
                            del request.session['confirm_email']
                            del request.session['reg_data']

                            return redirect('home')
                        else:
                            messages.error(request, 'Ошибка при создании пользователя. Попробуйте снова.')
                    else:
                        messages.error(request, 'Сессия истекла. Пожалуйста, зарегистрируйтесь заново.')
                        return redirect('register')

            except EmailConfirmationCode.DoesNotExist:
                messages.error(request, 'Неверный код.')
    else:
        form = EmailConfirmationForm()

    return render(request, 'users/password_reset_verify.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        email = request.POST['email']  # Явное получение email
        password = request.POST['password']
        
        # Правильная аутентификация через email
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('home')  # Убедитесь, что 'home' существует в urls.py
        else:
            messages.error(request, 'Неверный email или пароль')
    
    return render(request, 'users/login.html', {'messages': messages.get_messages(request)})


# def home_view(request):
#     user=request.user
#     return render(request, 'users/home.html',{'user':user})


def home_view(request):
    user = request.user
    
    if request.method == 'POST':
        if 'delete_key' in request.POST:
            # Удаление ключа (оставляем без изменений)
            key_id = request.POST.get('delete_key')
            if key_id:
                ExchangeAccount.objects.filter(id=key_id, user=user).delete()
                messages.success(request, 'Ключ успешно удален')
            return redirect('home')
        
        if 'edit_key' in request.POST:
            # Редактирование названия ключа
            key_id = request.POST.get('edit_key')
            if key_id:
                try:
                    key = ExchangeAccount.objects.get(id=key_id, user=user)
                    form = EditExchangeAccountForm(request.POST, instance=key)
                    if form.is_valid():
                        form.save()
                        messages.success(request, 'Название ключа успешно изменено')
                        return redirect('home')
                except ExchangeAccount.DoesNotExist:
                    messages.error(request, 'Ключ не найден')
                    return redirect('home')
        
        else:
            # Создание нового ключа (оставляем без изменений)
            form = ExchangeAccountForm(request.POST)
            if form.is_valid():
                new_key = form.save(commit=False)
                new_key.user = user
                new_key.exchange = 'bybit'
                new_key.save()
                messages.success(request, 'Ключ успешно добавлен')
                return redirect('home')
    
    # Для GET-запросов
    form = ExchangeAccountForm()  # Форма для создания ключа
    edit_form = EditExchangeAccountForm()  # Форма для редактирования названия
    
    api_keys = ExchangeAccount.objects.filter(user=user)
    
    return render(request, 'users/home.html', {
        'user': user,
        'form': form,
        'edit_form': edit_form,
        'api_keys': api_keys,
    })

def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('/users/profile/?success=1')
    else:
        form = ProfileForm(instance=request.user)
    
    return render(request, 'users/profile.html', {'form': form, 'user': request.user})

def password_reset_request_view(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            code = generate_reset_code()

            PasswordResetCode.objects.create(email=email, code=code)

            send_mail(
                'Восстановление доступа',
                f'Ваш код восстановления: {code}',
                None,
                [email],
                fail_silently=False,
            )

            # Сохраняем email в сессии
            request.session['reset_email'] = email

            messages.success(request, 'Код отправлен на вашу почту')
            return redirect('verify_reset_code')
    else:
        form = PasswordResetRequestForm()

    return render(request, 'users/password_reset_request.html', {'form': form})


def password_reset_verify_view(request):
    if request.method == 'POST':
        form = PasswordResetVerifyForm(request.POST)
        if form.is_valid():
            email = request.session.get('reset_email')
            code = form.cleaned_data['code']

            try:
                reset_entry = PasswordResetCode.objects.filter(email=email, code=code).latest('created_at')
                if reset_entry.is_valid():
                    messages.success(request, 'Код подтверждён. Можно сбросить пароль.')
                    return redirect('set_new_password')
                else:
                    messages.error(request, 'Код истёк.')
            except PasswordResetCode.DoesNotExist:
                messages.error(request, 'Неверный код.')
    else:
        form = PasswordResetVerifyForm()

    return render(request, 'users/password_reset_verify.html', {'form': form})


def set_new_password_view(request):
    email = request.session.get('reset_email')

    if not email:
        messages.error(request, 'Сессия сброса пароля истекла. Начните сначала.')
        return redirect('password_reset')

    if request.method == 'POST':
        form = SetNewPasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password1']
            try:
                user = User.objects.get(email=email)
                user.set_password(password)
                user.save()

                # Очистить email из сессии после сброса
                del request.session['reset_email']

                messages.success(request, 'Пароль успешно обновлён. Войдите с новым паролем.')
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'Пользователь не найден.')
    else:
        form = SetNewPasswordForm()

    return render(request, 'users/password_reset_set_password.html', {'form': form})
