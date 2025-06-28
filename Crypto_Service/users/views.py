from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .forms import RegisterForm, ProfileForm
from django.contrib import messages

from bots.models import ExchangeAccount, Bot, Deal
from .forms import ExchangeAccountForm, EditExchangeAccountForm

from .forms import PasswordResetRequestForm, PasswordResetVerifyForm
from .models import PasswordResetCode
from .utils import generate_reset_code
from django.core.mail import send_mail

from .forms import SetNewPasswordForm
from .models import User
from .forms import EmailConfirmationForm
from .models import EmailConfirmationCode

import ccxt

from django.utils import timezone
from datetime import timedelta


from mnemonic import Mnemonic
from bip32utils import BIP32Key, BIP32_HARDEN
from tronpy.keys import PrivateKey
from web3 import Web3
from django.conf import settings


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



# генерирует USDT-адрес для user_id в указанной сети (TRC20/ERC20)
def generate_crypto_address(user_id: int, network: str) -> str:

    if not settings.CRYPTO_SEED:
        raise ValueError("CRYPTO_SEED не задан в настройках!")

    try:
        # преобразуем seed-фразу в бинарный формат
        mnemo = Mnemonic("english")
        seed = mnemo.to_seed(settings.CRYPTO_SEED)
        master_key = BIP32Key.fromEntropy(seed)
    except Exception as e:
        print(f"ошибка при создании мастер ключа. Ошибка: {e}")
        return "ошибка создания мастер ключа"

    # генерируем адрес в зависимости от сети
    if network == "TRC20":
        # TRON: m/44'/195'/0'/0/{user_id}
        key = (
            master_key
            .ChildKey(44 + BIP32_HARDEN)
            .ChildKey(195 + BIP32_HARDEN)
            .ChildKey(0 + BIP32_HARDEN)
            .ChildKey(0)
            .ChildKey(user_id)
        )
        private_key = PrivateKey(key.PrivateKey())
        return private_key.public_key.to_base58check_address()

    elif network == "ERC20":
        # Ethereum: m/44'/60'/0'/0/{user_id}
        key = (
            master_key
            .ChildKey(44 + BIP32_HARDEN)
            .ChildKey(60 + BIP32_HARDEN)
            .ChildKey(0 + BIP32_HARDEN)
            .ChildKey(0)
            .ChildKey(user_id)
        )
        public_key = key.PublicKey()
        return Web3.to_checksum_address(Web3.keccak(public_key[1:])[-20:].hex())
    return "ошибка при получении сети"
    raise ValueError("Неподдерживаемая сеть")








def home_view(request):
    # request экземпляр класса HttpRequest 
    # request.user хранит данные пользователя в запросе
    user = request.user
    exchange_balance = None
    error_message = None
    total_bots_deposit=0
    number_of_bots=0
    unrealized_pnl = 0  # Инициализируем переменную
    pnl_error = None  
    

    # Получаем первый активный API ключ пользователя для Bybit
    api_key = ExchangeAccount.objects.filter(
        user=user, 
        exchange='bybit', 
        is_active=True
    ).first()
    
    # получение нереализованного pnl
    if api_key:
        try:
            # Инициализируем подключение к Bybit
            exchange = ccxt.bybit({
                'apiKey': api_key.api_key,
                'secret': api_key.api_secret,
                'options': {'defaultType': 'unified'},
                'enableRateLimit': True,
            })

            # Запрашиваем текущие позиции и баланс
            balance, positions = exchange.fetch_balance(), exchange.fetch_positions()
            
            # Суммируем нереализованный PnL для всех открытых позиций
            for pos in positions:
                if float(pos['contracts']) > 0:  # Только открытые позиции
                    unrealized_pnl += float(pos['unrealisedPnl'])

                     
            
            # Получаем баланс
            exchange_balance = balance['total'].get('USDT', 0)
            
        except ccxt.AuthenticationError:
            error_message = "Ошибка аутентификации API ключа"
        except ccxt.NetworkError:
            error_message = "Ошибка соединения с биржей"
        except Exception as e:
            error_message = "Что-то пошло не так"
            print(f"Ошибка: {e}")  # Логируем для дебага



    # Вычисляем сумму депозитов всех ботов пользователя
    bots = Bot.objects.filter(user=user, is_active=True)
    total_bots_deposit = sum(bot.deposit for bot in bots) if bots else 0

    number_of_bots=len(bots)

    weekly_profit = 0
    weekly_profit_percent = 0

    # Фильтруем сделки: закрытые и исполненные за последние 7 дней
    last_week = timezone.now() - timedelta(days=7)
    closed_deals = Deal.objects.filter(
        bot__user=user,
        is_active=False,
        is_filled=True,
        # __gte - фишка django (created_at<last_week)
        created_at__gte=last_week
    )

    # Суммируем PnL
    total_pnl = sum(deal.pnl for deal in closed_deals) if closed_deals else 0

    # Рассчитываем процент прибыли (если есть депозиты)
    if total_bots_deposit > 0:
        weekly_profit_percent = (total_pnl / total_bots_deposit) * 100



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
        'exchange_balance': exchange_balance,
        'balance_error': error_message,
        'total_bots_deposit': total_bots_deposit,  # Добавляем в контекст
        'number_of_bots': number_of_bots,
        'weekly_profit_percent': weekly_profit_percent,
        'weekly_profit_absolute': total_pnl,
        'unrealized_pnl': unrealized_pnl,
        'pnl_error': pnl_error,
        'trc20_address': generate_crypto_address(request.user.id, "TRC20"),
        'erc20_address': generate_crypto_address(request.user.id, "ERC20"),
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

                # Удаляем все коды сброса пароля для этого email
                PasswordResetCode.objects.filter(email=email).delete()

                # Очистить email из сессии после сброса
                del request.session['reset_email']

                messages.success(request, 'Пароль успешно обновлён. Войдите с новым паролем.')
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'Пользователь не найден.')
    else:
        form = SetNewPasswordForm()

    return render(request, 'users/password_reset_set_password.html', {'form': form})
