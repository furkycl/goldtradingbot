# goldtradingbot

Sadece altın (XAU/USD) işlem yapan, haber takipli, **önce sermayeyi koruyan** otomatik işlem botu.

> ⚠️ **Önce bunu oku.** Kaldıraçlı ürünlerde perakende hesapların çoğu para kaybeder. Bu bot kâr garantisi vermez. 100$ → 1.000.000$ (10.000 kat) hedefine "kontrollü" biçimde ulaştıracak bir strateji yoktur. Bu kadar agresif bir hedefi zorlamak hesabı sıfırlamanın en kısa yoludur. Bot bu yüzden varsayılan olarak **sanal parayla (paper)** çalışır. Gerçek parayla işlem yapmak için iki ayrı bilinçli adım gerekir (aşağıda). Yatırım tavsiyesi değildir.

## Ne yapar?

| Katman | İçerik |
|---|---|
| **Strateji** | Donchian kırılımı + EMA trend filtresi + ADX (yatay piyasada işlem yok). Sinyal mum kapanışında üretilir, emir bir sonraki mumda açılır (geleceği görme hatası yok). |
| **Stop / kâr al** | Her emirde zorunlu ATR stop'u, R-katı kâr hedefi ve 1R kârdan sonra ATR iz süren stop. Stop **broker tarafında** emirle birlikte gönderilir, bot çökse bile pozisyon korunur. Stopsuz emir kod seviyesinde reddedilir. |
| **Risk** | İşlem başına %1 risk, günlük %3 zarar limiti (o gün durur), zirveden %20 düşüşte kalıcı kill switch, en fazla 10:1 kaldıraç (SPK sınırı), en fazla 1 açık pozisyon, günde en fazla 4 işlem. |
| **Haber** | Doğrulanmış 12 RSS akışı (FinancialJuice, investingLive, Investing, FXStreet, Fed, ECB, BLS, MarketWatch, Bloomberg HT), isteğe bağlı Finnhub API, Telegram kanalları (Telethon ile okuma) ve altına özel duygu skoru (Fed/faiz, dolar, jeopolitik, enflasyon, merkez bankası alımları; Türkçe başlıklar dahil). Güçlü haber eğilimine ters işlem veto edilir. Yüksek etkili ABD verilerinin (CPI, NFP, FOMC) ±30 dakikasında yeni işlem açılmaz. |
| **Broker** | `paper` (varsayılan) · `mt5` (MetaTrader 5, çoğu SPK lisanslı kurumun sunduğu platform) · `ccxt` (PAXG gibi tokenize altın, küçük hesaplar için) |
| **Araştırma** | Aylık GitHub Actions işi: kanıta dayalı strateji varyantlarını (günlük trend, seans, zaman stopu) gerçek veride normal ve 2× maliyetle test eder, haber akışlarını kontrol eder, raporu `reports/` altına yazar. |
| **Kendini geliştirme** | Haftalık GitHub Actions döngüsü: güncel veriyle walk-forward optimizasyon → yeni parametreler örneklem dışında mevcutları geçerse ve güvenlik eşiklerini aşarsa → `auto/tune-*` branch'i, commit, PR → testler geçerse otomatik merge. |
| **Bildirim** | Açılan/kapanan her işlem Telegram'dan telefonuna (isteğe bağlı). |

## 100$ ile gerçek durum

Standart XAUUSD'de en küçük işlem 0,01 lot = 1 ons. Saatlik grafikte tipik stop mesafesi ons başına ~15–30$. 100$'lık hesapta bu, **tek işlemde hesabın %15–30'unu riske atmak** demek. Risk yöneticisi bunu reddeder. Backtest'te 100$ ile 273 sinyalin tamamı "lot çok büyük" diye atlanıyor. Bu bir hata değil, koruma.

Seçenekler (ayrıntılar `docs/RESEARCH.md` §2):
1. **Sanal parayla başla** (varsayılan). Stratejinin gerçek veride ne yaptığını 2-3 ay izle.
2. **VİOP gram altın (F_XAUTRYM):** 1 kontrat = 1 gram, teminat ~900 TL. Lisanslı ve borsada işlem gören, küçük sermaye için en temiz kaldıraçlı yol. Eksikleri: sadece gündüz seansı var, kur riski taşıyor ve halka açık bir Python API yok (Matriks IQ / ideAlgo gerekiyor).
3. **Tokenize altın, kaldıraçsız:** `config/profiles/small_account_paxg.yaml`. Ekim 2026 itibarıyla BtcTurk'te PAXG/XAUT yok. Paribu'da XAUT/TL var ama ccxt desteği yok. Platformlar SPK'nın geçici listesinde, nihai lisans yok.
4. **50.000 TL ve üzeri:** SPK lisanslı kurum ve MT5 (ör. QNB Invest EA'ları açıkça destekliyor). `mt5` adaptörü doğrudan çalışır.

⚠️ **Lisanssız yurt dışı brokerlar gri alan değildir.** Türkiye'de yerleşik kişilere izinsiz kaldıraçlı hizmet SPKn md. 109/2 kapsamında suçtur. Bu repo bu kurumları desteklemez.

Ayrıntılı karşılaştırma: [`docs/RESEARCH.md`](docs/RESEARCH.md)

## Kurulum

```bash
git clone https://github.com/furkycl/goldtradingbot && cd goldtradingbot
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # anahtarları doldur (asla commit etme)
pytest -q                                                # tüm testler geçmeli
```

## Kullanım

```bash
python -m goldbot backtest --yf --equity 10000   # gerçek altın verisiyle (Yahoo GC=F, 2 yıl saatlik)
python -m goldbot backtest --csv data/xauusd_h1.csv
python -m goldbot optimize --yf --trials 60       # walk-forward arama, sonucu yazdırır
python -m goldbot news                            # güncel başlıklar + duygu skoru + blackout durumu
python -m goldbot probe-feeds                     # haber akışları çalışıyor ve güncel mi?
python scripts/compare_variants.py                # araştırma varyantlarını gerçek veride karşılaştır
python -m goldbot run                             # sanal (paper) işlem döngüsü
```

## Gerçek parayla işleme geçmek (bunu sadece sen yapabilirsin)

1. En az birkaç ay paper modda sonuçları izle.
2. `config/settings.yaml` içinde `mode: live` ve `broker: mt5` (veya `ccxt`) yap.
3. Botun çalıştığı makinede şu ortam değişkenini **elle** tanımla:
   `GOLDBOT_LIVE_CONFIRM="I UNDERSTAND I CAN LOSE ALL MY MONEY"`

İkisi birden yoksa bot otomatik olarak paper moduna düşer. Kendini geliştirme döngüsü bu dosyaya ve değişkene **hiçbir zaman** dokunamaz. CI'daki `check_auto_diff.py` otomatik değişiklikleri sadece `config/params.yaml` ve `reports/` ile sınırlar.

MT5 için: Windows, `pip install MetaTrader5`, `.env` içinde `MT5_LOGIN/MT5_PASSWORD/MT5_SERVER`. Sembol adı kuruma göre değişebilir (`XAUUSD`, `GOLD`…), `broker_options.symbol` ile ayarla.

## Telegram

- **Haber okumak:** https://my.telegram.org'dan `TELEGRAM_API_ID/HASH` al ve `settings.yaml > news.telegram.channels` listesine güvendiğin herkese açık kanalları ekle. İlk çalıştırmada telefon numarası ve kod sorulur. Oturum dosyası `.gitignore`'dadır.
- **Bildirim almak:** @BotFather'dan bot oluştur, `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` gir.

Not: "Sinyal" satan Telegram kanallarının çoğu doğrulanamaz. Bot bu kanalları emir kaynağı olarak değil, sadece duygu skoruna katkı veren bir veri olarak kullanır.

## Kendini geliştirme döngüsü

`.github/workflows/self-improve.yml` her cumartesi 03:17 UTC'de (piyasa kapalıyken) çalışır:

1. Son 2 yılın saatlik altın verisini indirir.
2. Mevcut parametrelerin etrafında 60 aday dener (sadece ilk %60'lık eğitim verisinde).
3. En iyi adayları **görmedikleri** 4 walk-forward dilimde test eder.
4. Kabul şartları: medyan örneklem dışı skorda en az 0,10 iyileşme, en kötü düşüş ≤ %25, en az 8 işlem, kâr faktörü ≥ 1,1.
5. **Mühürlü test verisi:** En yeni %15'lik veri arama ve seçimde hiç kullanılmaz. Aday bu bölümde mevcut parametrelerden kötü sonuç verirse reddedilir. Böylece aynı veride tekrar tekrar optimizasyon yapmanın getirdiği aşırı uyum sınırlanır.
6. Kabul edilirse `auto/tune-YYYYMMDD-HHMM` branch'i açar, testleri çalıştırır, commit atar, PR açar ve squash-merge eder. Rapor `reports/` altına yazılır.

Actions'ın PR açma izni kapalıysa döngü, test edilmiş branch'i doğrudan `main`'e alır. Bu ayarı açmak zorunlu değil. İstersen açabilirsin: **Settings → Actions → General → Workflow permissions** → "Read and write permissions" ve "Allow GitHub Actions to create and approve pull requests".

## Yapı

```
goldbot/
  config.py        ayarlar, canlı mod kilidi
  indicators.py    EMA, ATR, ADX, Donchian
  strategy.py      sinyal + haber vetosu
  risk.py          lot hesabı, günlük limit, kill switch
  backtest.py      maliyetli, geleceği görmeyen backtest
  optimize.py      walk-forward arama + güvenlik eşikleri
  engine.py        canlı/paper döngüsü
  news/            RSS, Telegram, takvim, duygu skoru
  brokers/         paper, mt5, ccxt
scripts/           self_improve.py, check_auto_diff.py
config/            settings.yaml (senin), params.yaml (döngünün), profiles/
.github/workflows/ ci.yml, self-improve.yml
```
