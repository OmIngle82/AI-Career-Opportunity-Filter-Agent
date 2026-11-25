FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright needs libatomic1 to launch its bundled Node CLI before --with-deps installs browser OS deps.
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 && rm -rf /var/lib/apt/lists/* \
    && playwright install --with-deps chromium

# Copy the rest of the application
COPY . .

# Cloud providers dynamically assign the PORT variable
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
