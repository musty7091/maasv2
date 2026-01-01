from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.utils import timezone
from django.conf import settings
import os
import shutil
from datetime import datetime

class Command(BaseCommand):
    help = 'Veritabanını (db.sqlite3) e-posta adresine yedek olarak gönderir.'

    def handle(self, *args, **options):
        # 1. Veritabanı dosyasını bul
        db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
        
        if not os.path.exists(db_path):
            self.stdout.write(self.style.ERROR('Veritabanı dosyası bulunamadı!'))
            return

        # 2. Tarihli dosya ismi oluştur (Ör: db_yedek_2025-10-25.sqlite3)
        bugun = timezone.now().strftime('%Y-%m-%d')
        yedek_isim = f"db_yedek_{bugun}.sqlite3"
        
        # 3. E-Postayı hazırla
        konu = f"💾 Otomatik Yedek: Avlu Personel - {bugun}"
        mesaj = f"""
        Merhaba,
        
        Avlu Personel sisteminin {bugun} tarihli otomatik veritabanı yedeği ektedir.
        Bu dosyayı güvenli bir yerde saklayınız.
        
        Sistem Saati: {datetime.now().strftime('%H:%M:%S')}
        """
        
        gonderen = settings.EMAIL_HOST_USER
        alici_listesi = [settings.EMAIL_HOST_USER] # Kendine gönder

        mail = EmailMessage(
            subject=konu,
            body=mesaj,
            from_email=gonderen,
            to=alici_listesi,
        )
        
        # 4. Dosyayı ekle ve gönder
        with open(db_path, 'rb') as f:
            mail.attach(yedek_isim, f.read(), 'application/x-sqlite3')
            
        try:
            mail.send()
            self.stdout.write(self.style.SUCCESS(f'✅ Yedek başarıyla {gonderen} adresine gönderildi.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Hata oluştu: {str(e)}'))