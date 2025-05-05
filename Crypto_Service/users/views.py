from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .forms import RegisterForm
from django.contrib import messages

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


def home_view(request):
    user=request.user
    return render(request, 'users/home.html',{'user':user})

def profile(request):
    user=request.user
    return render(request, 'users/profile1.html',{'user':user})

