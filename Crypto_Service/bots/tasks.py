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
        ignore_result=True,  # Не сохранять результат
        queue="default",    # Очередь без бэкенда
        )
def run_trading_bot(bot_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop) 
    try:
        loop.run_until_complete(start_bot(bot_id))
    finally:
        loop.close()



@shared_task(
    name='check_payments',
    ignore_result=True,
    queue='payments'
)
def check_payments():
    check_trc20_payments()
    check_erc20_payments()

def check_trc20_payments():
    url = f'https://api.tronscan.org/api/account/token_transfer'
    for user in User.objects.filter(trc20_address__isnull=False):
        params = {
            'address': user.trc20_address,
            'token': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
            'limit': 100,
            'start': 0,
            'sort': '-timestamp',
            'apikey': settings.TRONSCAN_API_KEY
        }
        
        try:
            response = requests.get(url, params=params).json()
            for tx in response.get('token_transfers', []):
                # Проверяем в БД через exists() вместо tx.get('processed')
                if tx['confirmed'] and not CryptoTransaction.objects.filter(
                    tx_hash=tx['transaction_id'],
                    network='TRC20'
                ).exists():
                    amount = float(tx['quant']) / 10**6
                    user.balance += amount
                    user.save()
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
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": "0xdac17f958d2ee523a2206206994597c13d831ec7",
            "address": user.erc20_address,
            "sort": "desc",
            "apikey": settings.ETHERSCAN_API_KEY,
        }
        try:
            response = requests.get(url, params=params).json()
            for tx in response.get('result', []):
                if not CryptoTransaction.objects.filter(
                    tx_hash=tx['hash'],
                    network='ERC20'
                ).exists():
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
    from django.utils import timezone
    from datetime import timedelta
    from .models import CryptoTransaction

    CryptoTransaction.objects.filter(
        timestamp__lt=timezone.now() - timedelta(minutes=30)
    ).delete()


# в этом файле описываются задачи, они определяют что нужно выполнить
# после сериализации задача превращается в сообщение, которое храниться в redis и ждет выполнения вокером
