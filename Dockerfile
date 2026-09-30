FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Windows ke line endings (CRLF) hata do, warna start.sh Linux par nahi chalti
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

# Build ke waqt sirf collectstatic chalta hai, is liye dummy SECRET_KEY kaafi hai.
# Asli SECRET_KEY Render ke environment variables se runtime par aati hai.
RUN SECRET_KEY=build-only-dummy-key python manage.py collectstatic --noinput --skip-checks

EXPOSE 8000

CMD ["./start.sh"]