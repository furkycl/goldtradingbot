# Değişiklik günlüğü

## 0.4.0 — 6 Ekim 2026
- Çoklu pozisyon modu (aile başına bir, ters yön yasak, toplam açık risk tavanı); motor/backtest eşitliği testli.
- Güven skoru (trend, günlük trend, haber yönü, seans, oynaklık, uzama, aile uyumu): her bildirimde görünür; kademeli lot büyüklüğü isteğe bağlı.
- Sermaye merdiveni: bakiyeye göre risk (`risk_ladder`, kod tavanı %3) ve işlem tavanı (`trading_cap`) + Telegram "çekirdeğe taşı" uyarısı.
- `doctor` komutu: neyin ayarlı, neyin eksik olduğunu listeler.
- MT5: emir sonrası stop sunucuda doğrulanır; koyulamazsa pozisyon anında kapatılır.
- Gerçek veri hükümleri (STRATEGY.md §8): kademeli risk, kovalamama filtresi, 2–3 pozisyon ve dokunuşla giriş **risk-ayarlı getiriyi iyileştirmedi** → varsayılanlar değişmedi (1 pozisyon, %1 risk, kapanış teyidi).
- Workflow yayınlama tek betikte, adım adım hata annotation'ı.

## 0.3.0 — 5 Ekim 2026
- Strateji kütüphanesi: kırılım, sıkışma, gece seansı, haber şoku, ortalamaya dönüş; ortak çıkış ve risk kuralları.
- Performansa göre seçen ensemble (yedeğe alma, yön çatışmasında bekleme, kalıcı skor).
- Aile başına zorunlu çıkış; isteğe bağlı ATR'ye göre ölçeklenen risk.
- `scripts/compare_strategies.py` ve aylık çalıştırma: rastgeleye karşı p-değeri, 2× maliyet, walk-forward, aile bazında katkı.
- 100$ (mikro hesap) ve agresif (%2 risk) profilleri, iflas matematiğiyle.
- Motor ile backtest ensemble dahil kuruşu kuruşuna aynı (testli).

## 0.2.1 — 5 Ekim 2026
İkinci bağımsız inceleme bulguları:
- Gizli anahtarlar loglarda maskeleniyor.
- `/pause` ve izlenen pozisyonlar yeniden başlatmada korunuyor; bot kapalıyken kapanan işlemler deftere yazılıyor.
- Telegram: birikmiş komutlar çalıştırılmıyor; sahip kontrolü gönderen kimliğiyle yapılıyor.
- Tek kopya kilidi; `reset-halt` bot çalışırken reddediliyor.
- ccxt: borsa tarafı stop zorunlu; sadece botun aldığı miktar yönetiliyor.
- MT5: sunucu saati UTC'ye çevriliyor; demo hesap her emirde kontrol ediliyor.
- Canlı motor ile backtest kuruşu kuruşuna aynı (testli).
- Mühürlü test verisi her kabulden sonra yeniden başlıyor; doğrulama raporu mühürlü veriye bakmıyor.
- Otomatik main'e yazma yolunda test ve tekrar deneme eklendi.
- Docker: volume izinleri ve hafta sonuna duyarlı sağlık kontrolü.

## 0.2.0 — 5 Ekim 2026

**Doğrulama ve güvenilirlik**
- Bağımsız kod incelemesi bulguları düzeltildi:
  - Optimizer rastgele veride %45 sahte iyileşme kabul ediyordu; artık %5.
  - Walk-forward dilimlerinin ısınma çubukları işlem açabiliyordu; düzeltildi.
  - Mühürlü test verisi tarihe sabitlendi.
- Canlı motor ile backtest artık aynı işlemleri üretiyor; bu bir testle kontrol ediliyor.
- Swap (finansman) maliyeti ve platforma özel maliyet testleri eklendi.
- `scripts/validate.py`: rastgele girişe karşı test, parametre komşuluğu, PAXG çapraz kontrolü, 2001–2026 günlük karşılaştırma, Monte Carlo.
- `docs/STRATEGY.md`: veriye dayalı strateji kararı ve aşamalı plan.

**Canlı çalışma**
- Risk durumu (kalıcı durdurma, günlük limit) yeniden başlatmada korunuyor. Temizlemek için `reset-halt`.
- İşlem defteri, equity kaydı, `status` (canlıya geçiş listesi), HTML rapor, `core` sinyali.
- Maliyet koruması: pahalı platformda işlem açılmıyor.
- `demo` modu: MT5 demo hesabı doğrulanmadan işlem yok.
- Telegram uzaktan kontrol.
- Veri akışı bekçisi (watchdog), düzgün kapanma, log dosyası.
- `.env` dosyası artık gerçekten okunuyor.

**Kurulum ve kalite**
- Docker/compose, Windows + MT5 betikleri, systemd servisi.
- Ruff lint, Dependabot, internet gerektirmeyen haber testleri, CI'da Docker imajı derleme.

## 0.1.0 — 4 Ekim 2026
- İlk sürüm: strateji, risk yöneticisi, backtest, walk-forward optimizasyon, haber duygu skoru, paper/MT5/ccxt brokerları, haftalık kendini geliştirme döngüsü, araştırma raporu.
