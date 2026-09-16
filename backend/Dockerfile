FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright needs system dependencies. --with-deps handles the OS-level lifting on Debian-slim.
RUN playwright install --with-deps chromium

# Copy the rest of the application
COPY . .

# Cloud providers dynamically assign the PORT variable
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
