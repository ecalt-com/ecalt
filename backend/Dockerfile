FROM python:3.11-slim

WORKDIR /app

# Pinned versions (regenerate with the uv command in requirements.lock)
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
