from django.contrib import admin
# DİKKAT: Aşağıdaki satıra 'IslemLog' eklendi.
from .models import Personel, TaksitliAvans, FinansalHareket, Puantaj, MaasBordrosu, IslemLog

@admin.register(Personel)
class PersonelAdmin(admin.ModelAdmin):
    list_display = ('ad', 'soyad', 'telefon', 'calisma_tipi', 'aktif_mi')
    search_fields = ('ad', 'soyad', 'tc_no')
    list_filter = ('calisma_tipi', 'aktif_mi')

@admin.register(Puantaj)
class PuantajAdmin(admin.ModelAdmin):
    list_display = ('personel', 'tarih', 'durum', 'giris_saati', 'cikis_saati', 'hesaplanan_mesai_saati')
    list_filter = ('tarih', 'durum')
    date_hierarchy = 'tarih'

@admin.register(FinansalHareket)
class FinansalHareketAdmin(admin.ModelAdmin):
    list_display = ('personel', 'islem_tipi', 'tutar', 'tarih')
    list_filter = ('islem_tipi', 'tarih')

@admin.register(TaksitliAvans)
class TaksitliAvansAdmin(admin.ModelAdmin):
    list_display = ('personel', 'toplam_tutar', 'taksit_sayisi', 'tamamlandi')

@admin.register(MaasBordrosu)
class MaasBordrosuAdmin(admin.ModelAdmin):
    list_display = ('personel', 'donem', 'net_odenecek', 'olusturulma_tarihi')
    list_filter = ('donem', 'personel')
    search_fields = ('personel__ad', 'personel__soyad')

# --- YENİ EKLENEN LOG SİSTEMİ ---
@admin.register(IslemLog)
class IslemLogAdmin(admin.ModelAdmin):
    list_display = ('tarih', 'kullanici', 'islem_turu', 'konu', 'ilgili_personel')
    list_filter = ('islem_turu', 'kullanici', 'tarih')
    search_fields = ('detay', 'kullanici__username', 'ilgili_personel__ad')
    
    # Loglar değiştirilemez, sadece okunabilir olmalı (Güvenlik)
    readonly_fields = ('tarih', 'kullanici', 'islem_turu', 'konu', 'detay', 'ilgili_personel')
    
    def has_add_permission(self, request):
        return False # Elle log eklenemesin
    
    def has_delete_permission(self, request, obj=None):
        return False # Loglar silinemesin (Güvenlik)