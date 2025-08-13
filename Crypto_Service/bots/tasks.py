from celery import shared_task
from bots.bot_logic_ccxt import start_bot
import asyncio
import ccxt
from django.db import transaction

import requests
import logging
from datetime import datetime, timedelta

from django.conf import settings
from users.models import User
from django.utils import timezone
from .models import CryptoTransaction


# создает задачу для celery
# shared_task дает использовать функцию run_trading_bot как celery task
@shared_task(
    name="run_trading_bot_{bot_id}",
    queue="trading",  # Должно соответствовать CELERY_TASK_ROUTES
    bind=True,  # Для доступа к self (task.request и др.)
    autoretry_for=(Exception,),  # Автоповтор при ошибках
    retry_kwargs={'max_retries': 3, 'countdown': 10},
)
def run_trading_bot(self, bot_id):
    from bots.models import Bot
    from django.db import close_old_connections
    
    close_old_connections()
    bot = Bot.objects.filter(id=bot_id).first()
    
    if not bot or not bot.is_active:
        return  # Прекращаем если бот не активен
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_bot(bot_id))
    except Exception as e:
        self.retry(exc=e)  # Повторяем при ошибке
    finally:
        loop.close()
        close_old_connections()



@shared_task(
    name='check_payments',
    ignore_result=True,
    queue='payments'
)
def check_payments():
    check_trc20_payments()
    check_erc20_payments()

def check_trc20_payments():
    # цикл по всем пользователся у которых в бд есть trc20 (по всем)
    url = f'https://api.tronscan.org/api/account/token_transfer'
    for user in User.objects.filter(trc20_address__isnull=False):
        # параметры для запроса
        params = {
            'address': user.trc20_address,
            'token': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
            'limit': 100,
            'start': 0,
            'sort': '-timestamp',
            'apikey': settings.TRONSCAN_API_KEY
        }
        
        try:
            # запрос к api
            response = requests.get(url, params=params).json()
            for tx in response.get('token_transfers', []):
                # Проверяем в БД через exists() вместо tx.get('processed')
                # проверяем на наличие в модели с обработаными транзакциями
                if tx['confirmed'] and not CryptoTransaction.objects.filter(
                    tx_hash=tx['transaction_id'],
                    network='TRC20'
                ).exists():
                    # увеличение баланса и сохранение в бд
                    amount = float(tx['quant']) / 10**6
                    user.balance += amount
                    user.save()
                    # кастомная функция
                    mark_transaction_processed(
                        tx_hash=tx['transaction_id'],
                        network='TRC20',
                        user=user,
                        amount=amount,
                        tx_timestamp=tx['block_ts'] / 1000  # UNIX timestamp в секундах
                    )
        except Exception as e:
            print(f"TRC20 Error: {e}")
    


def check_erc20_payments():
    # эндпоинт для eth
    url = "https://api.etherscan.io/api"
    # проходимся по всем пользователям у которых есть erc20_address
    for user in User.objects.filter(erc20_address__isnull=False):
        # параметры для запроса
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": "0xdac17f958d2ee523a2206206994597c13d831ec7",
            "address": user.erc20_address,
            "sort": "desc",
            "apikey": settings.ETHERSCAN_API_KEY,
        }
        try:
            # запрос
            response = requests.get(url, params=params).json()
            for tx in response.get('result', []):
                # проверка на наличие транзакции в бд
                if not CryptoTransaction.objects.filter(
                    tx_hash=tx['hash'],
                    network='ERC20'
                ).exists():
                    # сохранение данных в бд
                    amount = float(tx['value']) / 10**6
                    user.balance += amount
                    user.save()
                    mark_transaction_processed(
                        tx_hash=tx['hash'],
                        network='ERC20',
                        user=user,
                        amount=amount,
                        tx_timestamp=int(tx['timeStamp'])
                    )
        except Exception as e:
            print(f"ERC20 Error: {e}")



def mark_transaction_processed(tx_hash: str, network: str, user: User, amount: float, tx_timestamp: int):
    """Сохраняет факт обработки транзакции."""
    CryptoTransaction.objects.get_or_create(
        tx_hash=tx_hash,
        network=network,
        defaults={
            'user': user,
            'amount': amount,
            'timestamp': timezone.datetime.fromtimestamp(tx_timestamp, tz=timezone.utc),
        }
    )


# задача для очистки CryptoTransaction
@shared_task(queue='maintenance')
def clean_old_transactions():
    """Удаляет транзакции старше 20 минут."""
    CryptoTransaction.objects.filter(
        timestamp__lt=timezone.now() - timedelta(minutes=30)
    ).delete()


# в этом файле описываются задачи, они определяют что нужно выполнить
# после сериализации задача превращается в сообщение, которое храниться в redis и ждет выполнения вокером
