# analytics/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from users.models import User
from bots.models import Deal, Bot
import json

@login_required
def statistics_view(request):
    # Получаем всех ботов пользователя для фильтра
    user_bots = Bot.objects.filter(user=request.user)
    return render(request, 'analytics/statistics.html', {
        'user_bots': user_bots
    })

@login_required
def get_deals_stats(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    try:
        data = json.loads(request.body)
        period_days = int(data.get('period_days', 30))
        bot_ids = data.get('bot_ids', [])
        
        # Рассчитываем дату начала периода
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        
        # Фильтруем сделки по пользователю, периоду и завершенным сделкам
        deals = Deal.objects.filter(
            bot__user=request.user,
            created_at__range=(start_date, end_date),
            is_active=False
        )
        
        # Дополнительная фильтрация по ботам, если выбраны конкретные
        if 'all' not in bot_ids:
            deals = deals.filter(bot_id__in=bot_ids)
        
        # Рассчитываем статистику
        total_deals = deals.count()
        profitable = deals.filter(pnl__gt=0).count()
        unprofitable = deals.filter(pnl__lt=0).count()
        
        total_pnl = sum(deal.pnl for deal in deals)
        exchange_commission = sum(deal.exchange_commission for deal in deals)
        service_commission = sum(deal.service_commission for deal in deals)
        
        # Группируем данные по дням для гистограммы
        daily_data = deals.extra({
            'day': "DATE(created_at)"
        }).values('day').annotate(
            daily_pnl=Sum('pnl'),
            daily_commission=Sum('exchange_commission') + Sum('service_commission')
        ).order_by('day')
        
        # Формируем данные для графиков
        pie_data = [
            max(0, float(total_pnl)),    # Прибыль
            abs(min(0, float(total_pnl))), # Убыток
            float(exchange_commission),    # Комиссия биржи
            float(service_commission)      # Комиссия сервиса
        ]
        
        bar_labels = [entry['day'].strftime('%Y-%m-%d') for entry in daily_data]
        bar_data = [float(entry['daily_pnl'] - entry['daily_commission']) for entry in daily_data]
        
        response_data = {
            'totalDeals': total_deals,
            'profitable': profitable,
            'unprofitable': unprofitable,
            'totalPnl': float(total_pnl),
            'exchangeCommission': float(exchange_commission),
            'serviceCommission': float(service_commission),
            'pieData': pie_data,
            'barLabels': bar_labels,
            'barData': bar_data
        }
        
        return JsonResponse(response_data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)