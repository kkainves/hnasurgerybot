FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Копируем всё кроме .env (Fly.io добавит его как секрет)
COPY . . 

# Точка входа
CMD ["python", "bot.py"]