# Araştırma raporu — altın algoritmik işlem, Türkiye (4 Ekim 2026)

Bu rapor bilgi amaçlıdır, yatırım tavsiyesi değildir. Ücretler, listelemeler ve düzenlemeler sık değişir. Hesap açmadan önce kurumun güncel resmi sayfasını ve SPK listelerini kontrol et. **[DOĞRULANMADI]** işareti, birincil veya güncel bir kaynaktan teyit edilemeyen bilgileri gösterir.

İçerik:
1. [Yasal çerçeve](#1-yasal-çerçeve)
2. [Platformlar ve maliyetler](#2-platformlar-ve-maliyetler)
3. [Strateji araştırması](#3-strateji-araştırması)
4. [Haber kaynakları](#4-haber-kaynakları)
5. [Açık kaynak projeler](#5-açık-kaynak-projeler)
6. [Bu repoya yansıyanlar](#6-bu-repoya-yansıyanlar)

---

## 1. Yasal çerçeve

| Konu | Durum | Kaynak |
|---|---|---|
| Kaldıraçlı FX/CFD azami kaldıraç | **1:10.** Altın dahil tüm enstrümanlara uygulanıyor. 2017'den beri yürürlükte. 2025–2026'da değişiklik bulunamadı. | [QNB Invest duyurusu](https://www.qnbinvest.com.tr/forex/duyuru/spk-kaldirac-degisikligi-ve-yatirimci-hesaplarina-etkis), [Track360 2026](https://track360.io/tr/blog/forex-kaldirac-nedir-rehberi-2026) |
| Asgari teminat | **50.000 TL** veya karşılığı döviz | [GCM hesap sayfası](https://www.gcmyatirim.com.tr/hesap-islemleri/forex-gercek-yatirim-hesabi) |
| Lisanssız yurt dışı kurumlar | **Gri alan değil.** Yetkisiz hizmet SPKn md. 109/2 kapsamında suç (2–5 yıl hapis ve adli para cezası). Siteler erişime kapatılıyor. | [SPK basın duyurusu](https://spk.gov.tr/duyurular/basin-duyurulari/2023/izinsiz-kaldiracli-islemlere-iliskin-basin-duyurusu) |
| Kripto platformları | SPK'nın "faaliyette bulunanlar" listesi **geçici**. Listede olmak izin anlamına gelmiyor. Ekim 2026 itibarıyla nihai faaliyet izni alan bir platform bulunamadı. Bitexen'e 23 Eylül 2026'da yeni müşteri ve listeleme kısıtı getirildi. | [SPK listesi](https://spk.gov.tr/kurumlar/kripto-varlik-hizmet-saglayicilar/faaliyette-bulunanlar-listesi), [Forbes TR](https://www.forbes.com.tr/ekonomi/spk-dan-kripto-platformlarina-ek-sure-karari) |
| İzinsiz kripto borsaları | 50'den fazla borsanın 108 sitesine erişim engeli getirildi | [Bengütürk](https://www.benguturk.com/ekonomi/spkden-izinsiz-kripto-para-borsalarina-erisim-engelinde-ilk-karar-176361h) |

---

## 2. Platformlar ve maliyetler

### 2.1 SPK lisanslı aracı kurum + MT5 (50.000 TL ve üzeri)

| Kurum | MT5 | XAUUSD koşulları | Algo/EA | Kaynak |
|---|---|---|---|---|
| **QNB Invest** | ✅ | 1 lot = 100 ons, komisyonsuz (maliyet spread'de), spread yayımlanmamış | ✅ **EA açıkça destekleniyor** | [altın sayfası](https://www.qnbinvest.com.tr/forex/altin), [EA rehberi](https://www.qnbinvest.com.tr/forex/expert-advisor) |
| **GCM Yatırım** (G-039) | MT4 ağırlıklı, MT5 bazı ürünlerde | ECN: 1:10, piyasa spread'i + komisyon, 01:01–23:59 TR saati | Belirtilmemiş, sorulmalı | [ECN koşulları](https://www.gcmyatirim.com.tr/forex/islem-kosullari/ecn) |
| **İnfo Yatırım** | ✅ (2017'den beri) | [DOĞRULANMADI] | VİOP için Matriks IQ | [MetaQuotes](https://www.metaquotes.net/en/company/news/5019) |
| Garanti BBVA, Ak, Halk, A1, Integral, Destek, Osmanlı | [DOĞRULANMADI] | — | — | — |

Türkiye'deki lisanslı kurumlarda altın spread'i ons başına yaklaşık **0,35–0,60$** (ikincil kaynak, gösterge niteliğinde). Hesap açmadan önce spread, komisyon, asgari lot ve EA/API iznini **yazılı olarak** iste.

### 2.2 VİOP altın vadeli (Borsa İstanbul)

| | USD/ons (F_XAUUSD) | TL/gram (F_XAUTRYM) |
|---|---|---|
| Sözleşme büyüklüğü | 1 ons | **1 gram** |
| Başlangıç teminatı (Haziran 2026) | %10 → kontrat başına **~430$** | %14 → kontrat başına **~909 TL (~20$)** |
| Açık pozisyon (10 Haziran 2026) | ~80 bin | ~731 bin |
| İşlem saatleri | 09:30–18:10 + akşam seansı 19:00–23:00 | 09:30–18:10 |
| Örnek komisyon (GCM) | onbinde 5 + borsa ücretleri | onbinde 5 |
| Vade | Çift aylar, nakdi uzlaşma | Aynı. Referans LBMA PM fiyatı ve TCMB kuru. |

Kaynaklar: [BIST sözleşme özellikleri](https://borsaistanbul.com/piyasalar/viop/vadeli-islem-sozlesmeleri/kiymetli-maden-vadeli-islem-sozlesmeleri), [Gedik VİOP bülteni 10.06.2026](https://cdn.gedik.com/cdn/bulletin/2026/06/10/VIOP_Bulten_10062026_c65bee23.pdf), [GCM VİOP koşulları](https://www.gcmyatirim.com.tr/viop/viop-islem-kosullari)

**Algo erişimi:**
- **Matriks IQ:** C# ile strateji yazma, backtest ve optimizasyon ([İnfo](https://infoyatirim.com/islem-platformlari/matriks-matriks-iq)).
- **Deniz Yatırım:** ideAlgo ve Matriks terminalleri, HFT ve colocation ([Deniz](https://www.denizyatirim.com/AlgorithmicOperations)).
- **FIX:** kurumsal kullanıcılar için ([BIST](https://borsaistanbul.com/duyuru/12058/viopta-fix-protokolu-ile-emir-iletim-altyapisi-devreye-alindi)).
- **Python:** halka açık, doğrulanmış bir Python API bulunamadı. AlgoLab'ın durumu doğrulanamadı.

### 2.3 Tokenize altın (SPK listesindeki kripto platformları)

| Platform | Altın tokenı | API | ccxt | Not |
|---|---|---|---|---|
| **Paribu** | **XAUT/TL var** (canlı ticker'da doğrulandı) | ✅ Ekim 2025'te açıldı (HMAC) | ❌ | Komisyon tablosu doğrulanamadı |
| **BtcTurk** | ❌ PAXG ve XAUT yok | ✅ | ✅ `btcturk` | Altın tokenı listelenirse kullanılabilir |
| Binance TR, OKX TR | [DOĞRULANMADI] | — | `binancetr` modülü yok | — |
| Midas | PAXG fiyatı gösteriliyor, alım-satım [DOĞRULANMADI] | Yok | ❌ | — |
| Banka "dijital altın" hesapları | — | Yok | ❌ | Bot için uygun değil |

### 2.4 Global maliyet karşılaştırması (sadece referans)

- **Raw hesaplar:** lot başına ~6$ komisyon ve neredeyse sıfır spread ([FXEmpire](https://www.fxempire.com/news/article/which-gold-xau-usd-trading-platforms-offer-low-spreads-and-low-trading-costs-top-5-brokers-compared-2026-1622410)).
- **Ortalama spread:** 100'den fazla brokerın ortalaması ~0,32 ([BrokerChooser](https://brokerchooser.com/tr/broker-reviews/multibank-review/xauusd-spread)).
- Bu kurumlar SPK izni olmadan Türkiye'de yerleşik kişilere kaldıraçlı hizmet veremez.

### 2.5 Sermayeye göre öneri listesi

| Sermaye | 1. seçenek | 2. seçenek | Not |
|---|---|---|---|
| **~100$** | Sanal mod (paper) | VİOP gram altın (1–2 kontrat) | Gram kontratta bir kötü gün hesabı silebilir. Python API olmadığı için bu repo VİOP'a doğrudan emir gönderemez. |
| **100$, kaldıraçsız** | Paribu XAUT/TL (özel istemci gerekir) | — | Kaldıraçsız ve sadece alış yönlü. Tether ihraççı riski ve geçici lisans durumu var. |
| **50.000 TL ve üzeri** | QNB Invest MT5 (EA destekli) | GCM, İnfo | Bu repodaki `mt5` adaptörü doğrudan çalışır. |

---

## 3. Strateji araştırması

### 3.1 Kanıtların özeti

| Bulgu | Kanıt gücü | Kaynak |
|---|---|---|
| Altında 4.000'den fazla zamanlama kuralı içinden sadece **yavaş trend ve momentum** kuralları veri madenciliği düzeltmesinden sonra anlamlı kaldı (lookback 1–48 ay) | Güçlü | [Bartsch et al. — Quantpedia](https://quantpedia.com/an-extensive-test-of-market-timing-strategies-in-the-gold-market/) |
| Trend takibi 110 yıl boyunca neredeyse tüm vadeli piyasalarda çalıştı | Güçlü | [AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing?aqrPDF=1) |
| Tek bir 200 günlük ortalama, altında rejim ayırt etmede başarısız | Orta | [CXO](https://www.cxoadvisory.com/?p=15805) |
| Altın Asya saatlerinde yükselme, Batı saatlerinde düşme eğiliminde | Orta, maliyetten sonra zayıf | [Blose & Gondhalekar](https://ideas.repec.org/a/taf/apeclt/v21y2014i18p1269-1272.html), [CBS tezi](https://research.cbs.dk/en/studentProjects/gold-price-dynamics-around-the-clock/) |
| Hacim ve oynaklık Londra–New York çakışmasında (11–17 GMT) zirve yapıyor | Tanımlayıcı | [Batten et al. 2017](https://reading-clone.eprints-hosting.org/79175/1/BattenLuceyMcGroartyPeatUrquhart2017.pdf) |
| NFP, CPI ve FOMC oynaklığı sıçratıyor: önce aşırı tepki, sonra kısmi geri dönüş | Güçlü (birden fazla hakemli çalışma) | [Elder et al.](https://mountainscholar.org/handle/10217/206884), [Smales 2015](https://ideas.repec.org/a/eee/intfin/v34y2015icp161-172.html), [Gu et al. 2023](https://experts.umn.edu/en/publications/monetary-policy-and-uncertainty-resolution-in-commodity-markets/) |
| Reel faiz ile altın arasındaki ilişki 2022–2024'te merkez bankası alımları nedeniyle bozuldu | Orta | [Janus Henderson](https://www.janushenderson.com/en-it/advisor/article/chart-to-watch-whats-behind-the-divergence-between-gold-and-real-treasury-yields/) |
| COT pozisyon verileri getiriyi öngörmüyor | Negatif | [CXO](https://www.cxoadvisory.com/?p=21053) |
| Volatilite hedeflemesi emtialarda Sharpe'ı artırmıyor, sadece kuyruk riskini azaltıyor | Güçlü | [Man/Harvey et al.](https://www.man.com/insights/the-impact-of-volatility-targeting) |
| Fear & Greed endeksinin altın için öngörü gücü yok | Negatif | [UCC](https://cora.ucc.ie/items/07658b3c-0384-4f8d-911e-667b288a0c1b/full) |
| Başlık duygusu altında yönden çok **oynaklığı** etkiliyor | Orta | [Smales 2015](https://ideas.repec.org/a/eee/intfin/v34y2015icp161-172.html), [Sinha & Khandait](https://arxiv.org/abs/2009.04202) |

### 3.2 Uygulanan varyantlar (kanıt gücüne göre)

Hepsi `config/params.yaml` içinde ve varsayılan olarak **kapalı**. Gerçek veride hem normal hem 2 kat maliyetle örneklem dışında daha iyi çıkmadıkça açılmazlar (`scripts/compare_variants.py`, aylık `research.yml`).

| Kod | Varyant | Parametre | Kanıt |
|---|---|---|---|
| A | Günlük trend filtresi: sadece N günlük getiri yönünde işlem | `daily_trend_days`: 20/60/120 | Güçlü |
| C | Yüksek etkili ABD verilerinde yeni işlem yok | Canlıda `news_blackout_minutes` (zaten aktif) | Güçlü |
| B | Seans filtresi: sadece Londra–NY saatlerinde giriş | `session_start_utc` / `session_end_utc` | Orta |
| E | Zaman stopu: N mum sonra hâlâ +0,5 ATR kârda değilse çık | `max_hold_bars` | Zayıf |

Değerlendirilip **eklenmeyenler:** COT, gün-of-week, Fear & Greed, Londra fix zamanlaması, katı reel faiz filtresi. Sebebi kanıtın negatif ya da zayıf olması.

### 3.3 Uyarılar

- Yahoo Finance saatlik veride sadece ~730 gün veriyor. GC=F sürekli bir vadeli seri olduğu için vade geçişlerinde sıçrama yapıyor. Örneklem küçük, sonuçlara temkinli yaklaş.
- Filtreleri üst üste yığma. Her filtre işlem sayısını düşürür ve tesadüfi sonuç riskini artırır. Bu yüzden her varyant tek tek, baz çizgiye karşı test ediliyor.

---

## 4. Haber kaynakları

4 Ekim 2026'da her kaynak tek tek açılarak doğrulandı. Kendi makinende `python -m goldbot probe-feeds` ile tekrar kontrol edebilirsin. GitHub'daki aylık araştırma işi de aynı kontrolü yapıp `reports/feeds-*.txt` dosyasına yazıyor.

### 4.1 RSS akışları (varsayılan liste)

| Kaynak | URL | Not |
|---|---|---|
| FinancialJuice | `financialjuice.com/feed.ashx?xy=rss` | **Bulunan en hızlı ücretsiz kaynak**, squawk tarzı başlıklar |
| investingLive (eski ForexLive) | `investinglive.com/feed/news` | Veriler açıklandığı anda yayımlanıyor. Eski forexlive adresi buraya yönleniyor. |
| Investing — ekonomik göstergeler | `investing.com/rss/news_95.rss` | Veri açıklamaları |
| FXStreet | `fxstreet.com/rss/news` | Altın ve FX analizi |
| Investing — emtia | `investing.com/rss/news_11.rss` | |
| Fed para politikası | `federalreserve.gov/feeds/press_monetary.xml` | FOMC metinleri |
| Fed tüm duyurular | `federalreserve.gov/feeds/press_all.xml` | |
| ECB | `ecb.europa.eu/rss/press.html` | |
| BLS CPI / istihdam | `bls.gov/feed/cpi.rss`, `bls.gov/feed/empsit.rss` | Resmi kaynak, 08:30 ET'de güncelleniyor |
| MarketWatch | `feeds.content.dowjones.io/public/rss/mw_topstories` | |
| Bloomberg HT | `bloomberght.com/rss` | Türkçe |

**Çalışmayan veya kaldırılanlar:**
- Kitco (RSS yok), Bloomberg (404), BullionVault (404), gold.org (404).
- CNBC (403) ve FT bot erişimini engelliyor.
- Reuters 2020'de RSS'i kapattı.
- Yahoo, Nasdaq ve Investing TR akışları güncellenmiyor.

### 4.2 Takvim ve API'ler

- **ForexFactory JSON** (`nfs.faireconomy.media/ff_calendar_thisweek.json`): çalışıyor. Blackout için kullanılıyor. Açıklanan değerleri içermiyor.
- **FOMC 2026 kalan toplantılar:** 27–28 Ekim, 8–9 Aralık ([Fed](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)).
- **Finnhub:** ücretsiz anahtarla dakikada ~60 istek, sadece kişisel kullanım. `FINNHUB_KEY` tanımlanırsa otomatik kullanılır.
- **Alpha Vantage:** günde 25 istek, yeterli değil. **NewsAPI:** 24 saat gecikmeli, uygun değil.

### 4.3 Telegram kanalları

| Kanal | İçerik | Durum |
|---|---|---|
| @WalterBloomberg | Ajans tarzı, büyük harfli başlıklar | ✅ Aktif, ~32 bin abone. En iyi ücretsiz kaynak. |
| @financialjuice | RSS ile aynı başlıklar, anlık bildirim | ✅ |
| @BreakingMarketNews | OPEC, jeopolitik, merkez bankaları | ✅ |
| @disclosetv | Jeopolitik son dakika | ✅ Hızlı ama güvenilirliği karışık |
| @WatcherGuru | Hızlı ama sansasyonel | Sadece ikincil kaynak olarak |
| @investingcom, @AAekonomi | — | ❌ **Resmi değil, uzak dur** |

⚠️ "Sinyal", "VIP" veya "hesap yönetimi" sunan altın kanallarının neredeyse tamamı sinyal satıcısı. Bot bu tür kanalları kullanmıyor.

CPI, NFP ve FOMC'de ücretsiz kaynaklar kurumsal hızla yarışamaz. Bu yüzden bot o anlarda işlem açmıyor (blackout).

---

## 5. Açık kaynak projeler

| Repo | Yaklaşım | Alınan fikir | Kırmızı bayrak |
|---|---|---|---|
| [EA_SCALPER_XAUUSD](https://github.com/francomascareloai/EA_SCALPER_XAUUSD) | MQL5 + NautilusTrader | Doğrulama listesi: walk-forward, Monte Carlo, maliyet/slipaj, martingale yasağı | Kurallar gizli |
| [xaubot-ai](https://github.com/GifariKemal/xaubot-ai) | XGBoost + rejim + MT5 | Seans ve spread filtresi, günlük ve toplam zarar limitleri | 13 ayda Sharpe 4,8 iddiası. Büyük olasılıkla aşırı uyum. 14 filtre üst üste. |
| [zero-was-here/tradingbot](https://github.com/zero-was-here/tradingbot) | PPO/DreamerV3 | Makro özellik fikirleri | Backtest'te maliyet yok, lookahead riski |
| [TradingAgents](https://github.com/TauricResearch/TradingAgents) | Çoklu LLM ajanı | Haberi filtre olarak kullanma mimarisi | Backtest yok, geçmişte lookahead hatası vardı |
| [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | LLM duygu analizi | FinBERT'ten iyi duygu skorları | 13B model, saatlik kullanım için ağır |

Ücretsiz duygu modelleri: [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert), [finbert-tone](https://huggingface.co/yiyanghkust/finbert-tone). Altın başlık veri seti: [SaguaroCapital](https://huggingface.co/datasets/SaguaroCapital/sentiment-analysis-in-commodity-market-gold) (ticari kullanım yasak).

---

## 6. Bu repoya yansıyanlar

- Varsayılan RSS listesi ve Telegram kanalları doğrulanmış kaynaklarla güncellendi.
- Finnhub desteği ve `probe-feeds` komutu eklendi.
- Strateji varyantları A, B ve E eklendi (kapalı). Aylık araştırma işi bunları gerçek veride normal ve 2 kat maliyetle test edip `reports/variants-*.md` dosyasına yazıyor.
- PAXG profiline listeleme bulguları eklendi. Varsayılan borsa kaldırıldı, seçim zorunlu.
- Kalan işler:
  - Paribu XAUT/TL için özel istemci. Resmi API dokümanı doğrulanınca yazılacak; gerçek parayla dokümansız istemci yazılmaz.
  - VİOP için Python köprüsü. Kurum bir API sağlarsa eklenecek.
  - Geçmiş haber verisiyle duygu skorunun backtest'i. Saat damgalı haber arşivi gerekiyor.
