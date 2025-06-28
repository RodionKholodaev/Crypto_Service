from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import BotForm, IndicatorFormSet
from .models import Bot, ExchangeAccount, Indicator
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Sum, F
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
    bot = get_object_or_404(Bot, id=bot_id, user=request.user)
    
    if request.method == 'POST':
        form = BotForm(request.user, request.POST, instance=bot)
        formset = IndicatorFormSet(request.POST, instance=bot)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            if bot.is_active:
                run_trading_bot.apply_async(args=[bot.id], task_id=f"run_trading_bot_{bot.id}")
            
            return redirect('my_bots')
    else:
        form = BotForm(request.user, instance=bot)
        formset = IndicatorFormSet(instance=bot)
    
    exchange_accounts = ExchangeAccount.objects.filter(user=request.user, is_active=True)
    return render(request, 'bots/bot_conf.html', {
        'form': form,
        'formset': formset,
        'exchange_accounts': exchange_accounts,
        'editing': True,
        'bot_id': bot_id
    })

@login_required
def my_bots(request):
    bots = Bot.objects.filter(user=request.user).annotate(
        total_pnl=Sum('deals__pnl'),
        roi=(Sum('deals__pnl') / F('deposit')) * 100
    )
    
    sort_by = request.GET.get('sort', 'name_asc')
    if sort_by == 'name_desc':
        bots = bots.order_by('-name')
    elif sort_by == 'active':
        bots = bots.order_by('-is_active', 'name')
    elif sort_by == 'inactive':
        bots = bots.order_by('is_active', 'name')
    elif sort_by == 'profit':
        bots = bots.order_by('-total_pnl')
    else:
        bots = bots.order_by('name')
    
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
        current_app.control.revoke(f"run_trading_bot_{bot_id}", terminate=True)
    
    return JsonResponse({'status': 'success'})

def bot_details(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, user=request.user)
    deals = bot.deals.all().order_by('-created_at')
    
    context = {
        'bot': bot,
        'deals': deals,
    }
    return render(request, 'bots/bot_details.html', context)

@login_required
def statistics(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, user=request.user)
    chart_path = generate_pnl_chart(bot_id, f'charts/bot_{bot_id}_pnl.png')
    context = {
        'bot': bot,
        'chart_path': chart_path,
    }
    return render(request, 'bots/statistics.html', context)