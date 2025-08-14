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
    
    # Настройки сетки ордеров
    grid_orders_count = models.PositiveIntegerField()
    grid_overlap_percent = models.PositiveIntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_active=models.BooleanField(default=True)

    



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
    bot = models.ForeignKey(
        Bot, 
        on_delete=models.SET_NULL,  # При удалении бота поле станет NULL
        null=True,                  # Разрешает NULL
        blank=True,                 # Разрешает пустое значение в формах
        related_name='deals'
    )
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss_price = models.DecimalField(max_digits=20, decimal_places=8,null=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    exchange_commission=models.DecimalField(max_digits=20, decimal_places=8)
    service_commission=models.DecimalField(max_digits=20, decimal_places=8)
    volume=models.DecimalField(max_digits=20, decimal_places=8)
    pnl=models.DecimalField(max_digits=20, decimal_places=8)
    trading_pair=models.CharField(max_length=30)
    order_id = models.CharField(max_length=100, null=True, blank=True)  # ID ордера на Bybit
    is_filled = models.BooleanField(default=False) # для лимитных ордеров
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True) # цена выхода



class CryptoTransaction(models.Model):
    # выбор для сети
    NETWORK_CHOICES = [
        ('TRC20', 'TRON (TRC20)'),
        ('ERC20', 'Ethereum (ERC20)'),
    ]

    tx_hash = models.CharField(max_length=100, unique=True)  # Хеш транзакции
    network = models.CharField(max_length=10, choices=NETWORK_CHOICES)
    user = models.ForeignKey(User, on_delete=models.CASCADE) # связь с пользователем
    amount = models.DecimalField(max_digits=20, decimal_places=6)  # Сумма USDT
    timestamp = models.DateTimeField()  # Время транзакции в блокчейне
    processed_at = models.DateTimeField(auto_now_add=True)  # Когда обработано у нас

    class Meta:
        indexes = [
            models.Index(fields=['tx_hash', 'network']),  # Для быстрого поиска
        ]

    def __str__(self):
        return f"{self.network}: {self.tx_hash}"