# -*- coding: utf-8 -*-
"""
YagiWeather hava sunucusu
konumlar.json'daki her yer icin hava verisini ceker, site/ altina JSON yazar.
GitHub Actions saat basi calistirir; ciktiyi GitHub Pages yayinlar.

Ciktinin bicimi Open-Meteo cevabiyla ayni tutuldu; boylece uygulamada
sadece adres degisiyor, ayristirma kodu aynen kaliyor.

Sadece standart kutuphane.
"""
import json
import math
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# Bazi aglarda IPv6 denemesi uzun suruyor; IPv4'e sabitliyoruz.
_adres_coz = socket.getaddrinfo


def _sadece_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _adres_coz(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _sadece_ipv4

TAHMIN = "https://api.open-meteo.com/v1/forecast"
HAVA_KALITE = "https://air-quality-api.open-meteo.com/v1/air-quality"
BASLIK = {"User-Agent": "YagiWeather/1.0 (kisisel hava uygulamasi)"}

# YagiWeather'in main.dart'ta istedigi degiskenlerin aynisi
SIMDI = ("temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m,is_day,"
         "precipitation,apparent_temperature,surface_pressure,uv_index,"
         "wind_direction_10m,visibility")
SAATLIK = ("temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m,"
           "is_day,precipitation_probability")
GUNLUK = ("temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max,"
          "relative_humidity_2m_max,relative_humidity_2m_min,sunrise,sunset,"
          "precipitation_sum,uv_index_max,precipitation_probability_max")

# Arka plan yagmur/kar bildirimi icin 15 dakikalik dilimler.
# (Turkiye'de bu veri saatlikten turetiliyor, uygulamadaki mevcut durumla ayni.)
DAKIKALIK = "weather_code,precipitation"
DAKIKALIK_ADET = 48                   # 48 x 15 dk = 12 saat ileri

GUN = 14
SAAT_DILIMI = "Europe/Istanbul"       # Turkiye tek dilim, yaz saati yok

# Katmanli yenileme: her saat her yeri cekmek gunluk siniri asiyor.
# Il merkezleri sik, ilceler seyrek yenilenir. Saat UTC'ye gore.
PERIYOT_TAHMIN = {"il": 1, "ilce": 6}      # kac saatte bir tahmin
PERIYOT_KALITE = {"il": 3, "ilce": 12}     # kac saatte bir hava kalitesi

TAHMIN_OBEK = 150      # tek istekteki konum sayisi (olcumde 200 calisti, pay biraktik)
KALITE_OBEK = 300
OBEK_BEKLE = 25        # saniye; dakikalik 600 sinirinin altinda kalmak icin
TEKRAR = 3

_sayac = {"konum": 0, "istek": 0, "429": 0, "hata": 0}


def _oku(url, zaman_asimi=180):
    """URL'yi cagirir, 429'da bekleyip tekrar dener."""
    son = None
    for d in range(TEKRAR):
        _sayac["istek"] += 1
        try:
            r = urllib.request.Request(url, headers=BASLIK)
            with urllib.request.urlopen(r, timeout=zaman_asimi) as c:
                return json.loads(c.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            son = f"HTTP {e.code}"
            if e.code == 429:
                _sayac["429"] += 1
                if d < TEKRAR - 1:
                    print(f"    429 - 65 sn bekleniyor (deneme {d+1})", flush=True)
                    time.sleep(65)
                    continue
            if d < TEKRAR - 1:
                time.sleep(10)
                continue
        except Exception as e:
            son = str(e)[:120]
            if d < TEKRAR - 1:
                time.sleep(10)
                continue
    _sayac["hata"] += 1
    raise RuntimeError(f"istek basarisiz: {son}")


def _liste(cevap, adet):
    """Open-Meteo tek konumda sozluk, coklu konumda liste donuyor. Listeye cevir."""
    if isinstance(cevap, list):
        return cevap
    return [cevap] if adet == 1 else []


def obekle(dizi, boy):
    for i in range(0, len(dizi), boy):
        yield dizi[i:i + boy]


def tahmin_cek(konumlar):
    """slug -> Open-Meteo tahmin cevabi"""
    sonuc = {}
    obekler = list(obekle(konumlar, TAHMIN_OBEK))
    for n, obek in enumerate(obekler, 1):
        lat = ",".join(str(k["lat"]) for k in obek)
        lon = ",".join(str(k["lon"]) for k in obek)
        url = (f"{TAHMIN}?latitude={lat}&longitude={lon}"
               f"&current={SIMDI}&hourly={SAATLIK}&daily={GUNLUK}"
               f"&minutely_15={DAKIKALIK}&forecast_minutely_15={DAKIKALIK_ADET}"
               f"&timezone={urllib.parse.quote(SAAT_DILIMI)}&forecast_days={GUN}")
        print(f"  tahmin obek {n}/{len(obekler)} ({len(obek)} konum)", flush=True)
        cevap = _liste(_oku(url), len(obek))
        if len(cevap) != len(obek):
            raise RuntimeError(f"beklenen {len(obek)} konum, gelen {len(cevap)}")
        for k, c in zip(obek, cevap):
            sonuc[k["slug"]] = c
        _sayac["konum"] += len(obek)
        if n < len(obekler):
            time.sleep(OBEK_BEKLE)
    return sonuc


def kalite_cek(konumlar):
    """slug -> european_aqi (bulunamazsa None). Hata olursa tum is durmasin."""
    sonuc = {}
    obekler = list(obekle(konumlar, KALITE_OBEK))
    for n, obek in enumerate(obekler, 1):
        lat = ",".join(str(k["lat"]) for k in obek)
        lon = ",".join(str(k["lon"]) for k in obek)
        url = f"{HAVA_KALITE}?latitude={lat}&longitude={lon}&current=european_aqi"
        print(f"  hava kalitesi obek {n}/{len(obekler)} ({len(obek)} konum)", flush=True)
        try:
            cevap = _liste(_oku(url), len(obek))
        except Exception as e:
            print(f"    hava kalitesi alinamadi, bos gecilecek: {e}", flush=True)
            cevap = []
        for i, k in enumerate(obek):
            deger = None
            if i < len(cevap):
                deger = (cevap[i].get("current") or {}).get("european_aqi")
            sonuc[k["slug"]] = deger
        _sayac["konum"] += len(obek)
        if n < len(obekler):
            time.sleep(OBEK_BEKLE)
    return sonuc


def yaz(yol, veri):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, separators=(",", ":"))
    return os.path.getsize(yol)


def main():
    kok = os.path.dirname(os.path.abspath(__file__))
    kaynak = os.path.join(kok, "konumlar.json")
    site = os.path.join(kok, "site", "v1")

    if not os.path.exists(kaynak):
        print(f"konumlar.json bulunamadi: {kaynak}")
        print("Once konumlar_kur.py calistirilmali.")
        return 1

    konumlar = json.load(open(kaynak, encoding="utf-8"))["konumlar"]
    saat = datetime.now(timezone.utc).hour
    hepsini_cek = "--hepsi" in sys.argv

    def dosya_yolu(slug):
        return os.path.join(site, "il", slug + ".json")

    # Vakti gelenleri ve dosyasi hic olmayanlari sec.
    # Onbellekten gelen eski dosyalar yerinde kalir, silinmez.
    tahmin_listesi, kalite_listesi, eksik = [], [], 0
    for k in konumlar:
        tur = k.get("tur", "il")
        yok = not os.path.exists(dosya_yolu(k["slug"]))
        if yok:
            eksik += 1
        pt = PERIYOT_TAHMIN.get(tur, 1)
        pk = PERIYOT_KALITE.get(tur, 3)
        if hepsini_cek or yok or saat % pt == 0:
            tahmin_listesi.append(k)
            if hepsini_cek or yok or saat % pk == 0:
                kalite_listesi.append(k)

    print(f"Toplam konum   : {len(konumlar)}")
    print(f"Saat (UTC)     : {saat}")
    print(f"Dosyasi yok    : {eksik}")
    print(f"Tahmin cekilecek      : {len(tahmin_listesi)}")
    print(f"Hava kalitesi cekilecek: {len(kalite_listesi)}\n", flush=True)

    basla = time.time()
    tahminler = tahmin_cek(tahmin_listesi) if tahmin_listesi else {}
    kaliteler = kalite_cek(kalite_listesi) if kalite_listesi else {}

    simdi = datetime.now(timezone.utc).isoformat(timespec="seconds")
    toplam_bayt = 0
    yazilan = 0
    korunan = 0
    def eski_aqi(slug):
        """Bu tur hava kalitesi cekilmediyse onceki degeri koru."""
        try:
            with open(dosya_yolu(slug), encoding="utf-8") as f:
                return json.load(f).get("aqi")
        except Exception:
            return None

    for k in konumlar:
        t = tahminler.get(k["slug"])
        if not t:
            # Bu tur yenilenmedi: onbellekten gelen dosya oldugu gibi kalsin.
            if os.path.exists(dosya_yolu(k["slug"])):
                toplam_bayt += os.path.getsize(dosya_yolu(k["slug"]))
                korunan += 1
            else:
                print(f"  UYARI: {k['ad']} icin veri yok")
            continue
        t["aqi"] = kaliteler[k["slug"]] if k["slug"] in kaliteler else eski_aqi(k["slug"])
        t["ad"] = k["ad"]
        t["slug"] = k["slug"]
        t["guncelleme"] = simdi
        toplam_bayt += yaz(dosya_yolu(k["slug"]), t)
        yazilan += 1

    # Uygulamanin en yakin yeri bulmak icin kullanacagi dizin
    dizin = [{"ad": k["ad"], "slug": k["slug"], "lat": k["lat"], "lon": k["lon"],
              "tur": k.get("tur", "il")} for k in konumlar]
    yaz(os.path.join(site, "konumlar.json"),
        {"surum": 1, "guncelleme": simdi, "konumlar": dizin})

    sure = time.time() - basla
    durum = {
        "surum": 1,
        "guncelleme": simdi,
        "konum_sayisi": yazilan + korunan,
        "yenilenen": yazilan,
        "onbellekten": korunan,
        "saat_utc": saat,
        "harcanan_konum_cagrisi": _sayac["konum"],
        "http_istegi": _sayac["istek"],
        "sinir_429": _sayac["429"],
        "hata": _sayac["hata"],
        "sure_saniye": round(sure, 1),
        "toplam_bayt": toplam_bayt,
    }
    yaz(os.path.join(site, "durum.json"), durum)

    print("\n" + "=" * 50)
    print(f"yenilenen dosya : {yazilan}")
    print(f"onbellekten     : {korunan}")
    print(f"toplam boyut    : {toplam_bayt/1024:.0f} KB")
    print(f"ortalama dosya  : {toplam_bayt/max(1,yazilan+korunan)/1024:.1f} KB")
    print(f"harcanan cagri  : {_sayac['konum']} konum / {_sayac['istek']} istek")
    print(f"429 sayisi      : {_sayac['429']}")
    print(f"sure            : {sure:.1f} sn")
    if yazilan + korunan < len(konumlar):
        print(f"UYARI: {len(konumlar)-yazilan-korunan} konum eksik")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
