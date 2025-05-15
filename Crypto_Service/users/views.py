from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .forms import RegisterForm
from .forms import ProfileForm
from django.contrib import messages

from bots.models import ExchangeAccount
from .forms import ExchangeAccountForm, EditExchangeAccountForm

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')  # куда перейдет после регистрации
    else:
        form = RegisterForm()
    return render(request, 'users/register.html', {'form': form})

#видимо параметр {'form': form} ну нужен

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