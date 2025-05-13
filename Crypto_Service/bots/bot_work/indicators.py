import json
import logging
from typing import Dict, List, Optional
import redis
import pandas as pd
import talib
from websockets import connect
from django.conf import settings
from celery import shared_task

logger = logging.getLogger(__name__)

class IndicatorChecker:
    """
    Класс для мониторинга торговых индикаторов в сервисе торговых ботов.
    Поддерживает REST API и WebSocket подключения к Bybit.
    
    Особенности:
    - Кэширование данных в Redis
    - Автоматическое восстановление WebSocket соединений
    - Поддержка множества торговых пар и индикаторов
    - Интеграция с Celery для периодических задач
    """
    
    def __init__(self, redis_client: redis.Redis = None):
        """
        Инициализация с подключением к Redis.
        
        :param redis_client: Экземпляр Redis клиента (по умолчанию берется из настроек Django)
        """
        self.redis = redis_client or redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB
        )
        self.ws_connections = {}
        
    async def initialize_indicators(self, bot_config: Dict):
        """
        Инициализация индикаторов для конкретного бота.
        
        :param bot_config: Конфигурация бота из БД
        """
        symbol = bot_config['symbol']
        timeframe = bot_config['timeframe']
        
        # Загрузка исторических данных при старте
        await self._fetch_initial_data(symbol, timeframe)
        
        # Запуск WebSocket подключения
        await self._start_ws_connection(symbol, timeframe)

    async def _fetch_initial_data(self, symbol: str, timeframe: str):
        """
        Получение начальных данных через REST API.
        
        :param symbol: Торговая пара (BTCUSDT)
        :param timeframe: Таймфрейм (1, 5, 15 и т.д.)
        """
        try:
            # Здесь должен быть код запроса к Bybit API
            # Для примера используем mock-данные
            data = self._mock_fetch_klines(symbol, timeframe)
            
            # Сохраняем в Redis
            self.redis.set(
                f"bybit:{symbol}:{timeframe}:klines",
                json.dumps(data),
                ex=3600  # TTL 1 час
            )
            logger.info(f"Initial data loaded for {symbol}_{timeframe}")
        except Exception as e:
            logger.error(f"Error fetching initial data: {e}")
            raise

    async def _start_ws_connection(self, symbol: str, timeframe: str):
        """
        Запуск WebSocket подключения для пары.
        
        :param symbol: Торговая пара
        :param timeframe: Таймфрейм
        """
        ws_url = "wss://stream.bybit.com/v5/public/linear"
        topic = f"kline.{timeframe}.{symbol}"
        
        try:
            async with connect(ws_url) as ws:
                self.ws_connections[f"{symbol}_{timeframe}"] = ws
                await ws.send(json.dumps({
                    "op": "subscribe",
                    "args": [topic]
                }))
                
                while True:
                    data = await ws.recv()
                    await self._process_ws_message(data)
        except Exception as e:
            logger.error(f"WS connection error: {e}")
            # Автопереподключение через 5 секунд
            await asyncio.sleep(5)
            await self._start_ws_connection(symbol, timeframe)

    async def _process_ws_message(self, message: str):
        """
        Обработка входящих сообщений WebSocket.
        
        :param message: Сообщение от Bybit WS
        """
        try:
            data = json.loads(message)
            if 'topic' in data and 'kline' in data['topic']:
                # Обновляем кэш
                symbol = data['topic'].split('.')[-1]
                self.redis.set(
                    f"bybit:{symbol}:current_kline",
                    json.dumps(data['data']),
                    ex=60  # TTL 1 минута
                )
                
                # Триггерим пересчет индикаторов
                self._trigger_indicator_recalculation(symbol)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid WS message: {e}")

    def _trigger_indicator_recalculation(self, symbol: str):
        """
        Запуск асинхронного пересчета индикаторов через Celery.
        
        :param symbol: Торговая пара
        """
        recalculate_indicators.delay(symbol)

    def get_current_values(self, symbol: str, indicators: List[str]) -> Dict:
        """
        Получение текущих значений индикаторов.
        
        :param symbol: Торговая пара
        :param indicators: Список запрашиваемых индикаторов
        :return: Словарь с текущими значениями
        """
        result = {}
        
        for indicator in indicators:
            # Получаем из Redis
            value = self.redis.get(f"bybit:{symbol}:indicator:{indicator}")
            if value:
                result[indicator] = float(value.decode())
                
        return result

    def check_entry_conditions(self, bot_config: Dict) -> bool:
        """
        Проверка условий для входа в сделку.
        
        :param bot_config: Конфигурация бота
        :return: True если условия выполнены
        """
        symbol = bot_config['symbol']
        indicators = bot_config['indicators']
        
        try:
            current_values = self.get_current_values(symbol, indicators.keys())
            
            for ind_name, conditions in indicators.items():
                if ind_name not in current_values:
                    return False
                    
                # Пример проверки для RSI
                if ind_name.startswith('RSI'):
                    if conditions['type'] == 'oversold':
                        if current_values[ind_name] > conditions['threshold']:
                            return False
                    elif conditions['type'] == 'overbought':
                        if current_values[ind_name] < conditions['threshold']:
                            return False
                            
            return True
            
        except Exception as e:
            logger.error(f"Condition check failed: {e}")
            return False

    # Mock-метод для тестирования
    def _mock_fetch_klines(self, symbol: str, timeframe: str) -> List[Dict]:
        """Генерация тестовых данных"""
        return [{
            'open': 50000 + i,
            'high': 51000 + i,
            'low': 49000 + i,
            'close': 50500 + i,
            'volume': 1000 + i,
            'timestamp': i
        } for i in range(100)]

@shared_task
def recalculate_indicators(symbol: str):
    """
    Celery-задача для пересчета индикаторов.
    
    :param symbol: Торговая пара
    """
    try:
        checker = IndicatorChecker()
        # Здесь должен быть код расчета индикаторов
        # Например:
        rsi_value = 30.5  # Расчетное значение
        checker.redis.set(
            f"bybit:{symbol}:indicator:RSI",
            rsi_value,
            ex=300  # TTL 5 минут
        )
    except Exception as e:
        logger.error(f"Indicator recalculation failed: {e}")