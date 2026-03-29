# 1. Базовый образ
FROM python:3.12-slim

# 2. Установка системных зависимостей для libvips и инструментов сборки
RUN apt-get update && apt-get install -y \
    libvips-dev \
    pkg-config \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 3. Рабочая директория внутри контейнера
WORKDIR /app

# 3.1. Create logs directory
RUN mkdir -p /app/logs && chmod 777 /app/logs

# 4. Сначала ставим зависимости
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 5. Копируем исходники
COPY app.py /app/
COPY config.py /app/
COPY logger_config.py /app/
COPY image_processor.py /app/
COPY rpc.py /app/
COPY rabbitmq_consumer.py /app/
COPY unzipper.py /app/
COPY templates /app/templates
COPY static /app/static

# 6. Порт, который слушает приложение
EXPOSE 8000

# 7. Команда запуска
# Increase timeout for file uploads (default is 60 seconds)
# Enable access logs to see all requests
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300", "--access-log", "--log-level", "info"]
