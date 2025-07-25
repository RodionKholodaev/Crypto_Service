from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import BotForm, IndicatorFormSet
from .models import Bot, ExchangeAccount, Indicator
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Sum, F, Count, Q
import json
from .tasks import run_trading_bot
from .statistics import generate_pnl_chart
from celery import current_app



@login_required
def create_bot(request):
    if request.method == 'POST':
        form = BotForm(request.user, request.POST)
        formset = IndicatorFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            bot = form.save(commit=False)
            bot.user = request.user
            bot.save()
            formset.instance = bot
            formset.save()
            
            if bot.is_active:
                # через apply_async мы кладем задачу в очередь в redis, воркеры забирают задачу из очереди и выполняют ее
                run_trading_bot.apply_async(args=[bot.id], task_id=f"run_trading_bot_{bot.id}")
            
            return redirect('home')
    else:
        form = BotForm(user=request.user)
        formset = IndicatorFormSet(queryset=Indicator.objects.none())
    
    return render(request, 'bots/bot_conf.html', {
        'form': form,
        'formset': formset,
        'exchange_accounts': ExchangeAccount.objects.filter(user=request.user, is_active=True)
    })


@login_required
def edit_bot(request, bot_id):
    pass


@login_required
def my_bots(request):
    # Получаем ботов пользователя с аннотациями для статистики
    bots = Bot.objects.filter(user=request.user).annotate(
        # Количество завершенных сделок (не активных и заполненных)
        deals_count=Count(
            'deals',
            filter=Q(deals__is_active=False) & Q(deals__is_filled=True)
        ),
        # Суммарный PNL по завершенным сделкам
        total_pnl=Sum(
            'deals__pnl',
            filter=Q(deals__is_active=False) & Q(deals__is_filled=True)
        ),
        # Суммарные комиссии по завершенным сделкам
        total_exchange_commission=Sum(
            'deals__exchange_commission',
            filter=Q(deals__is_active=False) & Q(deals__is_filled=True)
        ),
        total_service_commission=Sum(
            'deals__service_commission',
            filter=Q(deals__is_active=False) & Q(deals__is_filled=True)
        )
    )
    
    # Добавляем вычисление чистой прибыли и ROI для каждого бота
    for bot in bots:
        # Чистая прибыль = PNL - комиссии
        bot.net_profit = (bot.total_pnl or 0) - (bot.total_exchange_commission or 0) - (bot.total_service_commission or 0)
        
        # ROI = (Чистая прибыль / Депозит) * 100
        if bot.deposit > 0:
            bot.roi = (bot.net_profit / bot.deposit) * 100
        else:
            bot.roi = 0
    
    # Сортировка
    sort_by = request.GET.get('sort', 'name_asc')
    if sort_by == 'name_desc':
        bots = bots.order_by('-name')
    elif sort_by == 'active':
        bots = bots.order_by('-is_active', 'name')
    elif sort_by == 'inactive':
        bots = bots.order_by('is_active', 'name')
    elif sort_by == 'profit':
        bots = bots.order_by('-net_profit')
    else:
        bots = bots.order_by('name')
    
    # Пагинация
    paginator = Paginator(bots, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'bots/my_bots.html', {'bots': page_obj})

@require_POST
@login_required
def delete_bot(request, bot_id):
    try:
        bot = Bot.objects.get(id=bot_id, user=request.user)
        # Отменяем задачу Celery, если она существует
        current_app.control.revoke(f"run_trading_bot_{bot_id}", terminate=True)
        bot.delete()
        return JsonResponse({'status': 'success', 'message': 'Бот успешно удален'})
    except Bot.DoesNotExist:
        return JsonResponse(
            {'status': 'error', 'message': 'Бот не найден'},
            status=404
        )
    except Exception as e:
        return JsonResponse(
            {'status': 'error', 'message': str(e)},
            status=500
        )

@require_POST
@login_required
def toggle_bot(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, user=request.user)
    data = json.loads(request.body)
    activate = data.get('activate', False)
    bot.is_active = activate
    bot.save()
    
    if activate:
        run_trading_bot.apply_async(args=[bot.id], task_id=f"run_trading_bot_{bot.id}")
    else:
        # Отменяем задачу Celery при деактивации
        try:
            current_app.control.revoke(f"run_trading_bot_{bot_id}", terminate=True)
        except Exception as e:
            print (f"ошибка при попытке отменить задачу: {e}")
    
    return JsonResponse({'status': 'success'})

def bot_details(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, user=request.user)
    deals = bot.deals.all().order_by('-created_at')
    
    context = {
        'bot': bot,
        'deals': deals,
    }
    return render(request, 'bots/bot_details.html', context)

