from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User  # <-- EKLENDİ
from datetime import timedelta, datetime       # <-- EKLENDİ (Puantaj hesabı için gerekli)
import math

class Personel(models.Model):
    CALISMA_TIPLERI = (
        ('aylik', 'Aylık Maaşlı'),
        ('gunluk', 'Günlük Yevmiyeli'),
    )

    ad = models.CharField(max_length=50, verbose_name="Ad")
    soyad = models.CharField(max_length=50, verbose_name="Soyad")
    tc_no = models.CharField(max_length=11, unique=True, verbose_name="TC Kimlik No")
    telefon = models.CharField(max_length=15, verbose_name="Telefon")
    
    # Finansal Bilgiler
    iban = models.CharField(max_length=34, verbose_name="IBAN", blank=True, null=True)
    banka_adi = models.CharField(max_length=50, verbose_name="Banka Adı", blank=True, null=True)
    calisma_tipi = models.CharField(max_length=10, choices=CALISMA_TIPLERI, default='aylik', verbose_name="Çalışma Tipi")
    
    # Maaş: Aylıkçı ise Aylık Net, Günlükçü ise Günlük Yevmiye
    maas_tutari = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Maaş/Yevmiye Tutarı")
    
    # Özelleştirilebilir Alanlar
    ozel_mesai_ucreti = models.DecimalField(max_digits=10, decimal_places=2, default=250.00, verbose_name="Saatlik Mesai Ücreti")
    gunluk_calisma_saati = models.PositiveIntegerField(default=8, verbose_name="Günlük Çalışma Saati (Saat)")
    
    ise_giris_tarihi = models.DateField(default=timezone.now, verbose_name="İşe Giriş Tarihi")
    aktif_mi = models.BooleanField(default=True, verbose_name="Aktif Personel") # Arşivleme için

    class Meta:
        verbose_name = "Personel"
        verbose_name_plural = "Personeller"

    def __str__(self):
        return f"{self.ad} {self.soyad}"


class TaksitliAvans(models.Model):
    """
    Uzun vadeli, taksit taksit maaştan düşecek büyük avanslar.
    """
    personel = models.ForeignKey(Personel, on_delete=models.CASCADE, related_name='taksitli_avanslar')
    tarih = models.DateField(default=timezone.now, verbose_name="Veriliş Tarihi")
    toplam_tutar = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Toplam Tutar")
    taksit_sayisi = models.PositiveIntegerField(default=1, verbose_name="Taksit Sayısı")
    aylik_kesinti = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Aylık Kesilecek Tutar")
    aciklama = models.TextField(blank=True, null=True, verbose_name="Açıklama")
    
    # Durum takibi
    tamamlandi = models.BooleanField(default=False, verbose_name="Borç Bitti mi?")

    def save(self, *args, **kwargs):
        # Otomatik aylık taksit hesapla
        if self.taksit_sayisi > 0 and not self.aylik_kesinti:
            self.aylik_kesinti = self.toplam_tutar / self.taksit_sayisi
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Taksitli Avans"
        verbose_name_plural = "Taksitli Avanslar"
    
    def __str__(self):
        return f"{self.personel} - {self.toplam_tutar} TL"


class FinansalHareket(models.Model):
    """
    Maaştan tek seferde düşülecek kalemler veya Eklenecek Primler
    """
    TIPLER = (
        ('basit_avans', 'Basit Avans (Kesinti)'),
        ('kasa_acigi', 'Kasa Açığı (Kesinti)'),
        ('alisveris', 'Alışveriş/Yeme-İçme (Kesinti)'),
        ('prim', 'Prim / Bonus (MAAŞA EKLENİR)'),
    )

    personel = models.ForeignKey(Personel, on_delete=models.CASCADE, related_name='finansal_hareketler')
    tarih = models.DateField(default=timezone.now, verbose_name="İşlem Tarihi")
    islem_tipi = models.CharField(max_length=20, choices=TIPLER, verbose_name="İşlem Tipi")
    tutar = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Tutar")
    aciklama = models.CharField(max_length=255, blank=True, null=True, verbose_name="Açıklama")

    class Meta:
        verbose_name = "Finansal Hareket (Avans/Prim)"
        verbose_name_plural = "Finansal Hareketler"
    
    def __str__(self):
        return f"{self.personel} - {self.get_islem_tipi_display()} - {self.tutar}"


class Puantaj(models.Model):
    DURUMLAR = (
        ('geldi', 'Geldi (Normal)'),
        ('hafta_tatili', 'Hafta Tatili Çalışması (Tüm Saatler Mesai)'),
        ('gelmedi', 'Gelmedi'),
        ('izinli', 'İzinli (Ücretli)'),
        ('ucretsiz_izin', 'Ücretsiz İzin'),
        ('raporlu', 'Raporlu'),
    )

    personel = models.ForeignKey(Personel, on_delete=models.CASCADE, related_name='puantajlar')
    tarih = models.DateField(default=timezone.now, verbose_name="Tarih")
    durum = models.CharField(max_length=20, choices=DURUMLAR, default='geldi', verbose_name="Durum")
    
    giris_saati = models.TimeField(blank=True, null=True, verbose_name="Giriş Saati")
    cikis_saati = models.TimeField(blank=True, null=True, verbose_name="Çıkış Saati")
    
    # Otomatik Hesaplanan Alanlar
    hesaplanan_mesai_saati = models.DecimalField(max_digits=4, decimal_places=2, default=0.00, verbose_name="Hesaplanan Mesai (Saat)")
    manuel_mesai_saati = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, verbose_name="Manuel Düzeltme (Varsa)")

    class Meta:
        verbose_name = "Günlük Yoklama"
        verbose_name_plural = "Günlük Yoklamalar"
        unique_together = ('personel', 'tarih') # Aynı kişiye aynı gün 2 kayıt girilmesin

    def save(self, *args, **kwargs):
        """
        Mesai Hesaplama Mantığı (Otomatik)
        Web formundan gelen 'String' (Yazı) formatındaki saati 'Time' objesine çeviriyoruz.
        """
        # 1. Veri Tipi Kontrolü ve Dönüştürme
        if self.giris_saati and isinstance(self.giris_saati, str):
            try:
                self.giris_saati = datetime.strptime(self.giris_saati, '%H:%M').time()
            except ValueError:
                self.giris_saati = None

        if self.cikis_saati and isinstance(self.cikis_saati, str):
            try:
                self.cikis_saati = datetime.strptime(self.cikis_saati, '%H:%M').time()
            except ValueError:
                self.cikis_saati = None

        self.hesaplanan_mesai_saati = 0

        # 2. Hesaplama Mantığı
        if (self.durum == 'geldi' or self.durum == 'hafta_tatili') and self.giris_saati and self.cikis_saati:
            # Saat farkını hesapla
            giris = datetime.combine(self.tarih, self.giris_saati)
            cikis = datetime.combine(self.tarih, self.cikis_saati)
            
            # Eğer çıkış saati girişten küçükse (gece yarısını geçtiyse) gün ekle
            if cikis < giris:
                cikis += timedelta(days=1)
            
            calisilan_sure = cikis - giris
            calisilan_saat = calisilan_sure.total_seconds() / 3600
            
            # MESAİ HESABI:
            if self.durum == 'hafta_tatili':
                 # Hafta tatilinde çalışırsa standart saati düşmüyoruz, hepsi mesai.
                sonuc_saat = calisilan_saat
                is_negative = False
            else:
                 # Normal günde standart saat düşülür.
                standart_saat = self.personel.gunluk_calisma_saati
                fark_saat = calisilan_saat - standart_saat
                
                is_negative = fark_saat < 0
                abs_fark = abs(fark_saat)
                
                tam_saat = int(abs_fark)
                dakika_kismi = (abs_fark - tam_saat) * 60
                
                eklenen_mesai = 0
                
                # Senin belirlediğin kurallar:
                if dakika_kismi <= 15:
                    eklenen_mesai = 0 
                elif 16 <= dakika_kismi <= 45:
                    eklenen_mesai = 0.5 
                elif dakika_kismi >= 46:
                    eklenen_mesai = 1.0 
                
                sonuc_saat = tam_saat + eklenen_mesai

            # Sonucu kaydet (Eksi ise eksi olarak)
            if is_negative:
                self.hesaplanan_mesai_saati = -sonuc_saat
            else:
                self.hesaplanan_mesai_saati = sonuc_saat
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.personel} - {self.tarih} - {self.durum}"


class MaasBordrosu(models.Model):
    """
    Ay sonunda hesaplanan maaşların sabitlenmiş (snapshot) halidir.
    Personel maaşı değişse bile buradaki kayıt değişmez.
    """
    personel = models.ForeignKey(Personel, on_delete=models.PROTECT, verbose_name="Personel")
    donem = models.DateField(verbose_name="Dönem (Her ayın 1'i)") # Ör: 01.10.2025
    
    # O anki maaş bilgisi (Snapshot)
    brut_maas = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="O Ayki Maaş/Yevmiye")
    
    # Hesaplanan Değerler
    calistigi_gun = models.IntegerField(default=0, verbose_name="Çalıştığı Gün")
    gelmedigi_gun = models.IntegerField(default=0, verbose_name="Gelmediği Gün")
    mesai_saati = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Mesai Saati")
    mesai_ucreti = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Mesai Ücreti")
    
    toplam_prim = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Toplam Prim")
    toplam_kesinti = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Toplam Kesinti")
    
    net_odenecek = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Net Ödenecek Tutar")
    
    olusturulma_tarihi = models.DateTimeField(auto_now_add=True, verbose_name="İşlem Tarihi")

    class Meta:
        verbose_name = "Maaş Bordrosu (Kesinleşmiş)"
        verbose_name_plural = "Maaş Bordroları"
        unique_together = ('personel', 'donem') # Bir personelin o aya ait sadece 1 bordrosu olabilir.

    def __str__(self):
        return f"{self.personel.ad} - {self.donem.strftime('%B %Y')}"

# DÜZELTME: IslemLog artık MaasBordrosu'nun içinde değil, dışarıda tek başına bir sınıf.
class IslemLog(models.Model):
    """
    Sistemdeki kritik işlemlerin (Ekleme, Silme, Güncelleme) kayıt altına alındığı tablodur.
    """
    ISLEM_TURLERI = (
        ('ekleme', 'Ekleme'),
        ('guncelleme', 'Güncelleme'),
        ('silme', 'Silme'),
        ('kritik', 'Kritik İşlem (Bordro vb.)'),
    )

    kullanici = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="İşlemi Yapan")
    islem_turu = models.CharField(max_length=20, choices=ISLEM_TURLERI, verbose_name="İşlem Türü")
    konu = models.CharField(max_length=100, verbose_name="Konu (Örn: Finansal Hareket)")
    detay = models.TextField(verbose_name="İşlem Detayı")
    tarih = models.DateTimeField(auto_now_add=True, verbose_name="Tarih/Saat")
    
    # Hangi personelle ilgili işlem yapıldı? (Opsiyonel)
    ilgili_personel = models.ForeignKey(Personel, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="İlgili Personel")

    class Meta:
        verbose_name = "İşlem Logu"
        verbose_name_plural = "İşlem Logları (Audit)"
        ordering = ['-tarih'] # En yeni en üstte

    def __str__(self):
        return f"{self.kullanici} - {self.islem_turu} - {self.tarih.strftime('%d.%m.%Y %H:%M')}"