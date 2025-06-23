from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import timedelta
from bots.models import Deal, Bot
from django.db.models.functions import TruncDay

def dashboard_view(request):
    # Фильтрация сделок (только закрытые и исполненные)
    deals = Deal.objects.filter(
        is_active=False,
        is_filled=True,
        bot__user=request.user  # Только сделки текущего пользователя
    ).select_related('bot')

    # 1. Фильтр по времени
    time_period = request.GET.get('time_period', 'week')
    now = timezone.now()

    if time_period == 'today':
        start_date = now.replace(hour=0, minute=0, second=0)
        deals = deals.filter(created_at__gte=start_date)
    elif time_period == 'week':
        start_date = now - timedelta(days=7)
        deals = deals.filter(created_at__gte=start_date)
    elif time_period == 'month':
        start_date = now - timedelta(days=30)
        deals = deals.filter(created_at__gte=start_date)
    elif time_period == 'custom':
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        if date_from and date_to:
            deals = deals.filter(created_at__range=[date_from, date_to])

    # 2. Фильтр по ботам (если выбран)
    bot_filter = request.GET.get('bot_filter')
    if bot_filter and bot_filter != 'all':
        deals = deals.filter(bot_id=bot_filter)

    # 3. Основные метрики
    total_profit = deals.aggregate(Sum('pnl'))['pnl__sum'] or 0
    total_deposit = Bot.objects.filter(user=request.user).aggregate(Sum('deposit'))['deposit__sum'] or 1
    profit_percent = (total_profit / total_deposit) * 100

    total_deals = deals.count()
    win_deals = deals.filter(pnl__gt=0).count()
    win_rate = (win_deals / total_deals * 100) if total_deals > 0 else 0
    avg_profit_per_deal = total_profit / total_deals if total_deals > 0 else 0

    # 4. Данные для гистограммы (прибыль по дням)
    daily_profit = (
        deals.annotate(date=TruncDay('created_at'))
        .values('date')
        .annotate(profit=Sum('pnl'))
        .order_by('date')
    )

    # 5. Данные для круговой диаграммы (распределение PnL)
    profit_loss_data = {
        'profit': deals.filter(pnl__gt=0).aggregate(Sum('pnl'))['pnl__sum'] or 0,
        'loss': abs(deals.filter(pnl__lt=0).aggregate(Sum('pnl'))['pnl__sum'] or 0),
        'commission': deals.aggregate(Sum('exchange_commission'))['exchange_commission__sum'] or 0,
    }

    # 6. Таблица сделок (с пагинацией)
    paginator = Paginator(deals.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    deals_page = paginator.get_page(page_number)

    # 7. Списки для фильтров
    user_bots = Bot.objects.filter(user=request.user)
    trading_pairs = deals.values_list('trading_pair', flat=True).distinct()

    context = {
        'deals': deals_page,
        'total_profit': total_profit,
        'profit_percent': profit_percent,
        'total_deals': total_deals,
        'win_rate': win_rate,
        'avg_profit_per_deal': avg_profit_per_deal,
        'daily_profit': list(daily_profit),
        'profit_loss_data': profit_loss_data,
        'user_bots': user_bots,
        'trading_pairs': trading_pairs,
        'time_period': time_period,
    }
    return render(request, 'analytics/dashboard.html', context)