
#работа с путями к файлам и папкам
from pathlib import Path
#загружает переменные из файла env
from dotenv import load_dotenv
#позволяет работать с ос (например работать с переменными окружения)
import os

#загружает переменные из файла env
load_dotenv()


# базовый путь проекта, указывает корневую папку проекта (нужно чтобы правильно находить другие файлы)
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

#список доменов с которых можно обращаться к проекту
#домен - уникальное имя сайта по которому он доступен в интернете
ALLOWED_HOSTS = ['localhost','127.0.0.1','web']


# список всех приложений + стандартные
INSTALLED_APPS = [
    'analytics',
    'bots',
    'main',
    'users',
    'encrypted_model_fields', # для шифрования
    'django.contrib.admin', # создает автоматический интерфейс для управленя данными
    'django.contrib.auth', # добавляет систему входа/регистрации, проверку паролей
    'django.contrib.contenttypes', # позволяет связывать разные таблицы в бд между собой
    'django.contrib.sessions', # позволяет запоминать пользователя и его действия на страницах
    'django.contrib.messages',  # позволяет показывать одноразовые уведомления пользователю
    'django.contrib.staticfiles', # управляет CSS, JavaScript, изображениями и т.д. (нужно чтобы правильно все это подгружать)
]

# widdleware - промежуточное по, фильтры через которые проходят все запросы от пользователя и ответы от сайта
# каждый widdleware выполняет отдельную задачу пока запрос не дошел до пользователя
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', # защита от уграз (если сайт не использует https, заставляет браузер использовать безопасное соединение)
    'django.contrib.sessions.middleware.SessionMiddleware', # запоминает пользователя между запросами
    'django.middleware.common.CommonMiddleware', # общие настройки (например, уберает лишние слеши в URL)
    'django.middleware.csrf.CsrfViewMiddleware', # проверяет что форма отправлена с этого сайте, а не с фальшивой страницы
    'django.contrib.auth.middleware.AuthenticationMiddleware', # связывает пользователя с запросом (позволяет использовать request.user)
    'django.contrib.messages.middleware.MessageMiddleware', # позволяет выводить одноразовые сообщения
    'django.middleware.clickjacking.XFrameOptionsMiddleware', # запрещает другим сайтам встраивать этот сайт в себя (защита от кражи данных)
]

# указывает главные файл с url адресами проекта
ROOT_URLCONF = 'cryptoservice.urls'

# настройки шаблонов (где искать html файлы)
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates', # движок шаблонов django ({% if %})
        'DIRS': [os.path.join(BASE_DIR, 'templates')], # где искать html шаблоны
        'APP_DIRS': True, # разрешает искать шаблоны внутри приложений
        # дополнительные настройки для шаблонов
        # контекстные процессоры  - специальные функции, которые добавляют данные во все шаблоны автоматически
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# где находится "входная точка" (как дверь) для веб-сервера (например, Nginx или Apache)
# WSGI (Web Server Gateway Interface) - переводчик между django приложением и веб-сервером (без него сервер не поймет, что делать с кодом)

# cryptoservice.wsgi.application — это как "адрес главного офиса" твоего проекта.
# cryptoservice — имя твоего проекта (папка, где лежит settings.py).
# wsgi.py — файл, который создаётся автоматически и содержит настройки WSGI.

# application — это функция внутри wsgi.py, которая запускает Django.
WSGI_APPLICATION = 'cryptoservice.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql', # тип базы данных
        'NAME': 'mydb',
        'USER': 'admin',
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': 'db',  # Имя сервиса в docker-compose.yml
        'PORT': '5432',
    }
}




# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

# правила для проверки паролей (минимальная длина, запрет простых паролей, ...)

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'ru'

# в каком часовом поясе хранить и обрабатывать даты в бд
TIME_ZONE = 'UTC'
# разрешиет конвертацию времени между часовым поясом проекта и пользователя
USE_I18N = True
# включает переводы на указанный язык
USE_TZ = True



# настройки для CSS, JS и изображений
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# настройки для загружаемых файлов
MEDIA_URL = '/media/' 
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')



DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField' # заставляет автоматически создавать номер для записи в бд

AUTH_USER_MODEL = 'users.User' # говорит использовать кастомную модель пользователя, а не стандартную

LOGIN_REDIRECT_URL = 'home' # после входа на сайт перенаправлять на home

# список способов, которыми django проверяет логин и пароль
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend', # стандартный
]

FIELD_ENCRYPTION_KEY=os.getenv('FIELD_ENCRYPTION_KEY') # ключ для шифрования

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # или ваш SMTP-сервер
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# Добавить настройки Celery
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Добавить настройки email админа
ADMIN_EMAIL = 'kholodaev10e@mail.ru'


