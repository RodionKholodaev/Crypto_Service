from celery import shared_task
from bots.bot_logic_ccxt import start_bot
import asyncio
import ccxt
from django.db import transaction
from .models import PendingPayment, ProcessedTransaction
import requests
import logging
from datetime import datetime, timedelta



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



# задачи для обработки пополнения баланса

logger = logging.getLogger(__name__)
# Конфигурация API (вынесите в settings.py) (необязательно)
TRON_API_KEY = '1865581b-def9-42ef-93e4-856c2863fd51'
ETHERSCAN_API_KEY = 'C5DG7FMGGKXTAZUAIY6AGRM8YQW4MNG4CX'
TRON_WALLET = 'TNHCwXJiyUQBz6HhKP2Jg6Ya9rWma6Ucsp'
ETH_WALLET = '0xf828889B764407B291b7Ce35Cf84ab216eae7622'

# проверяет новые транзакции и обрабатывает первую в очереди
@shared_task(bind=True, queue='payments')
def check_payments(self):

    # получаем первого пользователя в очереди
    pending_payment = PendingPayment.objects.filter(is_processed=False).first()
    if not pending_payment:
        logger.info("Нет пользователей в очереди.")
        return

    # ищем новые транзакции за последние 5 минут
    try:
        latest_tx = _get_latest_transaction()
        if not latest_tx:
            logger.info("Нет новых транзакций.")
            return

        # проверяем, не обработана ли транзакция ранее
        if ProcessedTransaction.objects.filter(tx_hash=latest_tx['tx_hash']).exists():
            logger.warning(f"Транзакция {latest_tx['tx_hash']} уже обработана.")
            return

        # зачисляем средства пользователю
        # with transaction.atomic(): позволяет выполнить запись в бд как единое действие 
        # (чтобы не было ошибое когда что-то сохранилось, а что-то нет)
        with transaction.atomic():
            pending_payment.user.balance += latest_tx['amount']
            pending_payment.user.save()
            pending_payment.is_processed = True
            pending_payment.save()
            ProcessedTransaction.objects.create(
                tx_hash=latest_tx['tx_hash'],
                blockchain=latest_tx['blockchain']
            )
            logger.info(f"Зачислено {latest_tx['amount']} пользователю {pending_payment.user.id}")

    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)

# возвращает последнюю неподтвержденную транзакцию (TRC20 или ERC20)
def _get_latest_transaction():

    # проверяем TRC20 (Tron)
    tron_tx = _get_tron_transaction()
    if tron_tx:
        return tron_tx

    # проверяем ERC20 (Ethereum)
    eth_tx = _get_erc20_transaction()
    if eth_tx:
        return eth_tx

    return None

# проверяет последнюю транзакцию USDT-TRC20
#(работает)
def _get_tron_transaction():

    url = f"https://api.trongrid.io/v1/accounts/{TRON_WALLET}/transactions/trc20"
    params = {
        "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",  # USDT-TRC20
        "only_confirmed": True,
        "limit": 1,
    }
    headers = {"Authorization": f"Bearer {TRON_API_KEY}"}

    try:
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        if not data.get('data'):
            return None

        tx = data['data'][0]
        tx_time = datetime.fromtimestamp(tx['block_timestamp'] / 1000)
        if tx_time < datetime.now() - timedelta(minutes=5):
            return None

        return {
            'tx_hash': tx['transaction_id'],
            'amount': float(tx['value']) / 10**6,  # USDT (6 decimals)
            'blockchain': 'TRC20',
        }
    except Exception as e:
        logger.error(f"Ошибка Tron API: {e}")
        return None

# проверяет последнюю транзакцию USDT-ERC20
#(работает_скорее_всего)
def _get_erc20_transaction():

    url = "https://api.etherscan.io/api"
    params = {
        "module": "account",
        "action": "tokentx",
        "contractaddress": "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT-ERC20
        "address": ETH_WALLET,
        "page": 1,
        "offset": 1,
        "sort": "desc",
        "apikey": ETHERSCAN_API_KEY,
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        if not data.get('result'):
            return None

        tx = data['result'][0]
        tx_time = datetime.fromtimestamp(int(tx['timeStamp']))
        if tx_time < datetime.now() - timedelta(minutes=5):
            return None

        return {
            'tx_hash': tx['hash'],
            'amount': float(tx['value']) / 10**6,  # USDT (6 decimals)
            'blockchain': 'ERC20',
        }
    except Exception as e:
        logger.error(f"Ошибка Etherscan API: {e}")
        return None


# в этом файле описываются задачи, они определяют что нужно выполнить
# после сериализации задача превращается в сообщение, которое храниться в redis и ждет выполнения вокером
