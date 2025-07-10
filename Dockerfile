# Базовый образ Python
FROM python:3.10-slim

# Оптимизация работы Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Установка часового пояса UTC
ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Установка зависимостей
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    ntpdate \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя
RUN useradd -m -u 1000 appuser

# Рабочая директория
WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    --index-url https://pypi.org/simple/ \
    --timeout 100 \
    gunicorn  # Добавляем Gunicorn

# Копируем проект
COPY . .

# Права
RUN chown -R appuser:appuser /app

# Переходим в папку с manage.py
WORKDIR /app/Crypto_Service

# Собираем статику (будет выполняться при сборке)
RUN python manage.py collectstatic --noinput

# Запуск через Gunicorn вместо runserver
CMD /bin/sh -c "ntpdate pool.ntp.org && su appuser -c 'gunicorn --bind 0.0.0.0:8000 cryptoservice.wsgi'"