from django.db import models
from users.models import User
from encrypted_model_fields.fields import EncryptedCharField

# модель для хранения api ключей
class ExchangeAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exchange_accounts')
    name = models.CharField(max_length=100)  # Произвольное название для удобства
    exchange = models.CharField(max_length=50)  # Binance, Bybit и т.д.
    api_key = EncryptedCharField(max_length=255)
    api_secret = EncryptedCharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)



# таблица для хранения данных по каждому боту
class Bot(models.Model):
    # связь с таблицей User
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    name = models.CharField(max_length=100)

    # связь с таблицей с api ключами
    exchange_account = models.ForeignKey(ExchangeAccount, on_delete=models.PROTECT, related_name='bots')
    
    # депозит на бота
    deposit=models.PositiveIntegerField()

    # стратегия (long/short)
    strategy=models.BooleanField()

    # плечо бота
    bot_leverage=models.PositiveIntegerField()
    
    # Основные настройки
    trading_pair = models.CharField(max_length=20)
    take_profit_percent = models.PositiveIntegerField()
    stop_loss_percent = models.PositiveIntegerField()
    
    # Настройки сетки ордеров
    grid_orders_count = models.PositiveIntegerField()
    grid_overlap_percent = models.PositiveIntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)




# данные о том какие индикаторы и как использует бот
class Indicator(models.Model):
    INDICATOR_TYPES = (
        ('RSI', 'Relative Strength Index'),
        ('CCI', 'Commodity Channel Index'),
        # Добавьте другие типы по мере необходимости
    )
    
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='indicators')
    indicator_type = models.CharField(max_length=20, choices=INDICATOR_TYPES)
    timeframe = models.CharField(max_length=10)  # Например: '1h', '4h', '1d'
    parameters = models.JSONField()  # Гибкое хранение настроек
    



# информация по сделкам 
class Deal(models.Model):
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='deals')
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss_price = models.DecimalField(max_digits=20, decimal_places=8)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)