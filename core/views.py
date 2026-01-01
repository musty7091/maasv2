from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Q, Prefetch
from django.http import HttpResponse 
from .models import Personel, Puantaj, FinansalHareket, TaksitliAvans, MaasBordrosu, IslemLog
from .forms import PuantajForm, FinansalIslemForm, TaksitliAvansForm
from datetime import datetime
import calendar
import pandas as pd
import io

# --- YARDIMCI FONKSİYONLAR ---

def _log_kaydet(request, tur, konu, detay, personel=None):
    """
    Sistemdeki önemli işlemleri veritabanına log olarak kaydeder.
    """
    if request.user.is_authenticated:
        try:
            IslemLog.objects.create(
                kullanici=request.user,
                islem_turu=tur,
                konu=konu,
                detay=detay,
                ilgili_personel=personel
            )
        except Exception as e:
            print(f"Log kaydı hatası: {e}")

def _maas_verilerini_hesapla(yil, ay):
    """
    Verilen yıl ve ay için maaş verilerini getirir.
    Önce MaasBordrosu tablosuna bakar (Sabitlenmiş mi?),
    Yoksa canlı hesaplama yapar.
    
    Dönüş: (bordro_var_mi, rapor_listesi)
    """
    # 1. Önce veritabanında kesinleşmiş bordro var mı diye bak
    kayitli_bordrolar = MaasBordrosu.objects.filter(donem__year=yil, donem__month=ay).select_related('personel')
    
    if kayitli_bordrolar.exists():
        # --- KAYITLI VERİDEN OKUMA (SNAPSHOT) ---
        rapor_listesi = []
        for b in kayitli_bordrolar:
            # Geriye dönük ana hakediş tahmini (Gösterim tutarlılığı için)
            ana_hakedis_tahmini = float(b.net_odenecek) + float(b.toplam_kesinti) - float(b.toplam_prim) - float(b.mesai_ucreti)
            
            rapor_listesi.append({
                'personel': b.personel,
                'calistigi_gun': b.calistigi_gun,
                'gelmedigi_gun': b.gelmedigi_gun,
                'ana_hakedis': ana_hakedis_tahmini,
                'toplam_mesai': float(b.mesai_saati),
                'mesai_ucreti': float(b.mesai_ucreti),
                'toplam_prim': float(b.toplam_prim),
                'toplam_kesinti': float(b.toplam_kesinti),
                'net_maas': float(b.net_odenecek),
                'durum': 'kesinlesmis'
            })
        return True, rapor_listesi

    else:
        # --- CANLI HESAPLAMA (LIVE CALCULATION) ---
        puantaj_query = Puantaj.objects.filter(tarih__year=yil, tarih__month=ay)
        hareket_query = FinansalHareket.objects.filter(tarih__year=yil, tarih__month=ay)
        taksit_query = TaksitliAvans.objects.filter(tamamlandi=False)

        personeller = Personel.objects.filter(aktif_mi=True).prefetch_related(
            Prefetch('puantajlar', queryset=puantaj_query, to_attr='aylik_puantajlar'),
            Prefetch('finansal_hareketler', queryset=hareket_query, to_attr='aylik_hareketler'),
            Prefetch('taksitli_avanslar', queryset=taksit_query, to_attr='aktif_taksitler')
        )

        rapor_listesi = []
        for p in personeller:
            # Puantaj
            calistigi_gun = 0
            gelmedigi_gun = 0
            toplam_mesai = 0.0
            
            for pt in p.aylik_puantajlar:
                if pt.durum in ['geldi', 'hafta_tatili']:
                    calistigi_gun += 1
                elif pt.durum in ['gelmedi', 'ucretsiz_izin']:
                    gelmedigi_gun += 1
                toplam_mesai += float(pt.hesaplanan_mesai_saati)

            mesai_ucreti = toplam_mesai * float(p.ozel_mesai_ucreti)

            # Ana Hakediş
            ana_hakedis = 0
            if p.calisma_tipi == 'aylik':
                gunluk_maliyet = float(p.maas_tutari) / 30
                maas_kesintisi = gunluk_maliyet * gelmedigi_gun
                ana_hakedis = float(p.maas_tutari) - maas_kesintisi
            else:
                ana_hakedis = float(p.maas_tutari) * calistigi_gun

            # Finansal Hareketler
            toplam_prim = 0.0
            diger_kesintiler = 0.0
            for h in p.aylik_hareketler:
                if h.islem_tipi == 'prim':
                    toplam_prim += float(h.tutar)
                else:
                    diger_kesintiler += float(h.tutar)
            
            # Taksitler
            taksit_kesintisi = sum(float(t.aylik_kesinti) for t in p.aktif_taksitler)

            toplam_kesinti = diger_kesintiler + taksit_kesintisi
            net_maas = ana_hakedis + mesai_ucreti + toplam_prim - toplam_kesinti

            rapor_listesi.append({
                'personel': p,
                'calistigi_gun': calistigi_gun,
                'gelmedigi_gun': gelmedigi_gun,
                'ana_hakedis': ana_hakedis,
                'toplam_mesai': toplam_mesai,
                'mesai_ucreti': mesai_ucreti,
                'toplam_prim': toplam_prim,
                'toplam_kesinti': toplam_kesinti,
                'net_maas': net_maas,
                'durum': 'taslak'
            })
        
        return False, rapor_listesi

# --- VIEW FONKSİYONLARI ---

@login_required
def ana_sayfa(request):
    bugun = timezone.now().date()
    
    toplam_personel = Personel.objects.filter(aktif_mi=True).count()
    bugun_gelen = Puantaj.objects.filter(tarih=bugun, durum__in=['geldi', 'hafta_tatili']).count()
    gelmeyen = toplam_personel - bugun_gelen
    
    bu_ay_avans = FinansalHareket.objects.filter(
        tarih__year=bugun.year,
        tarih__month=bugun.month,
        islem_tipi__in=['basit_avans', 'kasa_acigi', 'alisveris']
    ).aggregate(Sum('tutar'))['tutar__sum'] or 0

    son_hareketler = FinansalHareket.objects.select_related('personel').order_by('-id')[:5]

    return render(request, 'core/ana_sayfa.html', {
        'toplam_personel': toplam_personel,
        'bugun_gelen': bugun_gelen,
        'gelmeyen': gelmeyen,
        'bu_ay_avans': bu_ay_avans,
        'son_hareketler': son_hareketler,
        'bugun': bugun,
    })

@login_required
def personel_listesi(request):
    personeller = Personel.objects.filter(aktif_mi=True)
    return render(request, 'core/personel_listesi.html', {'personeller': personeller})

@login_required
def personel_detay(request, personel_id):
    personel = get_object_or_404(Personel, id=personel_id)
    bugun = timezone.now().date()

    # 1. TARİH SEÇİMİNİ AL (URL'den veya bugünden)
    try:
        yil = int(request.GET.get('yil', bugun.year))
        ay = int(request.GET.get('ay', bugun.month))
    except ValueError:
        yil = bugun.year
        ay = bugun.month

    # 2. GÜVENLİK DUVARI: GEÇMİŞ DÖNEM KONTROLÜ
    # Seçilen dönem geçmişse ve kullanıcı Süper Yönetici DEĞİLSE -> Bugüne zorla.
    secilen_tarih_baslangic = datetime(yil, ay, 1).date()
    mevcut_tarih_baslangic = datetime(bugun.year, bugun.month, 1).date()

    if secilen_tarih_baslangic < mevcut_tarih_baslangic:
        if not request.user.is_superuser:
            messages.warning(request, "Geçmiş dönem kayıtlarını görüntüleme yetkiniz yok. Güncel döneme yönlendirildiniz.")
            return redirect(f'/personel/{personel.id}/')

    # 3. İŞLEM EKLEME (POST)
    if request.method == 'POST':
        if 'basit_islem' in request.POST:
            form = FinansalIslemForm(request.POST)
            if form.is_valid():
                islem = form.save(commit=False)
                islem.personel = personel
                # İşlem tarihi modelde auto_now_add değilse formdan gelir, biz default olarak bugün atıyoruz modelde.
                # Eğer kullanıcı spesifik bir tarihe eklemek isterse formda tarih alanı açılabilir.
                # Şimdilik "İşlem yapıldığı anın tarihi" olarak kaydediliyor.
                islem.save()
                
                # --- LOG EKLE ---
                _log_kaydet(request, 'ekleme', 'Finansal Hareket', 
                           f"{islem.tutar} TL tutarında {islem.get_islem_tipi_display()} eklendi. Açıklama: {islem.aciklama}", 
                           personel)
                
                messages.success(request, 'İşlem eklendi.')
                return redirect(f'/personel/{personel.id}/?ay={ay}&yil={yil}')
    else:
        finans_form = FinansalIslemForm(initial={'personel': personel})

    # 4. VERİLERİ SADECE O AY İÇİN ÇEK (FİLTRELEME)
    hareketler = personel.finansal_hareketler.filter(
        tarih__year=yil, 
        tarih__month=ay
    ).order_by('-tarih')

    # Avanslar genelde uzun vadeli olduğu için hepsi görünebilir veya filtrelenebilir.
    avanslar = personel.taksitli_avanslar.all()

    return render(request, 'core/personel_detay.html', {
        'personel': personel,
        'hareketler': hareketler,
        'avanslar': avanslar,
        'finans_form': finans_form,
        'yil': yil,
        'ay': ay,
        'ay_adi': calendar.month_name[ay]
    })

@login_required
def finansal_hareket_sil(request, islem_id):
    """
    Girilen hatalı bir finansal hareketi siler.
    Eğer bordro kesilmişse silmez.
    """
    islem = get_object_or_404(FinansalHareket, id=islem_id)
    personel = islem.personel
    
    # --- GÜVENLİK: BORDRO KONTROLÜ ---
    if MaasBordrosu.objects.filter(
        personel=personel, 
        donem__year=islem.tarih.year, 
        donem__month=islem.tarih.month
    ).exists():
        messages.error(request, f"⛔ HATA: {islem.tarih.strftime('%B %Y')} dönemi kapatıldığı için bu işlem silinemez!")
        return redirect('personel_detay', personel_id=personel.id)
    
    # --- LOG EKLE ---
    _log_kaydet(request, 'silme', 'Finansal Hareket', 
               f"{islem.tutar} TL tutarında {islem.get_islem_tipi_display()} silindi. Tarih: {islem.tarih}", 
               personel)
    
    islem.delete()
    messages.success(request, 'İşlem başarıyla silindi.')
    return redirect('personel_detay', personel_id=personel.id)

@login_required
def yoklama_al(request):
    secilen_tarih_str = request.GET.get('tarih')
    if secilen_tarih_str:
        secilen_tarih = datetime.strptime(secilen_tarih_str, '%Y-%m-%d').date()
    else:
        secilen_tarih = timezone.now().date()
    
    personeller = Personel.objects.filter(aktif_mi=True)
    
    if request.method == 'POST':
        personel_id = request.POST.get('personel_id')
        durum = request.POST.get('durum')
        giris = request.POST.get('giris_saati')
        cikis = request.POST.get('cikis_saati')
        
        kayit_tarihi_str = request.POST.get('kayit_tarihi')
        kayit_tarihi = datetime.strptime(kayit_tarihi_str, '%Y-%m-%d').date()
        
        personel = get_object_or_404(Personel, id=personel_id)
        
        puantaj, created = Puantaj.objects.get_or_create(
            personel=personel, 
            tarih=kayit_tarihi
        )
        puantaj.durum = durum
        puantaj.giris_saati = giris if giris else None
        puantaj.cikis_saati = cikis if cikis else None
        puantaj.save()
        
        messages.success(request, f'{personel.ad} güncellendi.')
        return redirect(f'/yoklama/?tarih={kayit_tarihi}')

    gunun_kayitlari = {p.personel_id: p for p in Puantaj.objects.filter(tarih=secilen_tarih)}
    
    list_data = []
    for p in personeller:
        kayit = gunun_kayitlari.get(p.id)
        list_data.append({
            'personel': p,
            'kayit': kayit
        })

    return render(request, 'core/yoklama.html', {
        'list_data': list_data, 
        'secilen_tarih': secilen_tarih
    })

@login_required
def toplu_puantaj(request, personel_id):
    personel = get_object_or_404(Personel, id=personel_id)
    
    bugun = timezone.now().date()
    try:
        yil = int(request.GET.get('yil', bugun.year))
        ay = int(request.GET.get('ay', bugun.month))
    except ValueError:
        yil = bugun.year
        ay = bugun.month
    
    _, son_gun = calendar.monthrange(yil, ay)
    
    if request.method == 'POST':
        for day in range(1, son_gun + 1):
            tarih_str = f"{yil}-{ay:02d}-{day:02d}"
            tarih_obj = datetime.strptime(tarih_str, '%Y-%m-%d').date()
            
            durum = request.POST.get(f'durum_{tarih_str}')
            giris = request.POST.get(f'giris_{tarih_str}')
            cikis = request.POST.get(f'cikis_{tarih_str}')
            
            if not durum: continue

            puantaj, created = Puantaj.objects.get_or_create(
                personel=personel,
                tarih=tarih_obj
            )
            puantaj.durum = durum
            puantaj.giris_saati = giris if giris else None
            puantaj.cikis_saati = cikis if cikis else None
            puantaj.save()
            
        messages.success(request, f'{personel.ad} için {ay}/{yil} kayıtları güncellendi.')
        return redirect(f'/personel/{personel.id}/toplu-puantaj/?ay={ay}&yil={yil}')

    mevcut_kayitlar = {
        p.tarih.day: p 
        for p in Puantaj.objects.filter(personel=personel, tarih__year=yil, tarih__month=ay)
    }
    
    gunler_listesi = []
    for day in range(1, son_gun + 1):
        tarih_obj = datetime(yil, ay, day).date()
        kayit = mevcut_kayitlar.get(day)
        
        gunler_listesi.append({
            'tarih': tarih_obj,
            'tarih_str': f"{yil}-{ay:02d}-{day:02d}",
            'gun_adi': tarih_obj.strftime('%A'),
            'kayit': kayit
        })

    return render(request, 'core/toplu_puantaj.html', {
        'personel': personel,
        'gunler_listesi': gunler_listesi,
        'yil': yil,
        'ay': ay,
        'ay_adi': calendar.month_name[ay]
    })

@login_required
def maas_raporu(request):
    bugun = timezone.now().date()
    try:
        yil = int(request.GET.get('yil', bugun.year))
        ay = int(request.GET.get('ay', bugun.month))
    except ValueError:
        yil = bugun.year
        ay = bugun.month

    # Tek merkezden verileri çek (Kayıtlı mı yoksa Canlı mı otomatik anlar)
    bordro_var_mi, rapor_listesi = _maas_verilerini_hesapla(yil, ay)
    
    genel_toplam_odenecek = sum(item['net_maas'] for item in rapor_listesi)

    return render(request, 'core/maas_raporu.html', {
        'rapor_listesi': rapor_listesi,
        'genel_toplam': genel_toplam_odenecek,
        'yil': yil,
        'ay': ay,
        'ay_adi': calendar.month_name[ay],
        'bordro_var_mi': bordro_var_mi
    })

@login_required
def maas_bordrosu_olustur(request):
    """
    Canlı hesaplanan verileri MaasBordrosu tablosuna sabitler (Snapshot alır).
    SADECE SÜPER YÖNETİCİLER (is_superuser=True) YAPABİLİR.
    """
    # --- GÜVENLİK KONTROLÜ ---
    if not request.user.is_superuser:
        messages.error(request, "Bu işlemi yapmak için 'Süper Yönetici' yetkisine sahip olmalısınız!")
        return redirect('maas_raporu')
    
    if request.method != 'POST':
        return redirect('maas_raporu')
        
    bugun = timezone.now().date()
    try:
        yil = int(request.POST.get('yil', bugun.year))
        ay = int(request.POST.get('ay', bugun.month))
    except ValueError:
        return redirect('maas_raporu')
    
    # Canlı hesaplama yaparak kaydet (Snapshot)
    puantaj_query = Puantaj.objects.filter(tarih__year=yil, tarih__month=ay)
    hareket_query = FinansalHareket.objects.filter(tarih__year=yil, tarih__month=ay)
    taksit_query = TaksitliAvans.objects.filter(tamamlandi=False)

    personeller = Personel.objects.filter(aktif_mi=True).prefetch_related(
        Prefetch('puantajlar', queryset=puantaj_query, to_attr='aylik_puantajlar'),
        Prefetch('finansal_hareketler', queryset=hareket_query, to_attr='aylik_hareketler'),
        Prefetch('taksitli_avanslar', queryset=taksit_query, to_attr='aktif_taksitler')
    )
    
    donem_tarihi = datetime(yil, ay, 1).date()
    created_count = 0
    updated_count = 0
    
    for p in personeller:
        # --- HESAPLAMA (LIVE) ---
        calistigi_gun = 0
        gelmedigi_gun = 0
        toplam_mesai = 0.0
        
        for pt in p.aylik_puantajlar:
            if pt.durum in ['geldi', 'hafta_tatili']:
                calistigi_gun += 1
            elif pt.durum in ['gelmedi', 'ucretsiz_izin']:
                gelmedigi_gun += 1
            toplam_mesai += float(pt.hesaplanan_mesai_saati)

        mesai_ucreti = toplam_mesai * float(p.ozel_mesai_ucreti)
        
        # Finansal
        toplam_prim = 0.0
        diger_kesintiler = 0.0
        for h in p.aylik_hareketler:
            if h.islem_tipi == 'prim':
                toplam_prim += float(h.tutar)
            else:
                diger_kesintiler += float(h.tutar)
        
        taksit_kesintisi = sum(float(t.aylik_kesinti) for t in p.aktif_taksitler)
        toplam_kesinti = diger_kesintiler + taksit_kesintisi
        
        # Maaş
        if p.calisma_tipi == 'aylik':
            gunluk_maliyet = float(p.maas_tutari) / 30
            maas_kesintisi = gunluk_maliyet * gelmedigi_gun
            ana_hakedis = float(p.maas_tutari) - maas_kesintisi
        else:
            ana_hakedis = float(p.maas_tutari) * calistigi_gun
            
        net_maas = ana_hakedis + mesai_ucreti + toplam_prim - toplam_kesinti
        
        # --- KAYDETME (SNAPSHOT) ---
        obj, created = MaasBordrosu.objects.update_or_create(
            personel=p,
            donem=donem_tarihi,
            defaults={
                'brut_maas': p.maas_tutari,
                'calistigi_gun': calistigi_gun,
                'gelmedigi_gun': gelmedigi_gun,
                'mesai_saati': toplam_mesai,
                'mesai_ucreti': mesai_ucreti,
                'toplam_prim': toplam_prim,
                'toplam_kesinti': toplam_kesinti,
                'net_odenecek': net_maas
            }
        )
        if created:
            created_count += 1
        else:
            updated_count += 1

    # --- LOG EKLE ---
    _log_kaydet(request, 'kritik', 'Bordro Kesinleştirme', 
               f"{calendar.month_name[ay]} {yil} dönemi kapatıldı. ({created_count} yeni, {updated_count} güncellendi)")

    messages.success(request, f"{calendar.month_name[ay]} {yil} dönemi için Bordro oluşturuldu. ({created_count} yeni, {updated_count} güncellendi)")
    return redirect(f'/maas-raporu/?ay={ay}&yil={yil}')

@login_required
def maas_raporu_indir(request):
    bugun = timezone.now().date()
    try:
        yil = int(request.GET.get('yil', bugun.year))
        ay = int(request.GET.get('ay', bugun.month))
    except ValueError:
        yil = bugun.year
        ay = bugun.month

    # Helper'ı kullan (Bordro varsa onu getirir)
    _, rapor_listesi = _maas_verilerini_hesapla(yil, ay)

    data = []
    for item in rapor_listesi:
        p = item['personel']
        data.append({
            'Ad Soyad': f"{p.ad} {p.soyad}",
            'Çalışma Tipi': p.get_calisma_tipi_display(),
            'Çalıştığı Gün': item['calistigi_gun'],
            'Gelmediği Gün': item['gelmedigi_gun'],
            'Ana Hakediş': item['ana_hakedis'],
            'Mesai Saati': item['toplam_mesai'],
            'Mesai Ücreti': item['mesai_ucreti'],
            'Primler': item['toplam_prim'],
            'Kesintiler': item['toplam_kesinti'],
            'NET ÖDENECEK': item['net_maas']
        })

    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=f'{ay}-{yil} Maas Raporu')
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Maas_Raporu_{ay}_{yil}.xlsx"'
    return response

@login_required
def personel_import(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            df = pd.read_excel(excel_file)
            basarili = 0
            atlanan = 0
            
            for index, row in df.iterrows():
                try:
                    tc = str(row['TC No']).strip()
                    if Personel.objects.filter(tc_no=tc).exists():
                        atlanan += 1
                        continue

                    c_tipi_raw = str(row['Çalışma Tipi']).lower()
                    c_tipi = 'gunluk' if 'gün' in c_tipi_raw else 'aylik'
                    
                    tarih_val = row['Giriş Tarihi']
                    if pd.isna(tarih_val):
                        tarih_obj = timezone.now().date()
                    else:
                        tarih_obj = pd.to_datetime(tarih_val).date()

                    Personel.objects.create(
                        ad=row['Ad'],
                        soyad=row['Soyad'],
                        tc_no=tc,
                        telefon=row['Telefon'],
                        calisma_tipi=c_tipi,
                        maas_tutari=row['Maaş'],
                        ozel_mesai_ucreti=row.get('Mesai Ücreti', 250),
                        iban=row.get('IBAN', ''),
                        banka_adi=row.get('Banka', ''),
                        ise_giris_tarihi=tarih_obj
                    )
                    basarili += 1
                except Exception as e:
                    print(f"Satır hatası: {e}")
                    atlanan += 1
            
            messages.success(request, f"{basarili} personel başarıyla eklendi. {atlanan} kayıt atlandı.")
            return redirect('personel_listesi')

        except Exception as e:
            messages.error(request, f"Dosya okuma hatası: {e}")

    return render(request, 'core/personel_import.html')

@login_required
def download_excel_template(request):
    columns = ['Ad', 'Soyad', 'TC No', 'Telefon', 'Çalışma Tipi', 'Maaş', 'Mesai Ücreti', 'Giriş Tarihi', 'IBAN', 'Banka']
    df = pd.DataFrame(columns=columns)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Personel Listesi')
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="personel_sablon.xlsx"'
    return response

@login_required
def personel_pusula(request, personel_id):
    personel = get_object_or_404(Personel, id=personel_id)
    bugun = timezone.now().date()
    try:
        yil = int(request.GET.get('yil', bugun.year))
        ay = int(request.GET.get('ay', bugun.month))
    except ValueError:
        yil = bugun.year
        ay = bugun.month

    # Pusula için de önce bordro kontrolü (Bordro varsa ondan oku, yoksa canlı hesapla)
    bordro = MaasBordrosu.objects.filter(personel=personel, donem__year=yil, donem__month=ay).first()
    
    if bordro:
        # --- BORDRODAN OKUMA ---
        calistigi_gun = bordro.calistigi_gun
        gelmedigi_gun = bordro.gelmedigi_gun
        toplam_mesai = bordro.mesai_saati
        mesai_ucreti = bordro.mesai_ucreti
        
        ana_hakedis = float(bordro.net_odenecek) + float(bordro.toplam_kesinti) - float(bordro.toplam_prim) - float(bordro.mesai_ucreti)
        toplam_prim = bordro.toplam_prim
        toplam_kesinti = bordro.toplam_kesinti
        net_maas = bordro.net_odenecek
        
        # Detay listeler için yine hareket tablosuna bakıyoruz
        tum_hareketler = FinansalHareket.objects.filter(personel=personel, tarih__year=yil, tarih__month=ay).order_by('tarih')
        primler_listesi = tum_hareketler.filter(islem_tipi='prim')
        kesintiler_listesi = tum_hareketler.exclude(islem_tipi='prim')
        taksitler = TaksitliAvans.objects.filter(personel=personel, tamamlandi=False)
        taksit_kesintisi = 0 # Toplama zaten dahil

    else:
        # --- CANLI HESAPLAMA ---
        calistigi_gun = Puantaj.objects.filter(personel=personel, tarih__year=yil, tarih__month=ay, durum__in=['geldi', 'hafta_tatili']).count()
        gelmedigi_gun = Puantaj.objects.filter(personel=personel, tarih__year=yil, tarih__month=ay, durum__in=['gelmedi', 'ucretsiz_izin']).count()
        toplam_mesai = Puantaj.objects.filter(personel=personel, tarih__year=yil, tarih__month=ay).aggregate(Sum('hesaplanan_mesai_saati'))['hesaplanan_mesai_saati__sum'] or 0
        mesai_ucreti = float(toplam_mesai) * float(personel.ozel_mesai_ucreti)

        if personel.calisma_tipi == 'aylik':
            gunluk_maliyet = float(personel.maas_tutari) / 30
            maas_kesintisi = gunluk_maliyet * gelmedigi_gun
            ana_hakedis = float(personel.maas_tutari) - maas_kesintisi
        else:
            ana_hakedis = float(personel.maas_tutari) * calistigi_gun

        tum_hareketler = FinansalHareket.objects.filter(personel=personel, tarih__year=yil, tarih__month=ay).order_by('tarih')
        primler_listesi = tum_hareketler.filter(islem_tipi='prim')
        toplam_prim = primler_listesi.aggregate(Sum('tutar'))['tutar__sum'] or 0
        
        kesintiler_listesi = tum_hareketler.exclude(islem_tipi='prim')
        diger_kesintiler = kesintiler_listesi.aggregate(Sum('tutar'))['tutar__sum'] or 0
        
        taksitler = TaksitliAvans.objects.filter(personel=personel, tamamlandi=False)
        taksit_kesintisi = taksitler.aggregate(Sum('aylik_kesinti'))['aylik_kesinti__sum'] or 0

        toplam_kesinti = float(diger_kesintiler) + float(taksit_kesintisi)
        net_maas = ana_hakedis + mesai_ucreti + float(toplam_prim) - toplam_kesinti

    return render(request, 'core/personel_pusula.html', {
        'personel': personel,
        'ay': ay,
        'yil': yil,
        'ay_adi': calendar.month_name[ay],
        'calistigi_gun': calistigi_gun,
        'gelmedigi_gun': gelmedigi_gun,
        'ana_hakedis': ana_hakedis,
        'toplam_mesai': toplam_mesai,
        'mesai_ucreti': mesai_ucreti,
        'primler_listesi': primler_listesi,
        'toplam_prim': toplam_prim,
        'kesintiler_listesi': kesintiler_listesi,
        'taksitler': taksitler,
        'taksit_kesintisi': taksit_kesintisi,
        'toplam_kesinti': toplam_kesinti,
        'net_maas': net_maas
    })

@login_required
def giris_cikis_raporu(request):
    bugun = timezone.now().date()
    try:
        yil = int(request.GET.get('yil', bugun.year))
        ay = int(request.GET.get('ay', bugun.month))
    except ValueError:
        yil = bugun.year
        ay = bugun.month

    personeller = Personel.objects.filter(aktif_mi=True)
    secilen_personel_id = request.GET.get('personel_id')

    kayitlar = Puantaj.objects.none()

    if secilen_personel_id:
        kayitlar = Puantaj.objects.filter(
            tarih__year=yil,
            tarih__month=ay,
            personel_id=secilen_personel_id
        ).select_related('personel').order_by('tarih')
        
        try:
            secilen_personel_id = int(secilen_personel_id)
        except ValueError:
            secilen_personel_id = None

    return render(request, 'core/giris_cikis_raporu.html', {
        'kayitlar': kayitlar,
        'yil': yil,
        'ay': ay,
        'ay_adi': calendar.month_name[ay],
        'personeller': personeller,
        'secilen_personel_id': secilen_personel_id
    })

@login_required
def giris_cikis_raporu_indir(request):
    bugun = timezone.now().date()
    try:
        yil = int(request.GET.get('yil', bugun.year))
        ay = int(request.GET.get('ay', bugun.month))
    except ValueError:
        yil = bugun.year
        ay = bugun.month

    secilen_personel_id = request.GET.get('personel_id')
    kayitlar = Puantaj.objects.none()

    if secilen_personel_id:
        kayitlar = Puantaj.objects.filter(
            tarih__year=yil,
            tarih__month=ay,
            personel_id=secilen_personel_id
        ).select_related('personel').order_by('tarih')
    
    data = []
    for k in kayitlar:
        giris = k.giris_saati.strftime('%H:%M') if k.giris_saati else '-'
        cikis = k.cikis_saati.strftime('%H:%M') if k.cikis_saati else '-'
        data.append({
            'Tarih': k.tarih.strftime('%d.%m.%Y'),
            'Gün': k.tarih.strftime('%A'),
            'Personel': f"{k.personel.ad} {k.personel.soyad}",
            'Durum': k.get_durum_display(),
            'Giriş Saati': giris,
            'Çıkış Saati': cikis,
            'Mesai (Saat)': k.hesaplanan_mesai_saati
        })

    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        sheet_name = f'Giris_Cikis_{ay}_{yil}'
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Giris_Cikis_Raporu_{ay}_{yil}.xlsx"'
    return response