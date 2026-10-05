# Kurulum ve sürekli çalıştırma

Bot üç modda çalışır: `paper` (sanal), `demo` (broker demo hesabı) ve `live` (gerçek para). Önerilen sıra **paper → demo → live** ([STRATEGY.md](STRATEGY.md) §5).

Hangi kurulumu seçeceğin modu ve brokeri belirler:

| Senaryo | Nerede çalışır | Kurulum |
|---|---|---|
| Paper (yfinance verisi) | Herhangi bir bilgisayar veya VPS | [A) Docker](#a-docker) ya da [C) Linux servis](#c-linux-vps-systemd) |
| **MT5 demo / canlı** (SPK lisanslı kurum) | **Windows** (MT5 terminali Windows'ta çalışır) | [B) Windows](#b-windows--metatrader-5) |

## Ortak ilk adımlar

1. `.env.example` dosyasını `.env` adıyla kopyala ve doldur. Bot bu dosyayı kendisi okur. `.env` asla commit edilmez.
2. `config/settings.yaml` içinde `mode` ve `broker` ayarlarını seç.
3. **Telegram (önerilir):**
   - @BotFather'dan bir bot oluştur ve `TELEGRAM_BOT_TOKEN` değerini al.
   - Bota bir mesaj yaz. Sonra `https://api.telegram.org/bot<TOKEN>/getUpdates` adresini açıp `chat.id` değerini bul ve `TELEGRAM_CHAT_ID` olarak gir.
   - Bot her işlemi telefonuna bildirir. Şu komutları dinler, sadece senin sohbetinden:
     - `/status`: anlık durum
     - `/forward`: ileriye dönük test sonucu
     - `/pause`, `/resume`: yeni işlemleri durdur / devam ettir
     - `/closeall yes`: tüm pozisyonları kapat

## A) Docker

```bash
git clone https://github.com/furkycl/goldtradingbot && cd goldtradingbot
cp .env.example .env          # doldur
docker compose up -d --build
docker compose logs -f
```

- `./state` klasörü kalıcıdır: risk durumu, işlem defteri ve loglar burada durur. Güncelleme sonrası da korunur. Klasör izinlerini konteyner kendisi düzeltir.
- Güncellemek için: `git pull && docker compose up -d --build`
- Sağlık kontrolü: Piyasa açıkken log 2 saatten uzun süre yazılmazsa konteyner "unhealthy" görünür. Hafta sonu bu kontrol yapılmaz.
- Komut çalıştırmak için: `docker compose run --rm goldbot status`

## B) Windows + MetaTrader 5

1. SPK lisanslı kurumdan **MT5 demo hesabı** aç ve MT5 terminalini kur.
2. Terminalde: Araçlar → Seçenekler → Uzman Danışmanlar → **"Algoritmik işlemlere izin ver"** seçeneğini aç.
3. Python 3.12'yi python.org'dan kur ("Add to PATH" kutusunu işaretle).
4. Repoyu indir ve `scripts\windows\setup.bat` dosyasını çalıştır. Bu adım sanal ortamı kurar, bağımlılıkları yükler ve testleri çalıştırır.
5. `.env` dosyasına `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` yaz.
6. `config\settings.yaml` dosyasında:
   ```yaml
   mode: demo
   broker: mt5
   broker_options:
     symbol: XAUUSD      # kurumundaki altın sembolü (GOLD, XAUUSD.m ...)
   ```
   - `commission_per_lot` ve `spread` değerlerini kurumunun gerçek değerleriyle güncelle.
   - Bot gerçek spread'i kendisi okur. Maliyet riskin %5'ini aşarsa işlem açmaz.
7. `scripts\windows\run.bat` ile başlat. Bot çökerse 30 saniye sonra kendini yeniden başlatır.
8. Windows açılışında otomatik başlaması için `scripts\windows\install_task.bat` dosyasını çalıştır.

`mode: demo` iken bot hesabın **gerçekten demo** olduğunu MT5'ten doğrular. Gerçek hesapsa çalışmayı reddeder.

## C) Linux VPS (systemd)

```bash
sudo useradd -m goldbot
sudo git clone https://github.com/furkycl/goldtradingbot /opt/goldtradingbot
sudo chown -R goldbot /opt/goldtradingbot && cd /opt/goldtradingbot
sudo -u goldbot python3 -m venv .venv
sudo -u goldbot .venv/bin/pip install -r requirements.txt telethon
sudo -u goldbot cp .env.example .env    # doldur
sudo cp deploy/goldbot.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now goldbot
journalctl -u goldbot -f
```

## Günlük kullanım

```bash
python -m goldbot status                 # ileriye dönük test ve canlıya geçiş listesi
python -m goldbot report --mode demo     # state/demo/report.html
python -m goldbot core                   # kaldıraçsız altın için trend durumu
python -m goldbot probe-feeds            # haber kaynakları çalışıyor mu
python -m goldbot reset-halt             # kalıcı zarar limiti tetiklendiyse: önce botu DURDUR, incele, sonra çalıştır
```

## Telegram kanallarından haber okumak (isteğe bağlı)

1. https://my.telegram.org adresinden `TELEGRAM_API_ID` ve `TELEGRAM_API_HASH` al ve `.env` dosyasına yaz.
2. `pip install telethon`
3. **Bir kez** etkileşimli giriş yap: `python -m goldbot telegram-login`. Telefon numaran ve gelen kod sorulur. Oturum `state/telegram/` içinde saklanır.
   - Docker'da: `docker compose run --rm goldbot telegram-login`
4. Kanallar `config/settings.yaml > news.telegram.channels` altında. Bot bu kanalları sadece okur.

## Aynı anda tek kopya

Bot her mod için bir kilit dosyası (`state/<mod>/goldbot.lock`) kullanır. Aynı modda ikinci bir kopya başlamayı reddeder. Bu yüzden `run.bat` ile Windows görevi gibi iki başlatma yolu yanlışlıkla aynı anda çalışırsa sorun çıkmaz.

## Canlıya geçiş (sadece sen)

`status` komutu "criteria met" demeden canlıya geçme. Geçiş için hepsi birlikte gerekli:

1. `mode: live`
2. Ortam değişkeni `GOLDBOT_LIVE_CONFIRM="I UNDERSTAND I CAN LOSE ALL MY MONEY"`
3. Gerçek hesap bilgileri

Paper, demo ve live kayıtları ayrı klasörlerde tutulur (`state/paper`, `state/demo`, `state/live`). Biri diğerinin risk limitini etkilemez.

## Güvenlik notları

- **Stoplar broker tarafında.** Bot veya bilgisayar kapansa bile açık pozisyonlar SL/TP ile korunur.
- **Kalıcı zarar limiti yeniden başlatmada sıfırlanmaz.** Sadece `reset-halt` komutuyla, bilgisayar başında temizlenir. Telegram'dan temizlenemez.
- **Anahtarlar:** `.env` dosyasını ve `*.session` dosyalarını kimseyle paylaşma. Broker API anahtarında para çekme yetkisi kapalı olsun.
