FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

VOLUME /app/data

ENV DATABASE_URL=sqlite:////app/data/travel_bot.db

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

CMD ["python", "fly_polling.py"]