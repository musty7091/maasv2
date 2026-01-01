# 1. Resmi Python imajını kullan (Hafif sürüm)
FROM python:3.10-slim

# 2. Performans ayarları (Python çıktılarını anlık gösterir)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Çalışma klasörünü oluştur
WORKDIR /app

# 4. Sistem kütüphanelerini yükle (PostgreSQL ve derleme araçları için gerekli)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Gereksinim dosyasını kopyala ve kütüphaneleri yükle
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 6. Proje dosyalarını kopyala
COPY . /app/

# 7. Portu dışarıya aç (Cloud Run genelde 8080 kullanır)
ENV PORT=8080

# 8. BAŞLATMA KOMUTU (EN ÖNEMLİ KISIM BURASI)
# - Önce tabloları oluşturur (migrate)
# - Sonra admin kullanıcısı oluşturmayı dener (varsa hata vermez, devam eder)
# - Son olarak Gunicorn sunucusunu başlatır
CMD python manage.py migrate && \
    python manage.py createsuperuser --noinput --username admin --email m.mkaradeniz@gmail.com || true && \
    exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 avlu_backend.wsgi:application