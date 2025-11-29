from django.db import models
from users.models import User
from encrypted_model_fields.fields import EncryptedCharField
from django.utils import timezone


# модель для хранения api ключей
class ExchangeAccount(models.Model):
    EXCHANGE_CHOICES = [
        ('binance', 'Binance'),
        ('bybit', 'Bybit'),
        ('okx', 'OKX'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exchange_accounts')
    name = models.CharField(max_length=100)  # Произвольное название для удобства
    exchange = models.CharField(max_length=50, choices=EXCHANGE_CHOICES) # Binance, Bybit и т.д.
    api_key = EncryptedCharField(max_length=255)
    api_secret = EncryptedCharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.exchange})" # вывод: название аккаута (биржа), если выполним {ExchangeAccount} где-то в шаблоне



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
    # take_profit_percent = models.PositiveIntegerField()
    # stop_loss_percent = models.PositiveIntegerField(blank=True, null=True,default=None)

    take_profit_percent = models.DecimalField(
        max_digits=5,         # Максимум 5 цифр (включая дробную часть)
        decimal_places=1,     # 1 знак после запятой (например: 25.5, 0.1, 100.0)
        default=5.0,          # Значение по умолчанию (если нужно)
    )

    stop_loss_percent = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        blank=True,
        null=True,
        default=None,
    )
    
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active=models.BooleanField(default=True)

    # Поле для хранения последней ошибки бота
    last_error = models.TextField(blank=True, null=True, help_text="Последняя ошибка, возникшая в работе бота")
    error_timestamp = models.DateTimeField(blank=True, null=True, help_text="Время возникновения ошибки")

    



# модель Indicator с пороговыми значениями
class Indicator(models.Model):
    INDICATOR_TYPES = (
        ('RSI', 'Relative Strength Index'),
        ('CCI', 'Commodity Channel Index'),
        ('STOCH_RSI', 'Stochastic RSI'),
        ('WILLIAMS_R', 'Williams %R'),
        ('MFI', 'Money Flow Index'),
        ('BB_PBAND', 'Bollinger Bands %B'),
        ('VOL_SMA', 'Volume SMA Ratio'),
    )
    
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='indicators')
    indicator_type = models.CharField(max_length=20, choices=INDICATOR_TYPES)
    timeframe = models.CharField(max_length=10)  # '1m', '5m', '15m', '1h', '4h', '1d'
    
    # Параметры расчета индикатора
    period = models.PositiveIntegerField(default=14)
    
    # Пороговые значения для сигнала
    threshold_value = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Пороговое значение для входа в сделку"
    )
    
    # Направление пересечения порога
    # 'above' - индикатор должен быть выше порога
    # 'below' - индикатор должен быть ниже порога
    cross_direction = models.CharField(
        max_length=10,
        choices=(('above', 'Выше'), ('below', 'Ниже')),
        default='below'
    )
    
    # Дополнительные параметры (для Bollinger Bands, Stochastic и т.д.)
    extra_params = models.JSONField(default=dict, blank=True)
    
    # Последнее значение индикатора (для отслеживания пересечения)
    last_value = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        blank=True, 
        null=True
    )
    
    class Meta:
        unique_together = ('bot', 'indicator_type', 'timeframe', 'threshold_value')



# models.py
class Deal(models.Model):
    """История сделок бота"""
    
    DEAL_STATUS = (
        ('OPEN', 'Открыта'),
        ('CLOSED_TP', 'Закрыта по Take Profit'),
        ('CLOSED_SL', 'Закрыта по Stop Loss'),
        ('CLOSED_MANUAL', 'Закрыта вручную'),
        ('ERROR', 'Ошибка'),
    )
    
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='deals')
    
    # Параметры входа
    entry_time = models.DateTimeField(auto_now_add=True)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    position_size = models.DecimalField(max_digits=20, decimal_places=8)
    side = models.CharField(max_length=10)  # 'buy' или 'sell'
    leverage = models.PositiveIntegerField()
    
    # Параметры выхода
    exit_time = models.DateTimeField(blank=True, null=True)
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, blank=True, null=True)
    
    # TP/SL
    take_profit_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss_price = models.DecimalField(max_digits=20, decimal_places=8, blank=True, null=True)
    
    # Результаты
    status = models.CharField(max_length=20, choices=DEAL_STATUS, default='OPEN')
    profit_loss = models.DecimalField(max_digits=20, decimal_places=8, blank=True, null=True)
    profit_loss_percent = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # ID ордера на бирже
    exchange_order_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Дополнительная информация
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-entry_time']
    
    def calculate_profit(self):
        """Расчет прибыли/убытка"""
        if not self.exit_price:
            return None
        
        entry = float(self.entry_price)
        exit = float(self.exit_price)
        size = float(self.position_size)
        
        if self.side == 'buy':
            pnl = (exit - entry) * size
        else:  # sell (short)
            pnl = (entry - exit) * size
        
        pnl_percent = (pnl / (entry * size)) * 100
        
        self.profit_loss = pnl
        self.profit_loss_percent = pnl_percent
        self.save()
        
        return pnl, pnl_percent



# class CryptoTransaction(models.Model):
#     # выбор для сети
#     NETWORK_CHOICES = [
#         ('TRC20', 'TRON (TRC20)'),
#         ('ERC20', 'Ethereum (ERC20)'),
#     ]

#     tx_hash = models.CharField(max_length=100, unique=True)  # Хеш транзакции
#     network = models.CharField(max_length=10, choices=NETWORK_CHOICES)
#     user = models.ForeignKey(User, on_delete=models.CASCADE) # связь с пользователем
#     amount = models.DecimalField(max_digits=20, decimal_places=6)  # Сумма USDT
#     timestamp = models.DateTimeField()  # Время транзакции в блокчейне
#     processed_at = models.DateTimeField(auto_now_add=True)  # Когда обработано у нас

#     class Meta:
#         indexes = [
#             models.Index(fields=['tx_hash', 'network']),  # Для быстрого поиска
#         ]

#     def __str__(self):
#         return f"{self.network}: {self.tx_hash}"