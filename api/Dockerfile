FROM python:3.10-slim
WORKDIR /app

COPY requirements.txt .

# Using the CPU-only flag to avoid Nvidia bloat and timeout errors!
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]