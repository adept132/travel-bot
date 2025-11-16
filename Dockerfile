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

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:$PORT/healthz || exit 1

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["python", "fly_polling.py"]