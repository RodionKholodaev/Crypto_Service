from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
import json
from bots.models import Deal, Bot

@require_POST
def get_stats(request):
    try:
        data = json.loads(request.body)
        
        # Получаем параметры фильтрации
        period = data.get('period', '30')
        bot_ids = data.get('bot_ids', [])
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        # Определяем период для фильтрации
        end_date = timezone.now()
        if period == 'custom' and date_from and date_to:
            start_date = timezone.datetime.strptime(date_from, '%Y-%m-%d')
            end_date = timezone.datetime.strptime(date_to, '%Y-%m-%d')
        else:
            days = int(period)
            start_date = end_date - timedelta(days=days)
        
        # Фильтруем сделки
        deals = Deal.objects.filter(
            created_at__range=(start_date, end_date),
            is_active=False,  # Только закрытые сделки
            is_filled=True    # Только исполненные ордера
        )
        
        if bot_ids:
            deals = deals.filter(bot_id__in=bot_ids)
        
        # Общая статистика
        total_deals = deals.count()
        total_profit = deals.aggregate(sum=Sum('pnl'))['sum'] or 0
        total_service_commission = deals.aggregate(sum=Sum('service_commission'))['sum'] or 0
        total_exchange_commission = deals.aggregate(sum=Sum('exchange_commission'))['sum'] or 0
        
        # Процент успешных сделок
        successful_deals = deals.filter(pnl__gt=0).count()
        success_rate = (successful_deals / total_deals * 100) if total_deals > 0 else 0
        
        # Динамика прибыли по дням
        profit_timeline = deals.values('created_at__date').annotate(
            daily_profit=Sum('pnl')
        ).order_by('created_at__date')
        
        timeline_labels = [item['created_at__date'].strftime('%d.%m.%Y') for item in profit_timeline]
        timeline_data = [float(item['daily_profit']) for item in profit_timeline]
        
        # Последние 10 сделок
        recent_deals = deals.select_related('bot').order_by('-created_at')[:10]
        recent_deals_data = [
            {
                'bot_name': deal.bot.name,
                'trading_pair': deal.trading_pair,
                'created_at': deal.created_at.isoformat(),
                'strategy': 'long' if deal.bot.strategy else 'short',
                'volume': float(deal.volume),
                'pnl': float(deal.pnl),
                'service_commission': float(deal.service_commission),
                'exchange_commission': float(deal.exchange_commission)
            }
            for deal in recent_deals
        ]
        
        return JsonResponse({
            'status': 'success',
            'data': {
                'total_profit': float(total_profit),
                'total_deals': total_deals,
                'success_rate': float(success_rate),
                'total_service_commission': float(total_service_commission),
                'total_exchange_commission': float(total_exchange_commission),
                'profit_timeline': {
                    'labels': timeline_labels,
                    'data': timeline_data
                },
                'recent_deals': recent_deals_data
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

def analytics_view(request):
    # Получаем всех ботов пользователя для фильтра
    user_bots = Bot.objects.filter(user=request.user).only('id', 'name')
    return render(request, 'analytics/analytics.html', {
        'user_bots': user_bots
    })