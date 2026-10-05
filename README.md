# goldtradingbot

Sadece altın (XAU/USD) işlem yapan, haber takipli ve **önce sermayeyi koruyan** otomatik işlem botu. Kendi stratejisini her hafta gerçek veride yeniden test ediyor ve sonuçları bu repoya commit ediyor.

> ⚠️ **Önce bunu oku.** Kaldıraçlı ürünlerde perakende hesapların çoğu para kaybeder. Bu bot kâr garantisi vermez. Gerçek veri testleri ([STRATEGY.md](docs/STRATEGY.md)) 100$ → 1.000.000$ hedefinin gerçekçi olmadığını gösteriyor: 5× kaldıraçta iflas olasılığı %45. Bot varsayılan olarak **sanal parayla** çalışır. Gerçek para için iki ayrı bilinçli adım gerekir. Yatırım tavsiyesi değildir.

## Mevcut durum (Ekim 2026)

| | |
|---|---|
| **Strateji** | Saatlik kırılım. Rastgele girişlere karşı anlamlı (p ≈ 0, iki ayrı veri serisinde), ama parametreler aynı dönemde seçildi. **İleriye dönük test sürüyor.** |
| **Nerede çalışır** | Sadece düşük maliyetli **SPK lisanslı MT5 CFD**'de. VİOP'ta avantaj kayboluyor, token borsalarında zarar ediyor. Bot pahalı platformda işlem açmayı reddeder. |
| **100$ için öneri** | Kaldıraçsız altın tut (`goldbot core`), botu demo hesapta test et. Ayrıntı: [STRATEGY.md §5](docs/STRATEGY.md). |
| **Canlıya geçiş şartı** | İleriye dönük testte ≥100 işlem, kâr faktörü ≥1,2, düşüş ≤%15, ≥60 gün. Kontrol için: `goldbot status`. |

## Ne yapar?

| Katman | İçerik |
|---|---|
| **Strateji** | Beş giriş ailesi (`goldbot/strategies/`): kırılım, sıkışma, gece seansı, haber şoku, ortalamaya dönüş. Hepsi aynı çıkış ve risk kurallarını paylaşır; performansa göre seçen bir ensemble hangisinin işlem açacağına karar verir. Varsayılan: sadece kırılım, çünkü diğerleri henüz gerçek veride kanıtlanmadı. Parametreler: `config/params.yaml`. |
| **Stop / kâr al** | Her emirde zorunlu ATR stop'u ve R-katı kâr hedefi. 1R kârdan sonra iz süren stop devreye girer. Stoplar **broker tarafında** durur; stopsuz emir kodda reddedilir. |
| **Risk** | <ul><li>İşlem başına %1 risk</li><li>Günlük %3 zarar limiti</li><li>Zirveden %20 düşüşte kalıcı durdurma</li><li>Azami 10:1 kaldıraç (SPK)</li><li>En fazla 1 pozisyon, günde en fazla 4 işlem</li><li>Maliyet koruması: işlem maliyeti riskin %5'ini aşarsa işlem açılmaz</li></ul>Tüm limitler yeniden başlatmada **korunur**. |
| **Haber** | <ul><li>10 doğrulanmış RSS kaynağı, isteğe bağlı Finnhub ve Telegram kanalları</li><li>Altına özel duygu skoru (Türkçe dahil); güçlü ters habere karşı veto</li><li>CPI, NFP ve FOMC'nin ±30 dakikasında yeni işlem yok</li></ul> |
| **Broker** | `paper` (varsayılan), `mt5` (demo veya canlı), `ccxt` (tokenize altın; işlem için önerilmez) |
| **Takip** | <ul><li>İşlem defteri ve equity kaydı (`state/<mod>/`)</li><li>`status` ile canlıya geçiş kontrol listesi</li><li>HTML rapor</li><li>Telegram bildirimleri ve uzaktan kontrol: `/status /forward /pause /resume /closeall`</li></ul> |
| **Otomatik döngüler** | Haftalık parametre testi ve ileriye dönük test raporu, aylık araştırma ve doğrulama. Hepsi branch → commit → PR → test → merge şeklinde çalışır ([aşağıda](#otomatik-döngüler)). |

## Hızlı başlangıç

```bash
git clone https://github.com/furkycl/goldtradingbot && cd goldtradingbot
python -m venv .venv && source .venv/bin/activate      # Windows: scripts\windows\setup.bat
pip install -r requirements.txt && pip install -e .     # `goldbot` komutu da kurulur
cp .env.example .env                                     # Telegram vb. (asla commit etme)
pytest -q
python -m goldbot run                                    # sanal işlem
```

Docker, Windows + MT5 demo ve Linux servis kurulumu: **[docs/DEPLOY.md](docs/DEPLOY.md)**

## Komutlar

```bash
python -m goldbot run                    # paper / demo / live (settings.yaml > mode)
python -m goldbot status                 # ileriye dönük test ve canlıya geçiş kontrol listesi
python -m goldbot report --mode paper    # state/paper/report.html
python -m goldbot core                   # kaldıraçsız altın: trend ve zirveden uzaklık
python -m goldbot news                   # güncel başlıklar ve duygu skoru
python -m goldbot probe-feeds            # haber kaynakları canlı mı?
python -m goldbot backtest --yf --equity 10000
python -m goldbot reset-halt             # kalıcı durdurmayı temizle (botu durdurup inceledikten sonra)
python -m goldbot telegram-login         # Telegram kanallarını okumak için bir kerelik giriş
python scripts/validate.py               # tam istatistiksel doğrulama (internet gerekir)
python scripts/compare_strategies.py     # strateji aileleri ve ensemble karşılaştırması
```

## Gerçek parayla işleme geçmek (bunu sadece sen yapabilirsin)

1. `goldbot status` komutu demo veya paper testte **"criteria met"** desin.
2. `config/settings.yaml`: `mode: live`, `broker: mt5` (SPK lisanslı kurum).
3. Botun çalıştığı makinede: `GOLDBOT_LIVE_CONFIRM="I UNDERSTAND I CAN LOSE ALL MY MONEY"`

Bu adımların hepsi olmadan bot paper modda kalır. Otomatik döngüler bu ayarlara dokunamaz.

⚠️ **Lisanssız yurt dışı brokerlar gri alan değildir.** Türkiye'de yerleşik kişilere izinsiz kaldıraçlı hizmet SPKn md. 109/2 kapsamında suçtur. Bu repo bu kurumları desteklemez.

## Otomatik döngüler

| Workflow | Sıklık | Ne yapar | Neyi değiştirebilir |
|---|---|---|---|
| `self-improve.yml` | Her hafta | <ul><li>Walk-forward parametre araması</li><li>5 Ekim 2026 sonrası **mühürlü** veride ileriye dönük test</li><li>Her hafta rapor</li></ul> | `config/params.yaml`, ama sadece mühürlü veride ≥1000 mum varken ve aday orada da açıkça daha iyiyse |
| `research.yml` | Her ay | Strateji varyantları ve haber kaynağı kontrolü | sadece `reports/` |
| `validate.yml` | Her ay | <ul><li>Rastgeleye karşı test</li><li>Platform maliyetleri</li><li>2001–2026 günlük karşılaştırma</li><li>Monte Carlo</li></ul> | sadece `reports/` |
| `ci.yml` | Her değişiklikte | Lint, testler, Docker imajı | — |

Aşırı uyuma karşı önlemler:
- Optimizer tek aday seçer, bu aday dilimlerin en az 3/4'ünde kazanmak zorundadır. Rastgele veride sahte kabul oranı %5 (`scripts/null_test.py`).
- Mühürlü veri kontrolü bunun üstüne ayrıca uygulanır.
- `scripts/check_auto_diff.py`, otomatik branch'lerin kod, risk veya mod ayarlarını değiştirmesini engeller.

## Yapı

```
goldbot/
  strategy.py, strategies/       strateji aileleri + ortak filtreler; ensemble.py seçici
  risk.py                        lot hesabı, limitler, kalıcı durum
  backtest.py, optimize.py       maliyetli backtest, walk-forward + null-test kalibreli kabul
  engine.py                      canlı döngü (backtest ile aynı işlemleri üretir; testli)
  journal.py, forward.py         işlem defteri, ileriye dönük test, HTML rapor
  daily.py, core.py              günlük stratejiler, kaldıraçsız altın sinyali
  telegram_control.py            uzaktan kontrol
  news/                          RSS, Telegram, takvim, duygu skoru
  brokers/                       paper, mt5, ccxt
scripts/                         validate, self_improve, compare_variants, null_test, check_auto_diff, windows/
config/                          settings.yaml + validation.yaml (senin), params.yaml (döngünün), profiles/ (micro_100usd, aggressive)
docs/                            STRATEGY.md (karar), RESEARCH.md (kaynaklar), DEPLOY.md (kurulum)
reports/                         otomatik raporlar
```
