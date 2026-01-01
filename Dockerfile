# 1. Python Sürümü
FROM python:3.10-slim

# 2. Ayarlar
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Klasör
WORKDIR /app

# 4. Kütüphaneler
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 5. Dosyalar
COPY . /app/

# 6. Port
ENV PORT 8080

# 7. BAŞLATMA KOMUTU (SİHİRLİ KISIM - GÜNCELLENDİ) ⚠️
# Önce 'migrate' ile tabloları kurar, sonra siteyi açar.
CMD python manage.py migrate && exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 avlu_backend.wsgi:application