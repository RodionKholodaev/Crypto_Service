import asyncio
import ccxt.async_support as ccxt
from ta.momentum import RSIIndicator
from ta.trend import CCIIndicator
from django.conf import settings
from bots.models import Bot, Deal, ExchangeAccount
from users.models import User
import pandas as pd
import logging
from django.core.mail import send_mail
from asgiref.sync import sync_to_async
import time
from datetime import datetime
import math


# Настройка логирования
logger = logging.getLogger('trading_bot')
logger.setLevel(logging.INFO)

# Обработчик для вывода в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class TradingBot:
    def __init__(self, bot_id):
        self.bot_id = bot_id
        self.bot = None
        self.client = None
        self.running = False
        self.notified = False  # Флаг для предотвращения спама уведомлениями

    async def initialize(self):
        """Инициализация бота: загрузка данных из модели и подключение к бирже через CCXT."""
        logger.info(f"Начало инициализации бота ID: {self.bot_id}")
        try:
            # Получаем данные бота из базы данных
            self.bot = await sync_to_async(Bot.objects.get)(id=self.bot_id)
            logger.info(f"Бот {self.bot_id} успешно загружен из базы данных")

            # Получаем exchange_account и его поля
            exchange_account = await sync_to_async(lambda: self.bot.exchange_account)()
            exchange_name = await sync_to_async(lambda: exchange_account.exchange)()
            api_key = await sync_to_async(lambda: exchange_account.api_key)()
            api_secret = await sync_to_async(lambda: exchange_account.api_secret)()

            # Инициализация клиента CCXT
            exchange_class = getattr(ccxt, exchange_name.lower(), None)
            if exchange_class is None:
                raise ValueError(f"Биржа {exchange_name} не поддерживается CCXT")
            self.client = exchange_class({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'asyncio_loop': asyncio.get_event_loop(),
                'defaultType': 'future',  # Фьючерсы
                'enableUnifiedAccount': True,  # Для USDT-фьючерсов
                'timeout': 30000, # почему-то не получается свзяваться с bybit (увеличил timeout для проверки)
            })
            # Устанавливаем реальную сеть 
            self.client.set_sandbox_mode(False)
            await self.client.load_markets()
            logger.info(f"Клиент CCXT для {exchange_name} инициализирован")

            self.running = await sync_to_async(lambda: self.bot.is_active)()
            logger.info(f"Бот ID: {self.bot_id} инициализирован, is_active: {self.running}")
            # Очищаем предыдущие ошибки при успешной инициализации
            if self.bot.last_error:
                await sync_to_async(lambda: setattr(self.bot, 'last_error', None))()
                await sync_to_async(lambda: setattr(self.bot, 'error_timestamp', None))()
                await sync_to_async(self.bot.save)()
                logger.info(f"Ошибки очищены для бота {self.bot_id}")
            self.notified = False  # Сбрасываем флаг уведомлений
        except Bot.DoesNotExist:
            error_msg = "Бот не найден в базе данных"
            logger.error(f"Бот с ID {self.bot_id} не найден")
            await self.save_error(error_msg, "not_found")
            if not self.notified:
                await sync_to_async(self.notify_admin)(f"Ошибка: Бот с ID {self.bot_id} не найден")
                self.notified = True
            self.running = False
        except Exception as e:
            error_msg = self.translate_error(str(e))
            logger.error(f"Ошибка инициализации бота {self.bot_id}: {e}", exc_info=True)
            await self.save_error(error_msg, "initialization")
            if not self.notified:
                await sync_to_async(self.notify_admin)(f"Ошибка инициализации бота {self.bot_id}: {str(e)}")
                self.notified = True
            self.running = False

    def notify_admin(self, message):
        """Отправка уведомления администратору."""
        try:
            send_mail(
                subject=f'Ошибка в боте {self.bot_id}',
                message=message,
                from_email=None,
                recipient_list=[settings.ADMIN_EMAIL],
                fail_silently=True,
            )
            logger.info(f"Уведомление отправлено администратору: {message}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления администратору: {e}")

    
    async def send_trade_notification(self, event_type, deal=None, indicators_data=None):
        """Отправка уведомления о входе/выходе из сделки"""
        try:
            bot_name = await sync_to_async(lambda: self.bot.name)()
            user = await sync_to_async(lambda: self.bot.user)()
            trading_pair = await sync_to_async(lambda: self.bot.trading_pair)()
            trading_pair_formatted = f"{trading_pair[:-4]}/{trading_pair[-4:]}:USDT"

            if event_type == "entry":
                subject = f"Бот {bot_name} вошёл в сделку"
                message = (
                    f"Вход в сделку:\n"
                    f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Пользователь: {user.email}\n"
                    f"Торговая пара: {trading_pair_formatted}\n"
                    f"Цена входа: {deal.entry_price}\n"
                    f"Объем: {deal.volume}\n"
                    f"Индикаторы на момент входа:\n"
                )
                for ind_name, value in indicators_data.items():
                    message += f"- {ind_name}: {value:.2f}\n"

            elif event_type == "exit":
                subject = f"Бот {bot_name} вышел из сделки"
                message = (
                    f"Выход из сделки:\n"
                    f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Пользователь: {user.email}\n"
                    f"Торговая пара: {trading_pair_formatted}\n"
                    f"Цена выхода: {deal.exit_price if hasattr(deal, 'exit_price') else 'N/A'}\n"
                    f"PNL: {deal.pnl:.2f} USDT\n"
                    f"Комиссия биржи: {deal.exchange_commission:.4f} USDT\n"
                    f"Комиссия сервиса: {deal.service_commission:.2f} USDT\n"
                    f"Итог: {deal.pnl - deal.service_commission:.2f} USDT"
                )

            send_mail(
                subject=subject,
                message=message,
                from_email=None,
                recipient_list=[settings.ADMIN_EMAIL],
                fail_silently=True,
            )
            logger.info(f"Уведомление о {event_type} отправлено")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о сделке: {e}")



    async def check_time_sync(self):
        """Проверка синхронизации времени с сервером биржи."""
        try:
            server_time = await self.client.fetch_time()
            server_timestamp = server_time // 1000  # CCXT возвращает время в миллисекундах
            local_timestamp = int(time.time())
            time_diff = abs(server_timestamp - local_timestamp)
            logger.info(f"Серверное время: {server_timestamp}, Локальное время: {local_timestamp}, Разница: {time_diff} сек")
            if time_diff > 2:  # Допустимая разница 2 секунды
                logger.warning(f"Время не синхронизировано! Разница: {time_diff} секунд")
                if not self.notified:
                    await sync_to_async(self.notify_admin)(
                        f"Время не синхронизировано для бота {self.bot_id}. Разница: {time_diff} секунд"
                    )
                    self.notified = True
                return False
            logger.info("Время синхронизировано успешно")
            return True
        except Exception as e:
            logger.error(f"Ошибка при проверке времени сервера: {e}")
            if not self.notified:
                await sync_to_async(self.notify_admin)(f"Ошибка при проверки времени сервера для бота {self.bot_id}: {str(e)}")
                self.notified = True
            return False

    async def get_symbol_specs(self, symbol):
        """Получение спецификаций торговой пары."""
        logger.info(f"Получение спецификаций для {symbol}")
        try:
            market = self.client.markets[symbol]
            if not market:
                logger.error(f"Торговая пара {symbol} не найдена")
                return None
            return {
                'qty_step': float(market['precision']['amount']),
                'min_order_qty': float(market['limits']['amount']['min'] or 0.1),
                'max_order_qty': float(market['limits']['amount']['max'] or float('inf')),
                'min_notional': float(market['limits']['cost']['min'] or 5.0)  # Минимальная стоимость ордера
            }
        except Exception as e:
            logger.error(f"Ошибка при получении спецификаций для {symbol}: {e}", exc_info=True)
            if not self.notified:
                await sync_to_async(self.notify_admin)(f"Ошибка при получении спецификаций для {symbol} в боте {self.bot_id}: {str(e)}")
                self.notified = True
            return None

    async def get_kline_data(self, symbol, timeframe):
        """Получение данных свечей для расчета индикаторов."""
        logger.info(f"Получение данных свечей для {symbol} на таймфрейме {timeframe}")
        try:
            ohlcv = await self.client.fetch_ohlcv(symbol, timeframe, limit=100)
            if not ohlcv:
                logger.error(f"Некорректный ответ от API для {symbol}")
                return None

            df = pd.DataFrame(ohlcv, columns=['start_time', 'open', 'high', 'low', 'close', 'volume'])
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            logger.debug(f"Получены данные свечей для {symbol} на таймфрейме {timeframe}")
            return df
        except Exception as e:
            logger.error(f"Ошибка при получении данных свечей для {symbol}: {e}", exc_info=True)
            return None

    async def check_indicators(self):
        """Проверка сигналов индикаторов."""
        bot_name = await sync_to_async(lambda: self.bot.name)()
        logger.info(f"Проверка индикаторов для бота {bot_name}")
        signals = []
        indicators = await sync_to_async(lambda: list(self.bot.indicators.all()))()

        trading_pair_raw = await sync_to_async(lambda: self.bot.trading_pair)()
        trading_pair = f"{trading_pair_raw[:-4]}/{trading_pair_raw[-4:]}:USDT"

        for indicator in indicators:
            indicator_type = await sync_to_async(lambda: indicator.indicator_type)()
            timeframe = await sync_to_async(lambda: indicator.timeframe)()
            parameters = await sync_to_async(lambda: indicator.parameters)()
            
            df = await self.get_kline_data(trading_pair, timeframe)
            if df is None:
                logger.warning(f"Не удалось получить данные для индикатора {indicator_type}")
                return False

            try:
                if indicator_type == 'RSI':
                    rsi = RSIIndicator(close=df['close'], window=14).rsi()
                    latest_rsi = rsi.iloc[-1]
                    condition = parameters['condition']
                    value = parameters['value']
                    
                    if condition == 'gt' and latest_rsi > value:
                        signals.append(True)
                    elif condition == 'gte' and latest_rsi >= value:
                        signals.append(True)
                    elif condition == 'lt' and latest_rsi < value:
                        signals.append(True)
                    elif condition == 'lte' and latest_rsi <= value:
                        signals.append(True)
                    else:
                        signals.append(False)
                    logger.debug(f"RSI: {latest_rsi}, Условие: {condition} {value}, Сигнал: {signals[-1]}")

                elif indicator_type == 'CCI':
                    cci = CCIIndicator(high=df['high'], low=df['low'], close=df['close'], window=20).cci()
                    latest_cci = cci.iloc[-1]
                    condition = parameters['condition']
                    value = parameters['value']
                    
                    if condition == 'gt' and latest_cci > value:
                        signals.append(True)
                    elif condition == 'gte' and latest_cci >= value:
                        signals.append(True)
                    elif condition == 'lt' and latest_cci < value:
                        signals.append(True)
                    elif condition == 'lte' and latest_cci <= value:
                        signals.append(True)
                    else:
                        signals.append(False)
                    logger.debug(f"CCI: {latest_cci}, Условие: {condition} {value}, Сигнал: {signals[-1]}")

            except Exception as e:
                logger.error(f"Ошибка при расчете индикатора {indicator_type}: {e}")
                signals.append(False)

        result = all(signals)
        logger.info(f"Проверка индикаторов для бота {bot_name}: {'Сигнал получен' if result else 'Сигнал не получен'}")
        return result

    # отслеживание неисполненных лимитных ордеров
    async def check_limit_fills(self, current_price: float):
        """Проверка исполнения лимитных ордеров."""
        bot_name = await sync_to_async(lambda: self.bot.name)()
        logger.info(f"Проверка лимитных ордеров для бота {bot_name} при цене {current_price}")

        # Получаем все неисполненные лимитные сделки
        deals = await sync_to_async(
            lambda: list(Deal.objects.filter(bot=self.bot, is_filled=False, is_active=False))
        )()
        if not deals:
            logger.info(f"Нет ожидающих лимитных сделок для бота {bot_name}")
            return

        strategy = await sync_to_async(lambda: self.bot.strategy)()

        for deal in deals:
            limit_price = float(deal.entry_price)

            if (strategy and current_price <= limit_price) or (not strategy and current_price >= limit_price):
                logger.info(f"Лимитный ордер {deal.order_id} исполнен по цене {current_price}")
                deal.is_filled = True
                deal.is_active = True
                deal.entry_price = limit_price  # уже есть
                await sync_to_async(deal.save)()





    async def place_orders(self):
        """Размещение рыночного и лимитных ордеров."""
        bot_name = await sync_to_async(lambda: self.bot.name)()
        logger.info(f"Размещение ордеров для бота {bot_name}")
        try:
            if not await self.check_time_sync():
                logger.error("Не удалось разместить ордера из-за ошибки синхронизации времени")
                return False

            trading_pair_raw = await sync_to_async(lambda: self.bot.trading_pair)()
            trading_pair = f"{trading_pair_raw[:-4]}/{trading_pair_raw[-4:]}:USDT"
            
            deposit = await sync_to_async(lambda: self.bot.deposit)()
            grid_orders_count = await sync_to_async(lambda: self.bot.grid_orders_count)()
            strategy = await sync_to_async(lambda: self.bot.strategy)()
            bot_leverage = await sync_to_async(lambda: self.bot.bot_leverage)()
            take_profit_percent = float(await sync_to_async(lambda: self.bot.take_profit_percent)())
            stop_loss_percent_raw = await sync_to_async(lambda: self.bot.stop_loss_percent)()
            stop_loss_percent = float(stop_loss_percent_raw) if stop_loss_percent_raw is not None else None
            grid_overlap_percent = await sync_to_async(lambda: self.bot.grid_overlap_percent)()

            specs = await self.get_symbol_specs(trading_pair)
            if not specs:
                logger.error(f"Не удалось получить спецификации для {trading_pair}")
                return False
            qty_step = specs['qty_step']
            min_order_qty = specs['min_order_qty']
            max_order_qty = specs['max_order_qty']
            min_notional = specs['min_notional']

            ticker = await self.client.fetch_ticker(trading_pair)
            current_price = float(ticker['last'])
            logger.info(f"Текущая цена {trading_pair}: {current_price}")

            min_qty_for_notional = min_notional / current_price
            order_qty = (deposit / grid_orders_count * bot_leverage) / current_price
            order_qty = max(min_qty_for_notional, order_qty)
            order_qty = math.floor(order_qty / qty_step * 1000000) * qty_step / 1000000 # костыли чтобы нормально работало округление
            

            if order_qty < min_order_qty:
                logger.error(f"Рассчитанное количество {order_qty} меньше минимального объема {min_order_qty} для {trading_pair}")
                if not self.notified:
                    await sync_to_async(self.notify_admin)(f"рассчитанное количество {order_qty} меньше минимального объема {min_order_qty} для {trading_pair}")
                return False
            
            if order_qty > max_order_qty:
                logger.error(f"Рассчитанное количество {order_qty} превышает максимальный объем {max_order_qty} для {trading_pair}")
                if not self.notified:
                    await sync_to_async(self.notify_admin)(
                        f"Рассчитанное количество {order_qty} превышает максимальный объем {max_order_qty} для {trading_pair} в боте {self.bot_id}"
                    )
                    self.notified = True
                return False

            order_value = order_qty * current_price
            if order_value < min_notional:
                logger.error(f"Стоимость ордера {order_value} USDT меньше минимальной {min_notional} USDT для {trading_pair}")
                if not self.notified:
                    await sync_to_async(self.notify_admin)(
                        f"Стоимость ордера {order_value} USDT меньше минимальной {min_notional} USDT для {trading_pair} в боте {self.bot_id}"
                    )
                    self.notified = True
                return False

            logger.info(f"Рассчитанное количество для ордера: {order_qty} (шаг: {qty_step}, минимальный объем: {min_order_qty}, минимальная стоимость: {min_notional} USDT)")

            side = "buy" if strategy else "sell"
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Установка плеча (для фьючерсов, если поддерживается)
                    try:
                        await self.client.set_leverage(bot_leverage, symbol=trading_pair)
                    except ccxt.BaseError as e:
                        logger.warning(f"Ошибка установки плеча для {trading_pair}: {e}. Продолжаем без установки.")
                    market_order = await self.client.create_order(
                        symbol=trading_pair,
                        type='market',
                        side=side,
                        amount=order_qty,
                    )
                    order_id = market_order['id']
                    break
                except ccxt.InvalidOrder as e:
                    logger.warning(f"Ошибка количества (попытка {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                except ccxt.NetworkError as e:
                    logger.warning(f"Ошибка сети (попытка {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                except Exception as e:
                    logger.error(f"Ошибка при размещении рыночного ордера: {e}")
                    raise e
            else:
                logger.error(f"Не удалось разместить рыночный ордер после {max_retries} попыток")
                if not self.notified:
                    await sync_to_async(self.notify_admin)(f"Не удалось разместить рыночный ордер для бота {self.bot_id} после {max_retries} попыток")
                    self.notified = True
                return False
            
            # начало обработки лимитных ордеров
            order_info = await self.safe_fetch_order(order_id, trading_pair)
            # получение данных по комисии биржы
            exchange_commission = float(order_info.get('fee', {}).get('cost', 0.0))


            if stop_loss_percent is not None:
                if strategy:
                    stop_loss_price=current_price * (1 - stop_loss_percent / 100)
                else:
                    stop_loss_price=current_price * (1 + stop_loss_percent / 100)
            else:
                stop_loss_price=None

            deal = await sync_to_async(Deal.objects.create)(
                bot=self.bot,
                entry_price=current_price,
                take_profit_price=current_price * (1 + take_profit_percent / 100) if strategy else current_price * (1 - take_profit_percent / 100),
                stop_loss_price=stop_loss_price,
                is_active=True,
                exchange_commission=exchange_commission,
                service_commission=0.0, # нужно будет потом исправить
                volume=order_qty,
                pnl=0.0,
                trading_pair=trading_pair,
                order_id=order_id
            )
            logger.info(f"Рыночный ордер размещен: {order_id}, объем: {order_qty}")



            # сообщение на почту админа (не проверенный код)
            indicators_data = {}
            indicators = await sync_to_async(lambda: list(self.bot.indicators.all()))()
            for indicator in indicators:
                ind_type = await sync_to_async(lambda: indicator.indicator_type)()
                if ind_type == "RSI":
                    df = await self.get_kline_data(trading_pair, await sync_to_async(lambda: indicator.timeframe)())
                    rsi = RSIIndicator(close=df['close'], window=14).rsi()
                    indicators_data["RSI"] = rsi.iloc[-1]
                elif ind_type == "CCI":
                    df = await self.get_kline_data(trading_pair, await sync_to_async(lambda: indicator.timeframe)())
                    cci = CCIIndicator(high=df['high'], low=df['low'], close=df['close'], window=20).cci()
                    indicators_data["CCI"] = cci.iloc[-1]

            await self.send_trade_notification("entry", deal, indicators_data)


            price_step = current_price * (grid_overlap_percent / 100) / (grid_orders_count - 1)
            for i in range(1, grid_orders_count):
                limit_price = current_price - price_step * i if strategy else current_price + price_step * i
                for attempt in range(max_retries):
                    try:
                        limit_order = await self.client.create_order(
                            symbol=trading_pair,
                            type='limit',
                            side=side,
                            amount=order_qty,
                            price=round(limit_price, 6)
                        )
                        logger.info(f"разместил {i} лимитный на {order_qty} ")
                        logger.info(f"осталось для следующих ордеров: {deposit-i*order_qty*current_price}")
                        break
                    except ccxt.InvalidOrder as e:
                        logger.warning(f"Ошибка количества при размещении лимитного ордера (попытка {attempt + 1}/{max_retries}): {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                    except ccxt.NetworkError as e:
                        logger.warning(f"Ошибка сети при размещении лимитного ордера (попытка {attempt + 1}/{max_retries}): {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                    except Exception as e:
                        logger.error(f"Ошибка при размещении лимитного ордера: {e}")
                        logger.info(f"не смог разместить {i} лимитный ордер на {order_qty} ")
                        raise e
                else:
                    logger.error(f"Не удалось разместить лимитный ордер после {max_retries} попыток")
                    if not self.notified:
                        await sync_to_async(self.notify_admin)(f"Не удалось разместить лимитный ордер для бота {self.bot_id} после {max_retries} попыток")
                        self.notified = True
                    continue
                

                if stop_loss_percent is not None:
                    if strategy:
                        stop_loss_price=limit_price * (1 - stop_loss_percent / 100)
                    else:
                        stop_loss_price=limit_price * (1 + stop_loss_percent / 100)
                else:
                    stop_loss_price=None

                await sync_to_async(Deal.objects.create)(
                    bot=self.bot,
                    entry_price=limit_price,
                    take_profit_price=limit_price * (1 + take_profit_percent / 100) if strategy else limit_price * (1 - take_profit_percent / 100),
                    stop_loss_price=stop_loss_price,
                    exchange_commission=0.0,
                    service_commission=0.0,
                    volume=order_qty,
                    pnl=0.0,
                    trading_pair=trading_pair,
                    order_id=limit_order['id'],
                    is_active=False,       #  Не активна пока не исполнена
                    is_filled=False        #  Еще не исполнен
                )


                logger.info(f"Лимитный ордер размещен: {limit_order['id']}, цена: {limit_price}")

            return True

        except Exception as e:
            logger.error(f"Ошибка при размещении ордеров для бота {bot_name}: {e}", exc_info=True)
            if not self.notified:
                await sync_to_async(self.notify_admin)(f"Ошибка при размещении ордеров для бота {self.bot_id}: {str(e)}")
                self.notified = True
            return False

    async def monitor_orders(self):
        """Отслеживание TP/SL и закрытие ордеров."""
        bot_name = await sync_to_async(lambda: self.bot.name)()
        logger.info(f"начали мониторить бота {bot_name}")
        while self.running:
            try:
                self.bot = await sync_to_async(Bot.objects.get)(id=self.bot_id)
                is_active = await sync_to_async(lambda: self.bot.is_active)()

                trading_pair_raw = await sync_to_async(lambda: self.bot.trading_pair)()
                trading_pair = f"{trading_pair_raw[:-4]}/{trading_pair_raw[-4:]}:USDT"

                logger.info(f"получили данные из бд")

                if not is_active:
                    self.running = False
                    await self.client.cancel_orders(trading_pair)
                    logger.info(f"Бот {bot_name} остановлен")
                    return

                ticker = await self.client.fetch_ticker(trading_pair)
                current_price = float(ticker['last'])
                # вызов метода для проверки исполнения лимитных ордеров
                await self.check_limit_fills(current_price)

                
                deals = await sync_to_async(lambda: list(Deal.objects.filter(bot=self.bot, is_active=True)))()
                logger.info(f"получили сделки из бд, количество {len(deals)}")
                if not deals:
                    logger.info(f"Нет активных сделок для бота {bot_name}")
                    return

                strategy = await sync_to_async(lambda: self.bot.strategy)()
                avg_tp = sum(float(deal.take_profit_price) for deal in deals) / len(deals)
                avg_sl = (
                    sum(float(deal.stop_loss_price) for deal in deals if deal.stop_loss_price) / len([deal for deal in deals if deal.stop_loss_price])
                    if any(deal.stop_loss_price for deal in deals)
                    else None
                )

                logging.info('проверка текущей цены для выхода из сделки')
                close_position = False
                if strategy:
                    if current_price >= avg_tp or (avg_sl and current_price <= avg_sl):
                        logging.info('выход по tp или sl (long)')
                        close_position = True
                else:
                    if current_price <= avg_tp or (avg_sl and current_price >= avg_sl):
                        logging.info('выход по tp или sl (short)')
                        close_position = True

                if close_position:
                    logger.info(f"отменяем все незакрытые ордера")
                    await self.client.cancel_all_orders(symbol=trading_pair)

                    # Новый рыночный ордер для выхода из позиции
                    total_qty = sum(float(deal.volume) for deal in deals)
                    side = "sell" if strategy else "buy"  # Противоположная сторона
                    logger.info(f"создаем ордер в противоположном направлении для закрытия ордеров. их суммарный объем {total_qty}")
                    try:
                        close_order = await self.client.create_order(
                            symbol=trading_pair,
                            type='market',
                            side=side,
                            amount=total_qty
                        )
                        logger.info(f"Создан рыночный ордер на закрытие позиции: {close_order['id']}, объем: {total_qty}")
                        # Подождем чуть-чуть, чтобы биржа успела обработать
                        await asyncio.sleep(2)


                        # Проверяем, действительно ли позиция закрыта
                        position = await self.client.fetch_position(trading_pair)
                        position_size = abs(float(position['contracts'] if 'contracts' in position else position['size']))
                        
                        if position_size > 0:
                            logger.warning(f"Позиция по {trading_pair} не закрыта! Остаток: {position_size}")
                            # Тут можно повторить попытку или отправить уведомление
                            return  # Прерываем, чтобы не записывать фиктивный PnL



                    except Exception as e:
                        logger.error(f"Ошибка при попытке закрыть позицию рыночным ордером: {e}")
                        return  # Без закрытия позиции дальше смысла нет



                    for deal in deals:
                        # тут беда, мы не можем получить ордера, которые отменили ранее
                        order_info = await self.safe_fetch_order(deal.order_id, trading_pair)
                        logger.info(f"выполнелась невозможная операция. вывод {order_info}")

                        if order_info['status'] != 'closed' or not order_info['filled']:
                            continue

                        exit_price = current_price
                        entry_price = float(deal.entry_price)
                        qty = float(deal.volume)
                        pnl = (exit_price - entry_price) * qty if strategy else (entry_price - exit_price) * qty
                        deal.pnl = pnl
                        
                        deal.service_commission = max(0, pnl * 0.1)
                        deal.is_active = False
                        deal.is_filled = True


                        # уведомление админу
                        deal.exit_price = current_price 
                        await sync_to_async(deal.save)()
                        await self.send_trade_notification("exit", deal)


                        if deal.service_commission > 0:
                            user = await sync_to_async(lambda: self.bot.user)()

                            logger.info(f"сейчас будем применять сомнительныю функцию Decimal")

                            user.balance -= Decimal(str(deal.service_commission))

                            logger.info(f"применили Decimal, получили {user.balance}")

                            await sync_to_async(user.save)()
                            logger.info(f"Списана комиссия сервиса {deal.service_commission} с баланса пользователя {user.email}")

                    logger.info(f"Позиции закрыты для бота {bot_name}")
                    return

                await asyncio.sleep(10)
            except Bot.DoesNotExist:
                error_msg = "Бот не найден в базе данных"
                logger.error(f"Бот с ID {self.bot_id} не найден")
                await self.save_error(error_msg, "not_found")
                if not self.notified:
                    await sync_to_async(self.notify_admin)(f"Ошибка: Бот с ID {self.bot_id} не найден")
                    self.notified = True
                self.running = False
                return
            except Exception as e:
                error_msg = self.translate_error(str(e))
                logger.error(f"Ошибка при мониторинге ордеров для бота {bot_name}: {e}", exc_info=True)
                await self.save_error(error_msg, "monitoring")
                if not self.notified:
                    await sync_to_async(self.notify_admin)(f"Ошибка при мониторинге ордеров для бота {self.bot_id}: {str(e)}")
                    self.notified = True
                await asyncio.sleep(10)

    async def run(self):
        """Основной цикл бота."""
        logger.info(f"начало run {self.bot_id}")
        await self.initialize()
        logger.info(f"инициализация выполнена")
        if not self.running:
            logger.info(f"Бот {self.bot_id} не запущен из-за ошибки инициализации")
            return

        try:
            while self.running:
                self.bot = await sync_to_async(Bot.objects.get)(id=self.bot_id)
                is_active = await sync_to_async(lambda: self.bot.is_active)()
                bot_name = await sync_to_async(lambda: self.bot.name)()
                trading_pair = await sync_to_async(lambda: self.bot.trading_pair)()

                # Проверяем баланс пользователя
                user = await sync_to_async(lambda: self.bot.user)()
                balance = await sync_to_async(lambda: user.balance)()

                if balance<=0:
                    logger.info("Недостаточно баланса! Бот остановлен.")
                    self.bot.is_active = False
                    self.running=False
                    await sync_to_async(self.bot.save)()
                    break

                logger.info(f"получены данные из бд {is_active}, {bot_name}, {trading_pair}")

                if not is_active:
                    self.running = False
                    logger.info(f"Бот {bot_name} остановлен")
                    return

                if await self.check_indicators():
                    logger.info(f"инидикаторы проверены")
                    orders = await self.client.fetch_open_orders(trading_pair)
                    logger.info(f"все ордера получены. количество: {len(orders)}")
                    if len(orders)>0:
                        logger.info(f"все ордера уже размещены, идем мониторить")
                        await self.monitor_orders()
                
                    else:
                        success = await self.place_orders()
                        if success:
                            logger.info(f"разместили ордера, идем мониторить")
                            await self.monitor_orders()
                        else:
                            logger.info(f"Мониторинг ордеров пропущен для бота {bot_name} из-за ошибки размещения ордеров")

                await asyncio.sleep(10)
        except Bot.DoesNotExist:
            error_msg = "Бот не найден в базе данных"
            logger.error(f"Бот с ID {self.bot_id} не найден")
            await self.save_error(error_msg, "not_found")
            if not self.notified:
                await sync_to_async(self.notify_admin)(f"Ошибка: Бот с ID {self.bot_id} не найден")
                self.notified = True
            self.running = False
        except Exception as e:
            error_msg = self.translate_error(str(e))
            logger.error(f"Ошибка в цикле бота {self.bot_id}: {e}", exc_info=True)
            await self.save_error(error_msg, "runtime")
            if not self.notified:
                await sync_to_async(self.notify_admin)(f"Ошибка в цикле бота {self.bot_id}: {str(e)}")
                self.notified = True
            await asyncio.sleep(10)
        finally:
            if self.client:
                await self.client.close()

    async def save_error(self, error_message, error_type="general"):
        """Сохранение ошибки в базу данных."""
        try:
            from django.utils import timezone
            await sync_to_async(lambda: setattr(self.bot, 'last_error', error_message))()
            await sync_to_async(lambda: setattr(self.bot, 'error_timestamp', timezone.now()))()
            await sync_to_async(self.bot.save)()
            logger.info(f"Ошибка сохранена в БД для бота {self.bot_id}: {error_message}")
        except Exception as e:
            logger.error(f"Не удалось сохранить ошибку в БД: {e}")

    def translate_error(self, error_message):
        """Перевод технических ошибок в понятные пользователю сообщения."""
        error_lower = error_message.lower()
        
        # Ошибки подключения к бирже
        if 'timeout' in error_lower or 'connection' in error_lower:
            return "Проблема с подключением к бирже. Проверьте интернет-соединение."
        elif 'rate limit' in error_lower or 'too many requests' in error_lower:
            return "Слишком много запросов к бирже. Попробуйте позже."
        elif 'invalid api' in error_lower or 'api key' in error_lower:
            return "Неверные API ключи. Проверьте настройки аккаунта."
        elif 'insufficient balance' in error_lower or 'balance' in error_lower:
            return "Недостаточно средств на балансе для выполнения операции."
        elif 'symbol not found' in error_lower or 'trading pair' in error_lower:
            return "Торговая пара не найдена на бирже."
        elif 'order not found' in error_lower:
            return "Ордер не найден на бирже."
        elif 'market closed' in error_lower:
            return "Рынок закрыт для торговли."
        elif 'maintenance' in error_lower:
            return "Биржа находится на техническом обслуживании."
        elif 'network' in error_lower:
            return "Проблема с сетью. Попробуйте позже."
        else:
            return "Произошла ошибка в работе бота. Попробуйте перезапустить."

    # безопасное получение данных по ордерам
    async def safe_fetch_order(self, order_id, symbol):
        try:
            # Пробуем современный метод (snake_case)
            return await self.client.fetchOpenOrder(order_id, symbol)
        except (AttributeError, ccxt.NotSupported):
            # Если не поддерживается — пробуем старый (camelCase)
            return await self.client.fetch_order(order_id, symbol)
        except Exception as e:
            logger.error(f"Ошибка при получении ордера {order_id}: {e}")
            raise

async def start_bot(bot_id):
    """Запуск бота."""
    logger.info(f"Запуск бота с ID: {bot_id}")
    bot = TradingBot(bot_id)
    await bot.run()