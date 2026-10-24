# hava — YagiWeather veri sunucusu

Türkiye'nin 81 ili ve 917 ilçesi için hava tahmini verisini hazırlayıp statik
JSON olarak yayınlar. [YagiWeather](https://github.com/7kym-ship-it) mobil
uygulaması verisini buradan alır.

Adres: **https://7kym-ship-it.github.io/hava/v1/**

## Yapı

| Dosya | İçerik |
|---|---|
| `v1/konumlar.json` | Konum dizini — ad, slug, koordinat, tür (il/ilçe) |
| `v1/il/<slug>.json` | Bir konumun verisi: anlık durum, 14 günlük saatlik tahmin, 14 günlük özet, 12 saatlik 15 dakikalık tahmin, hava kalitesi |
| `v1/durum.json` | Son çalışmanın raporu — kaç konum yenilendi, kaç çağrı harcandı, ne kadar sürdü |

## Yenileme düzeni

GitHub Actions saat başı çalışır. Her şeyi her saat yenilemek veri
sağlayıcısının günlük sınırını aştığı için katmanlı çalışır:

| | tahmin | hava kalitesi |
|---|---|---|
| İl merkezleri (81) | her saat | 3 saatte bir |
| İlçeler (917) | 6 saatte bir | 12 saatte bir |

Günlük toplam yaklaşık 8.100 çağrı. O saat yenilenmeyen dosyalar Actions
önbelleğinden taşınır, böylece sitede her zaman 998 konumun tamamı bulunur.

## Betikler

| Dosya | İşi |
|---|---|
| `hava.py` | Asıl boru hattı. Actions bunu çalıştırır. |
| `konumlar_kur.py` | 81 ilin koordinatını bir kez çözer. |
| `ilceler_kur.py` | GeoNames verisinden 917 ilçeyi çıkarır. |
| `olcum.py` | Toplu istek sınırını ölçer. |

## Veri kaynakları ve lisans

Hava tahmini verisi **Open-Meteo** üzerinden alınmaktadır:

> Weather data by [Open-Meteo.com](https://open-meteo.com/)
> Lisans: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

Konum listesi **GeoNames** verisinden üretilmiştir:

> [GeoNames](https://www.geonames.org/)
> Lisans: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

**Değişiklik bildirimi:** Veriler olduğu gibi yeniden yayınlanmamaktadır.
Türkiye sınırlarına süzülmüş, uygulamanın kullandığı değişkenlerle
sınırlanmış, saatlik olarak önbelleklenmiş ve konum başına ayrı dosyalara
bölünmüştür.
