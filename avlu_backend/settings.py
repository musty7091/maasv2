"""
Django settings for avlu_backend project.
NİHAİ SÜRÜM - SQLITE YAPILANDIRMASI
"""

from pathlib import Path
import os
import environ

# 1. Env başlatma
env = environ.Env(
    DEBUG=(bool, True),
    SECRET_KEY=(str, 'django-insecure-local-key'),
)

# Ana dizin
BASE_DIR = Path(__file__).resolve().parent.parent

# .env dosyasını oku
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# --- GÜVENLİK AYARLARI ---
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG') 
ALLOWED_HOSTS = ['*']

# Cloud Run / PythonAnywhere için güvenilen kaynaklar
CSRF_TRUSTED_ORIGINS = ['https://*.run.app', 'http://localhost:8080', 'https://*.pythonanywhere.com']

# --- UYGULAMALAR ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic', 
    'django.contrib.staticfiles',
    'core', 
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', 
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'avlu_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'avlu_backend.wsgi.application'

# --- VERİTABANI (SQLITE OLARAK SABİTLENDİ) ---
# Karmaşık URL'ler ve şifre hatalarıyla uğraşmamak için SQLite kullanıyoruz.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# --- ŞİFRE DOĞRULAMA ---
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

# --- DİL VE SAAT ---
LANGUAGE_CODE = 'tr-tr'
TIME_ZONE = 'Europe/Istanbul'
USE_I18N = True
USE_TZ = True

# --- STATİK DOSYALAR ---
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# --- GİRİŞ/ÇIKIŞ AYARLARI ---
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'ana_sayfa' 
LOGOUT_REDIRECT_URL = 'login'

# --- EMAIL ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_PASSWORD', default='')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Güvenlik Ayarları
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')