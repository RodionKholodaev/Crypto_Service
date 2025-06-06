from celery import shared_task
from bots.bot_logic import start_bot
import asyncio

# создает задачу для celery
# shared_task дает использовать функцию run_trading_bot как celery task
@shared_task(name="run_trading_bot_{bot_id}")
def run_trading_bot(bot_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_bot(bot_id))
    finally:
        loop.close()