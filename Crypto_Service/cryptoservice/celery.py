import os
from celery import Celery
import logging
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
# @app.task(bind=True) превращаем задачу в ассихронную задачу celery
@app.task(bind=True)
def debug_task(self):
    logger.info('Celery работает!')


# этот файл нужен для интеграции celery в django


