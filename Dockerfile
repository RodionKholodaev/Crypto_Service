# Базовый образ Python
FROM python:3.10-slim

# Оптимизация работы Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Установка часового пояса UTC
ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Установка зависимостей для PostgreSQL, ntpdate и других утилит
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    ntpdate \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя для запуска приложения
RUN useradd -m -u 1000 appuser

# Создаем и переходим в рабочую директорию
WORKDIR /app

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    --index-url https://pypi.org/simple/ \
    --timeout 100

# Копируем весь проект
COPY . .

# Устанавливаем права на проект
RUN chown -R appuser:appuser /app

# Переходим в папку с manage.py
WORKDIR /app/Crypto_Service

# Синхронизация времени с помощью ntpdate и запуск приложения
CMD /bin/sh -c "ntpdate pool.ntp.org && su appuser -c 'python manage.py runserver 0.0.0.0:8000'"