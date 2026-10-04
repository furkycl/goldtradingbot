# Araştırma notları (Ekim 2026)

Bu notlar bilgi amaçlıdır, yatırım tavsiyesi değildir. Düzenlemeler ve ücretler değişir. Hesap açmadan önce kurumun güncel resmi sayfasını ve SPK listelerini kontrol et.

## 1. Türkiye'de yasal çerçeve

- **Kaldıraçlı FX/CFD (altın dahil):** SPK, Türkiye'de yerleşik kişiler için azami kaldıracı **10:1** olarak belirliyor ve işlem için asgari **50.000 TL** teminat şartı arıyor. Bu kurallar 2017'den beri yürürlükte. Kaynak: [Track360 SPK rehberi](https://track360.io/tr/blog/forex-kaldirac-nedir-rehberi-2026), [BloombergHT](https://www.bloomberght.com/spknin-foreks-duzenlemeleri-yururluge-girdi-1847688).
- **Yurt dışı lisanssız kurumlar:** SPK tarafından denetlenmezler. Sorun çıktığında Türk hukukunda başvuru yolun yok denecek kadar azdır. SPK izinsiz kaldıraçlı işlem siteleri hakkında düzenli olarak duyuru yapıyor ve erişim engeli getiriyor. Kaynak: [Paratic](https://paratic.com/spkdan-izinsiz-kaldiracli-islemler-hakkinda-duyuru/).
- **Kripto platformları:** 2024 tarihli düzenlemeyle kripto varlık hizmet sağlayıcıları SPK iznine tabi oldu. SPK, Türkiye'ye izinsiz hizmet vermeye devam eden 50'den fazla borsanın 108 sitesine erişim engeli getirdi. Kaynak: [Bengütürk](https://www.benguturk.com/ekonomi/spkden-izinsiz-kripto-para-borsalarina-erisim-engelinde-ilk-karar-176361h), [KPMG notu](https://kpmg.com/tr/tr/home/insights/2025/04/kripto-varlik-hizmet-saglayicilari-icin-rehber.html).
- **VİOP altın:** Borsa İstanbul'da USD/ons ve TL/gram altın vadeli sözleşmeleri işlem görüyor. Teminat oranı tipik olarak ~%10. Kaynak: [hisse.net](https://www.hisse.net/haber/vadeli-islemler-piyasasinda-altin-yatirimi-nasil-yapilir-28264).

## 2. Platform seçenekleri (100$ başlangıç açısından)

| Seçenek | Yasal durum (TR yerleşik) | 100$ ile uygulanabilir mi? | Bot entegrasyonu | Not |
|---|---|---|---|---|
| SPK lisanslı aracı kurum, XAUUSD (MT5) | ✅ | ❌ (asgari ~50.000 TL) | `mt5` adaptörü | En korumalı yol, maliyetleri karşılaştır |
| VİOP altın vadeli | ✅ | ❌ (teminat + kontrat büyüklüğü) | Kurumun API'si gerekir (bu repoda yok) | Borsa garantili, şeffaf |
| SPK izinli kripto platformunda PAXG/XAUT | ✅ (izinli platformsa) | ✅ kesirli miktar | `ccxt` adaptörü | Kaldıraçsız, sadece alış, token/ihraççı riski var |
| Yurt dışı offshore broker (raw spread) | ⚠️ SPK denetimi yok | Teknik olarak evet | `mt5` | En düşük spread burada ama koruma yok. Bu repo önermiyor |

Global raw-spread hesaplarda XAUUSD maliyeti tipik olarak lot başına ~6$ round-turn komisyon artı çok dar spread şeklinde ([FXEmpire 2026 karşılaştırması](https://www.fxempire.com/news/article/which-gold-xau-usd-trading-platforms-offer-low-spreads-and-low-trading-costs-top-5-brokers-compared-2026-1622410)). Backtest varsayılanları bu yüzden temkinli tutuldu: 7$/lot + 0,30$ spread.

## 3. Strateji araştırması — neden kırılım + trend?

- Altın piyasasında 4.000'den fazla zamanlama stratejisini test eden bir çalışmada, veri madenciliği düzeltmesinden sonra sadece hareketli ortalama ve momentum tabanlı **trend takip** stratejileri anlamlı kaldı. Mevsimsel ve temel analiz stratejileri elendi. Çalışmanın açıklaması: fiyat haberin etkisini kademeli olarak fiyatlıyor. Kaynak: [Quantpedia](https://quantpedia.com/an-extensive-test-of-market-timing-strategies-in-the-gold-market/).
- Yüzyıllık veride zaman serisi momentumu (trend takibi) emtialar dahil birçok varlık sınıfında tutarlı sonuç verdi. Kaynak: [A Century of Evidence on Trend-Following](https://www.TrendFollowing.com/whitepaper/Century_Evidence_Trend_Following.pdf), [Alpha Architect](https://alphaarchitect.com/time-series-momentum-aka-trend-following-the-historical-evidence/).
- **Haber filtresi:** Altının ana sürücüleri reel faizler, dolar, risk iştahı/jeopolitik ve merkez bankası alımları. Duygu sözlüğü bu sürücülere göre kuruldu. Haber kapanış çağrısı olarak değil, ters yöndeki işlemi engelleyen bir **veto** olarak kullanılıyor. Hızlı haber botları kurumsal düşük gecikmeli sistemlerle yarışamaz. Bu yüzden haberin rolü yön teyidi ve olay öncesi işlemden kaçınmak.

## 4. İncelenen açık kaynak projeler

- [GifariKemal/xaubot-ai](https://github.com/GifariKemal/xaubot-ai): MT5 + yapay zeka tabanlı XAUUSD botu.
- [zero-was-here/tradingbot](https://scour.ing/@hello/p/https://github.com/zero-was-here/tradingbot): XAUUSD için derin pekiştirmeli öğrenme (DRL) botu.

Ortak sorunlar ve bu repodaki karşılıkları:
- Backtest'te bir sonraki mumu görme (lookahead) → sinyal kapanışta, dolum sonraki açılışta. Testle doğrulanıyor.
- Maliyet ihmali → spread + komisyon her işlemde düşülüyor.
- Aşırı optimizasyon → sadece örneklem dışı walk-forward ile kabul ve iyileşme marjı.
- Stopsuz grid/martingale → kod seviyesinde yasak.
- Derin öğrenme modelleri → küçük veride aşırı uyum riski yüksek. İleride `optimize.py` arayüzüne eklenebilir, ama yalnızca aynı örneklem dışı kapıdan geçerse.

## 5. Gerçekçi beklenti

Saatlik trend sistemleri tipik olarak %35–50 kazanma oranıyla, birkaç büyük kazancın çok sayıda küçük kaybı telafi etmesiyle çalışır. Uzun düşüş dönemleri normaldir. İyi bir sistemde yıllık getiri genellikle düşük çift haneli yüzdelerdedir. 10.000 kat için bu oranlarla onlarca yıl gerekir. Kaldıracı artırarak bu süreyi kısaltmak iflas olasılığını kesinliğe yaklaştırır.
