from django.db import migrations
from decimal import Decimal

def fix_deal_data(apps, schema_editor):
    """
    Исправляем некорректные данные в сделках:
    - Заменяем 0E-8 на 0.0 для комиссий и PnL
    - Устанавливаем корректные значения для закрытых сделок
    """
    Deal = apps.get_model('bots', 'Deal')
    
    # Исправляем сделки с некорректными значениями
    deals_to_fix = Deal.objects.filter(
        exchange_commission__lte=Decimal('0.00000001'),
        service_commission__lte=Decimal('0.00000001'),
        pnl__lte=Decimal('0.00000001')
    )
    
    for deal in deals_to_fix:
        # Если сделка закрыта, рассчитываем примерные значения
        if deal.is_filled and not deal.is_active:
            # Примерная комиссия биржи (0.1%)
            deal.exchange_commission = deal.volume * deal.entry_price * Decimal('0.001')
            
            # Если есть exit_price, рассчитываем PnL
            if hasattr(deal, 'exit_price') and deal.exit_price:
                # Получаем стратегию бота
                bot = deal.bot
                if bot and hasattr(bot, 'strategy'):
                    if bot.strategy:  # Long
                        pnl = (deal.exit_price - deal.entry_price) * deal.volume
                    else:  # Short
                        pnl = (deal.entry_price - deal.exit_price) * deal.volume
                    
                    # Применяем плечо если есть
                    if hasattr(bot, 'bot_leverage'):
                        pnl *= bot.bot_leverage
                    
                    deal.pnl = pnl
                    
                    # Комиссия сервиса (10% от прибыли)
                    if pnl > 0:
                        deal.service_commission = pnl * Decimal('0.1')
                    else:
                        deal.service_commission = Decimal('0.0')
        
        deal.save()

def reverse_fix_deal_data(apps, schema_editor):
    """
    Откат изменений (устанавливаем значения обратно в 0E-8)
    """
    Deal = apps.get_model('bots', 'Deal')
    
    deals_to_revert = Deal.objects.filter(
        exchange_commission__gt=Decimal('0.00000001')
    )
    
    for deal in deals_to_revert:
        deal.exchange_commission = Decimal('0.00000001')
        deal.service_commission = Decimal('0.00000001')
        deal.pnl = Decimal('0.00000001')
        deal.save()

class Migration(migrations.Migration):

    dependencies = [
        ('bots', '0017_bot_error_fields'),
    ]

    operations = [
        migrations.RunPython(fix_deal_data, reverse_fix_deal_data),
    ]
