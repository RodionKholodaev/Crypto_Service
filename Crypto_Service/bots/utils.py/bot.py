# bot_runner.py
import time
import logging
from decimal import Decimal
from django.utils import timezone
from typing import Optional

logger = logging.getLogger(__name__)

class TradingBot:
    """Основной класс торгового бота"""
    
    def __init__(self, bot_model, api):
        self.bot = bot_model
        self.api = api
        self.current_deal = None
        self.check_interval = 10  # секунд
    
    def calculate_position_size(self, current_price: float) -> float:
        """Расчет размера позиции в базовой валюте"""
        deposit_usdt = float(self.bot.deposit)
        leverage = self.bot.bot_leverage
        
        # Размер позиции в USDT
        position_value_usdt = deposit_usdt * leverage
        
        # Конвертируем в количество монет
        position_size = position_value_usdt / current_price
        
        return round(position_size, 3)  # Округляем до 3 знаков
    
    def calculate_tp_sl_prices(self, entry_price: float) -> tuple:
        """Расчет цен Take Profit и Stop Loss"""
        tp_percent = float(self.bot.take_profit_percent) / 100
        sl_percent = float(self.bot.stop_loss_percent) / 100 if self.bot.stop_loss_percent else None
        
        if self.bot.strategy:  # Long
            tp_price = entry_price * (1 + tp_percent)
            sl_price = entry_price * (1 - sl_percent) if sl_percent else None
        else:  # Short
            tp_price = entry_price * (1 - tp_percent)
            sl_price = entry_price * (1 + sl_percent) if sl_percent else None
        
        return round(tp_price, 2), round(sl_price, 2) if sl_price else None
    
    def open_position(self):
        """Открытие позиции"""
        try:
            # Получаем текущую цену
            ticker = self.api.exchange.fetch_ticker(self.bot.trading_pair)
            current_price = ticker['last']
            
            # Рассчитываем параметры
            position_size = self.calculate_position_size(current_price)
            tp_price, sl_price = self.calculate_tp_sl_prices(current_price)
            
            side = 'buy' if self.bot.strategy else 'sell'
            
            # Создаем ордер
            params = {
                'takeProfit': {'triggerPrice': tp_price},
            }
            if sl_price:
                params['stopLoss'] = {'triggerPrice': sl_price}
            
            order = self.api.exchange.create_order(
                symbol=self.bot.trading_pair,
                type='market',
                side=side,
                amount=position_size,
                params=params
            )
            
            # Сохраняем сделку в БД
            self.current_deal = Deal.objects.create(
                bot=self.bot,
                entry_price=current_price,
                position_size=position_size,
                side=side,
                leverage=self.bot.bot_leverage,
                take_profit_price=tp_price,
                stop_loss_price=sl_price,
                exchange_order_id=order['id'],
                status='OPEN'
            )
            
            logger.info(
                f"✅ Позиция открыта: {side} {position_size} {self.bot.trading_pair} "
                f"@ {current_price}, TP: {tp_price}, SL: {sl_price}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка открытия позиции: {e}")
            self.bot.last_error = str(e)
            self.bot.error_timestamp = timezone.now()
            self.bot.save()
            return False
    
    def check_position_closed(self) -> Optional[str]:
        """Проверка закрытия позиции"""
        if not self.current_deal:
            return None
        
        try:
            # Проверяем позицию на бирже
            position = self.api.get_position(self.bot.trading_pair)
            
            if not position or float(position.get('contracts', 0)) == 0:
                # Позиция закрыта - определяем причину
                ticker = self.api.exchange.fetch_ticker(self.bot.trading_pair)
                exit_price = ticker['last']
                
                # Определяем статус по цене выхода
                if self.bot.strategy:  # Long
                    if exit_price >= float(self.current_deal.take_profit_price):
                        status = 'CLOSED_TP'
                    else:
                        status = 'CLOSED_SL'
                else:  # Short
                    if exit_price <= float(self.current_deal.take_profit_price):
                        status = 'CLOSED_TP'
                    else:
                        status = 'CLOSED_SL'
                
                # Обновляем запись в БД
                self.current_deal.exit_price = exit_price
                self.current_deal.exit_time = timezone.now()
                self.current_deal.status = status
                self.current_deal.calculate_profit()
                
                logger.info(
                    f"🏁 Позиция закрыта: {status}, "
                    f"PnL: {self.current_deal.profit_loss} USDT "
                    f"({self.current_deal.profit_loss_percent}%)"
                )
                
                self.current_deal = None
                return status
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка проверки позиции: {e}")
            return None
    
    def run(self):
        """Основной цикл бота"""
        logger.info(f"🚀 Запуск бота '{self.bot.name}'")
        
        try:
            # Установка плеча
            self.api.set_leverage(self.bot.trading_pair, self.bot.bot_leverage)
        except Exception as e:
            logger.error(f"Ошибка установки плеча: {e}")
        
        # Проверяем есть ли открытая сделка в БД
        open_deal = Deal.objects.filter(bot=self.bot, status='OPEN').first()
        if open_deal:
            self.current_deal = open_deal
            logger.info("Найдена открытая позиция")
        
        while self.bot.is_active:
            try:
                self.bot.refresh_from_db()
                
                if not self.bot.is_active:
                    logger.info("Бот остановлен")
                    break
                
                # Если есть открытая позиция - проверяем её закрытие
                if self.current_deal:
                    self.check_position_closed()
                    time.sleep(self.check_interval)
                    continue
                
                # Если позиции нет - проверяем сигналы на вход
                indicators_data = []
                for ind in self.bot.indicators.all():
                    indicators_data.append({
                        'id': ind.id,
                        'indicator_type': ind.indicator_type,
                        'timeframe': ind.timeframe,
                        'period': ind.period,
                        'threshold_value': ind.threshold_value,
                        'cross_direction': ind.cross_direction,
                        'extra_params': ind.extra_params,
                        'last_value': float(ind.last_value) if ind.last_value else None,
                    })
                
                # Проверяем все индикаторы
                if SignalChecker.check_all_indicators(indicators_data, self.api, self.bot.trading_pair):
                    logger.info("🎯 Все индикаторы дали сигнал! Открываем позицию...")
                    self.open_position()
                    
                    # Обновляем last_value для всех индикаторов
                    for ind_data in indicators_data:
                        if '_current_value' in ind_data:
                            Indicator.objects.filter(id=ind_data['id']).update(
                                last_value=ind_data['_current_value']
                            )
                else:
                    # Обновляем last_value даже если сигнала нет
                    for ind_data in indicators_data:
                        if '_current_value' in ind_data:
                            Indicator.objects.filter(id=ind_data['id']).update(
                                last_value=ind_data['_current_value']
                            )
                
                # Задержка перед следующей проверкой
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в работе бота: {e}")
                self.bot.last_error = str(e)
                self.bot.error_timestamp = timezone.now()
                self.bot.save()
                time.sleep(60)  # При ошибке ждем минуту
        
        logger.info(f"⏹️ Бот '{self.bot.name}' остановлен")
