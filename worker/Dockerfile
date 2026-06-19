FROM python:3.10-slim
WORKDIR /app

COPY requirements.txt .

# We added --extra-index-url to force it to download the lightweight CPU-only AI libraries
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

COPY . .

# This command starts the Celery worker process
CMD ["celery", "-A", "tasks.celery_app", "worker", "--loglevel=info"]