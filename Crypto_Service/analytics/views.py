from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from bots.models import Deal, Bot
from django.db.models.functions import TruncDay

from django.http import HttpResponse, JsonResponse
from django.views import View
import csv
import json
from openpyxl import Workbook
from io import BytesIO



def dashboard_view(request):
    # Базовый queryset: только закрытые и исполненные сделки
    deals = Deal.objects.filter(
        is_active=False,
        is_filled=True,
        bot__user=request.user
    ).select_related('bot').exclude(pnl=0)  # Исключаем сделки с нулевым PnL

    now = timezone.now()
    time_period = request.GET.get('time_period', 'week')

    # Фильтр по времени
    if time_period == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
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
            try:
                start = datetime.strptime(date_from, "%Y-%m-%d")
                end = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
                deals = deals.filter(created_at__range=[start, end])
            except ValueError:
                pass

    # Фильтр по боту
    bot_filter = request.GET.get('bot_filter')
    if bot_filter and bot_filter != 'all':
        deals = deals.filter(bot_id=bot_filter)

    # Фильтр по паре
    pair_filter = request.GET.get('pair_filter')
    if pair_filter and pair_filter != 'all':
        deals = deals.filter(trading_pair=pair_filter)

    # Основные метрики
    total_profit = deals.aggregate(Sum('pnl'))['pnl__sum'] or 0
    total_deposit = Bot.objects.filter(user=request.user).aggregate(Sum('deposit'))['deposit__sum'] or 0
    profit_percent = (total_profit / total_deposit * 100) if total_deposit > 0 else 0

    total_deals = deals.count()
    win_deals = deals.filter(pnl__gt=0).count()
    win_rate = (win_deals / total_deals * 100) if total_deals > 0 else 0
    avg_profit_per_deal = total_profit / total_deals if total_deals > 0 else 0

    # Гистограмма
    daily_profit_qs = (
        deals.annotate(date=TruncDay('created_at'))
        .values('date')
        .annotate(profit=Sum('pnl'))
        .order_by('date')
    )
    
    # Проверяем, что есть данные для графика
    if daily_profit_qs.exists():
        daily_profit_labels = [dp['date'].strftime('%Y-%m-%d') for dp in daily_profit_qs]
        daily_profit_values = [float(dp['profit']) for dp in daily_profit_qs]
    else:
        daily_profit_labels = []
        daily_profit_values = []

    # Круговая диаграмма
    profit_loss_data = {
        'profit': float(deals.filter(pnl__gt=0).aggregate(Sum('pnl'))['pnl__sum'] or 0),
        'loss': abs(float(deals.filter(pnl__lt=0).aggregate(Sum('pnl'))['pnl__sum'] or 0)),
        'commission': float(deals.aggregate(Sum('exchange_commission'))['exchange_commission__sum'] or 0),
    }
    
    # Проверяем, что есть данные для круговой диаграммы
    if not any([profit_loss_data['profit'], profit_loss_data['loss'], profit_loss_data['commission']]):
        profit_loss_data = {'profit': 0, 'loss': 0, 'commission': 0}

    # Пагинация
    paginator = Paginator(deals.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    deals_page = paginator.get_page(page_number)

    user_bots = Bot.objects.filter(user=request.user)
    trading_pairs = deals.values_list('trading_pair', flat=True).distinct()

    context = {
        'deals': deals_page,
        'total_profit': total_profit,
        'profit_percent': profit_percent,
        'total_deals': total_deals,
        'win_rate': win_rate,
        'avg_profit_per_deal': avg_profit_per_deal,
        'daily_profit_labels': daily_profit_labels,
        'daily_profit_values': daily_profit_values,
        'profit_loss_data': profit_loss_data,
        'user_bots': user_bots,
        'trading_pairs': trading_pairs,
        'time_period': time_period,
        'date_from': request.GET.get('date_from', ''),
        'date_to': request.GET.get('date_to', ''),
    }
    return render(request, 'analytics/dashboard.html', context)


# скачивание данных
class ExportDealsView(View):
    def get(self, request):
        # Получаем фильтры из запроса
        deals = Deal.objects.filter(bot__user=request.user)
        
        # Применяем фильтры
        time_period = request.GET.get('time_period', 'today')
        if time_period == 'today':
            deals = deals.filter(created_at__date=timezone.now().date())
        elif time_period == 'week':
            deals = deals.filter(created_at__gte=timezone.now() - timezone.timedelta(days=7))
        elif time_period == 'month':
            deals = deals.filter(created_at__gte=timezone.now() - timezone.timedelta(days=30))
        elif time_period == 'custom':
            date_from = request.GET.get('date_from')
            date_to = request.GET.get('date_to')
            if date_from and date_to:
                deals = deals.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
        
        bot_filter = request.GET.get('bot_filter')
        if bot_filter and bot_filter != 'all':
            deals = deals.filter(bot_id=bot_filter)
        
        pair_filter = request.GET.get('pair_filter')
        if pair_filter and pair_filter != 'all':
            deals = deals.filter(trading_pair=pair_filter)
        
        # Получаем формат экспорта
        export_format = request.GET.get('export_format', 'csv')
        
        # Подготавливаем данные
        deals_data = deals.values(
            'created_at',
            'bot__name',
            'trading_pair',
            'volume',
            'entry_price',
            'take_profit_price',
            'stop_loss_price',
            'exit_price',
            'pnl',
            'exchange_commission',
            'service_commission',
            'order_id',
            'is_filled'
        )
        
        # Экспорт в выбранном формате
        if export_format == 'csv':
            return self.export_csv(deals_data)
        elif export_format == 'json':
            return self.export_json(deals_data)
        elif export_format == 'excel':
            return self.export_excel(deals_data)
        else:
            return HttpResponse("Unsupported format", status=400)
    
    def export_csv(self, queryset):
        response = HttpResponse(
            content_type='text/csv; charset=utf-8-sig'  # utf-8-sig для Excel
        )
        response['Content-Disposition'] = 'attachment; filename="deals_export.csv"'
        
        writer = csv.writer(response, delimiter=';')  # Используем ; как разделитель
        
        # Заголовки
        headers = [
            'Date', 'Bot Name', 'Trading Pair', 'Volume', 
            'Entry Price', 'Take Profit', 'Stop Loss', 'Exit Price', 'PNL',
            'Exchange Commission', 'Service Commission', 'Order ID', 'Is Filled'
        ]
        writer.writerow(headers)
        
        # Данные
        for deal in queryset:
            writer.writerow([
                deal['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                deal['bot__name'],
                deal['trading_pair'],
                str(deal['volume']).replace('.', ','),  # Для русской локализации
                str(deal['entry_price']).replace('.', ','),
                str(deal['take_profit_price']).replace('.', ','),
                str(deal['stop_loss_price']).replace('.', ',') if deal['stop_loss_price'] else '',
                str(deal['exit_price']).replace('.', ',') if deal['exit_price'] else '',
                str(deal['pnl']).replace('.', ','),
                str(deal['exchange_commission']).replace('.', ','),
                str(deal['service_commission']).replace('.', ','),
                deal['order_id'] or '',
                'Yes' if deal['is_filled'] else 'No'
            ])
        
        return response
    
    def export_json(self, queryset):
        data = list(queryset)
        for item in data:
            item['created_at'] = item['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            item['is_filled'] = 'Yes' if item['is_filled'] else 'No'
            # Добавляем поле exit_price если его нет
            if 'exit_price' not in item:
                item['exit_price'] = None
        
        response = JsonResponse(data, safe=False)
        response['Content-Disposition'] = 'attachment; filename="deals_export.json"'
        return response
    
    def export_excel(self, queryset):
        wb = Workbook()
        ws = wb.active
        ws.title = "Deals"
        
        # Заголовки
        ws.append([
            'Date', 'Bot Name', 'Trading Pair', 'Volume', 'Entry Price', 
            'Take Profit', 'Stop Loss', 'Exit Price', 'PNL', 'Exchange Commission', 
            'Service Commission', 'Order ID', 'Is Filled'
        ])
        
        # Данные
        for deal in queryset:
            ws.append([
                deal['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                deal['bot__name'],
                deal['trading_pair'],
                float(deal['volume']),
                float(deal['entry_price']),
                float(deal['take_profit_price']),
                float(deal['stop_loss_price']) if deal['stop_loss_price'] else None,
                float(deal['exit_price']) if deal['exit_price'] else None,
                float(deal['pnl']),
                float(deal['exchange_commission']),
                float(deal['service_commission']),
                deal['order_id'] or '',
                'Yes' if deal['is_filled'] else 'No'
            ])
        
        # Сохраняем в BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="deals_export.xlsx"'
        return response