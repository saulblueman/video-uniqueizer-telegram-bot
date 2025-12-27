FROM python:3.10-slim

# Устанавливаем ffmpeg и системные зависимости
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем requirements
COPY requirements.txt .

# Устанавливаем зависимости из файла + принудительно python-dotenv
RUN pip install --no-cache-dir -r requirements.txt python-dotenv

# Копируем остальной код
COPY . .

# Запуск бота
CMD ["python", "bot.py"]
