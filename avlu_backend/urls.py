from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views # <-- YENİ: Giriş/Çıkış için gerekli
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- YENİ EKLENEN GİRİŞ/ÇIKIŞ YOLLARI ---
    path('giris/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('cikis/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    # ----------------------------------------

    path('', views.ana_sayfa, name='ana_sayfa'),
    path('personeller/', views.personel_listesi, name='personel_listesi'),
    path('personel-ekle-excel/', views.personel_import, name='personel_import'),
    path('sablon-indir/', views.download_excel_template, name='download_excel_template'),
    path('personel/<int:personel_id>/', views.personel_detay, name='personel_detay'),
    path('yoklama/', views.yoklama_al, name='yoklama_al'),
    path('personel/<int:personel_id>/toplu-puantaj/', views.toplu_puantaj, name='toplu_puantaj'),
    path('maas-raporu/', views.maas_raporu, name='maas_raporu'),
    path('maas-raporu-indir/', views.maas_raporu_indir, name='maas_raporu_indir'),
    path('personel/<int:personel_id>/pusula/', views.personel_pusula, name='personel_pusula'),
    path('giris-cikis-raporu/', views.giris_cikis_raporu, name='giris_cikis_raporu'),
    path('giris-cikis-raporu-indir/', views.giris_cikis_raporu_indir, name='giris_cikis_raporu_indir'),
    path('maas-bordrosu-olustur/', views.maas_bordrosu_olustur, name='maas_bordrosu_olustur'),
    path('islem-sil/<int:islem_id>/', views.finansal_hareket_sil, name='finansal_hareket_sil'),
    path('update_server/', views.update_server, name='update_server'),
]