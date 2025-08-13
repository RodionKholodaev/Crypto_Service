import os
from celery import Celery
import logging
from celery.signals import worker_ready
from celery.schedules import crontab
# устанавливаем переменную окружения (говорим celery где брать настройки django)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cryptoservice.settings')
# создаем объект класса celery  с именем cryptoservice
app = Celery(
    'cryptoservice',
    broker_connection_retry_on_startup=True,
    )
# согружаем настройки для celery из settings с префиксом CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')
# устанавливаем автоподгрузку задач (celery ищет задачит в tasks.py во всех приложениях)
app.autodiscover_tasks()

# логирование для дебага
# создание логера с именем текущего модуля (__name__=celery)
logger = logging.getLogger(__name__)


@worker_ready.connect
def auto_start_bots(**kwargs):
    """Автозапуск активных ботов при старте воркера"""
    from bots.models import Bot
    from bots.tasks import run_trading_bot
    
    for bot in Bot.objects.filter(is_active=True):
        try:
            run_trading_bot.apply_async(
                args=[bot.id], 
                task_id=f"run_trading_bot_{bot.id}",
                queue='trading'  # Явно указываем очередь
            )
            logger.info(f"Автозапущен бот {bot.id}")
        except Exception as e:
            logger.error(f"Ошибка автозапуска бота {bot.id}: {e}")

# @app.task(bind=True) превращаем задачу в ассихронную задачу celery
@app.task(bind=True)
def debug_task(self):
    logger.info('Celery работает!')


# этот файл нужен для интеграции celery в django
# возможно при отправке на сервер можно будет сделать иначе
app.conf.beat_schedule = {
    'clean_old_transactions': {
        'task': 'bots.tasks.clean_old_transactions',
        'schedule': crontab(minute='*/30'),  # Каждые 30 минут
    },
}