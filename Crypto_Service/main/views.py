from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect
from .forms import HelpRequestForm

def index(request):
    return render(request,'main/index.html')


def help_view(request):
    if request.method == 'POST':
        form = HelpRequestForm(request.POST)
        if form.is_valid():
            # Получаем данные из формы
            email = form.cleaned_data['email']
            message = form.cleaned_data['message']
            
            # Тема и текст письма
            subject = f'Новое обращение в поддержку от {email}'
            full_message = f"""
            От: {email}
            Сообщение:
            {message}
            
            IP адрес: {request.META.get('REMOTE_ADDR')}
            Пользователь: {'Аутентифицирован' if request.user.is_authenticated else 'Аноним'}
            """
            
            try:
                # Отправка письма
                send_mail(
                    subject=subject,
                    message=full_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.SUPPORT_EMAIL],
                    fail_silently=False,
                )
                
                messages.success(request, 'Ваше сообщение успешно отправлено! Мы ответим вам в ближайшее время.')
                return redirect('help')
            
            except Exception as e:
                messages.error(request, f'Произошла ошибка при отправке: {e}')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        # Для авторизованных пользователей подставляем email
        initial = {}
        if request.user.is_authenticated:
            initial['email'] = request.user.email
        form = HelpRequestForm(initial=initial)
    
    return render(request, 'main/help.html', {'form': form})