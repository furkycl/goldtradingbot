# Strateji kararı: doğrulama sonuçları ve en mantıklı kâr yöntemi (5 Ekim 2026)

Bu belge `reports/validation-2026-10-05.md` raporundaki gerçek veri testlerine ve bağımsız bir kod incelemesine dayanıyor. Yatırım tavsiyesi değildir. Geçmiş performans geleceği garanti etmez.

## Özet

| Soru | Cevap |
|---|---|
| Saatlik kırılım stratejisinin gerçek bir avantajı var mı? | **Umut verici ama kanıtlanmadı.** Rastgele girişlerden belirgin şekilde iyi. Ancak parametreler aynı dönemde seçildi; kesin cevabı ileriye dönük test verecek. |
| Hangi platformda çalışır? | **Sadece düşük maliyetli CFD'de (SPK lisanslı MT5).** VİOP'ta avantaj neredeyse kayboluyor, token platformlarında zarar ediyor. |
| Uzun vadede en iyi yöntem ne? | **Kaldıraçsız altın tutmak.** 2001–2026'da yıllık ~%10,9. Trend zamanlaması getiriyi düşürüp düşüşü azaltıyor ama rastgele zamanlamadan iyi değil. |
| 100$ → 1.000.000$ mümkün mü? | **Gerçekçi değil.** En iyimser senaryoda bile 10 yılda olasılık ~%0–9. Kaldıracı artırmak iflas olasılığını hızla yükseltiyor. |

## 1. Saatlik strateji doğrulandı mı?

### Lehine kanıtlar
- **Rastgele girişlere karşı:** Çıkışları, lot hesabı ve maliyetleri aynı, ama giriş zamanı ve yönü rastgele olan 300 simülasyonla karşılaştırıldı. Gerçek strateji GC=F'de rastgelelerin hepsinden iyi çıktı (p ≈ 0): getiri +%58, rastgele medyan +%6.
- **İkinci enstrüman:** Parametreler GC=F'de seçildi. Vade geçişi sıçraması olmayan PAXG-USD serisinde de aynı sonuç alındı (p ≈ 0, 575 işlem, kâr faktörü 1,52).
- **Parametre sağlamlığı:** Her parametre tek tek değiştirildiğinde komşu ayarların %97'si kârlı. Sonuç tek bir şanslı noktaya bağlı değil.
- **Maliyet dayanıklılığı:** CFD maliyetleri 3 katına çıksa da kârlı kalıyor.
- **Kod doğruluğu:** Bağımsız incelemede göstergelerde, işlem zamanlamasında ve maliyet hesabında geleceği görme (lookahead) hatası bulunmadı. Canlı motor ile backtest aynı işlemleri üretiyor; bu artık bir test.

### Aleyhine kanıtlar ve belirsizlikler
- **Parametreler aynı veride seçildi.** Elde yalnızca 2 yıllık saatlik veri var ve bu veri birden fazla kez kullanıldı. Bu yüzden p ≈ 0 iyimser.
- **Veriye hiç bakılmadan seçilen orijinal ayarlar** anlamlı değil: p = 0,15, kâr faktörü 1,19.
- **Eski optimizasyon hatalıydı.** Rastgele veride %45 oranında sahte iyileşme kabul ediyordu. Dün raporladığım 1,18 → 1,57 artışın bir kısmı bu yüzden şişkin. Düzeltilmiş süreç bu oranı %5'e indirdi (`scripts/null_test.py`).
- **Dönem tek yönlü.** Altın bu dönemde neredeyse kesintisiz yükseldi (al-tut +%80). Strateji uzun yatay veya düşüş dönemlerinde test edilmedi.

### Karar
Mevcut parametreler korunuyor, ama strateji "kanıtlanmış" değil, **"ileriye dönük teste aday"** kabul ediliyor. 5 Ekim 2026'dan sonraki veri mühürlendi (`config/validation.yaml`). Haftalık döngü bu yeni verideki gerçek performansı her hafta `reports/self-improve-*.json` dosyasına yazıyor. ~1000 saatlik mum (yaklaşık 2 ay) birikmeden hiçbir parametre değişikliği kabul edilmiyor.

## 2. Platform maliyeti stratejiyi belirliyor

Aynı strateji, aynı veri, farklı platform maliyetleri (GC=F, saatlik, 10.000$ hesap):

| Platform | Getiri | Maks. düşüş | Kâr faktörü | İşlem başı maliyet (risk birimi R) |
|---|---|---|---|---|
| Global raw CFD (TR'de yasal değil, sadece referans) | +%60 | %8 | 1,66 | 0,004 R |
| **SPK lisanslı TR CFD (MT5)** | **+%56** | **%9** | **1,62** | **0,011 R** |
| VİOP F_XAUUSD (onbinde 5 + ücretler) | +%9 | %16 | 1,10 | 0,10 R |
| Token spot, %0,10/taraf | −%5 | %17 | 0,90 | 0,20 R |
| Token spot, %0,20/taraf | −%20 | %21 | 0,15 | 0,59 R |

Sonuç: Bu strateji işlem başına küçük bir avantajla çok sayıda işlem yapıyor. Maliyet risk tutarının ~%5'ini geçince avantaj kayboluyor. Bu nedenle bota bir **maliyet koruması** eklendi: `risk.max_cost_in_r: 0.05`. Bu eşiği aşan bir platformda bot canlı veya demo modda işlem açmayı reddediyor.

## 3. Uzun vade: tutmak mı, zamanlamak mı?

GC=F günlük veri, 2001–2026, kaldıraçsız (ETF/token/fiziki, yıllık %0,4 ücret):

| Yöntem | Yıllık getiri | Maks. düşüş | Sharpe | 2011–15 ayı piyasası |
|---|---|---|---|---|
| **Al ve tut** | **%10,9** | %45 | 0,66 | yıllık −%12, düşüş %45 |
| Al-tut + %15 volatilite hedefi | %10,9 | %46 | 0,73 | −%12 |
| 6 aylık trend filtresi (TSMOM) | %7,5 | **%32** | 0,56 | yıllık −%8, düşüş %31 |
| 12 aylık trend filtresi | %7,3 | %41 | 0,52 | −%7 |
| Uzun/kısa trend (açığa satış dahil) | %2,9 | %73 | 0,25 | — |

- **Trend filtresi düşüşü azaltıyor ama getiriyi düşürüyor.** Aynı sürede piyasada kalan rastgele bir zamanlamadan daha iyi değil (rastgelelerin %37'sinden iyi). Yani bir "avantaj" değil, bir **sigorta**. Literatürdeki "altında trend takibi çalışır" bulgusu bu veride zayıf çıktı.
- **Altında açığa satış uzun vadede zarar ettiriyor**, çünkü altının uzun vadeli eğilimi yukarı.
- **CFD ile uzun süre tutmak pahalı.** Yıllık ~%5 swap, al-tut getirisini %10,9'dan %5,9'a düşürüyor. Altın tutacaksan kaldıraçsız tut: gram altın, fon/ETF veya token.

## 4. 100$ → 1.000.000$ ne gerektirir?

10.000 kat demek. Monte Carlo (4.000 senaryo, 10 yıl):

| Yöntem | Kaldıraç / risk | Medyan 10 yıl | 10 yılda 10.000× olasılığı | %50+ düşüş olasılığı | İflas olasılığı |
|---|---|---|---|---|---|
| Al-tut (CFD) | 1× | 1,8× | %0 | %12 | %0 |
| Al-tut (CFD) | 2× | 2,4× | %0 | %82 | %0,3 |
| Al-tut (CFD) | 5× | 0,7× | %0 | %100 | **%45** |
| Al-tut (CFD) | 10× | ~0 | %0,03 | %100 | **%98** |
| Saatlik strateji* | işlem başı %1 risk | 5× | %0 | %0 | %0 |
| Saatlik strateji* | işlem başı %5 risk | 1.656× | %8,6 | %6,5 | %0 |

\* Saatlik stratejinin satırları sadece 2 yıllık, parametrelerin seçildiği veriden türetildi. **Gerçek beklentinin çok üstünde olmaları muhtemel.** İşlem başı %5 risk, art arda 10 kayıpta hesabın ~%40'ını kaybetmek demek.

**Sonuç:** Kaldıraç belli bir noktadan sonra getiriyi artırmıyor, iflası artırıyor. Hedefe gerçekten yaklaştıracak tek şey sermayeyi zaman içinde büyütmek: düzenli birikim ve kanıtlanmış bir avantaj.

## 5. En mantıklı kâr yöntemi: aşamalı plan

**Aşama 0, şimdi (100$ ile):**
1. **Çekirdek varlık:** 100$'ı kaldıraçsız altında tut (gram altın, altın fonu veya SPK listesindeki bir platformda XAUT). Uzun vadede kanıtı en güçlü getiri bu. Düşüşü azaltmak istersen 6 aylık trend filtresini kullan (getiriden ~3 puan feragat ederek).
2. **Botu ücretsiz test et:** `python -m goldbot run` (paper). Daha gerçekçi test için SPK lisanslı bir kurumun **MT5 demo hesabında** `mode: demo` ile çalıştır. Gerçek spread ve emir iletimi olur, gerçek para olmaz. Bot hesabın gerçekten demo olduğunu doğrulamadan işlem yapmaz.
3. 100$ ile kaldıraçlı işlem **yapma.** Yasal ve ucuz bir yol yok: CFD için 50.000 TL gerekiyor, VİOP ve token platformlarında maliyet avantajı yok ediyor.

**Aşama 1, birikim + ileriye dönük test (~2–6 ay):**
- Haftalık döngü mühürlü yeni veride stratejinin gerçek performansını raporluyor.
- **Geçiş şartı:** İleriye dönük testte en az 100 işlem, kâr faktörü ≥ 1,2 ve düşüş ≤ %15.

**Aşama 2, canlı (şartlar sağlanırsa, ≥ 50.000 TL):**
- SPK lisanslı kurum ve MT5. İşlem başına **%0,5–1 risk**, en fazla 1 pozisyon, mevcut günlük ve kalıcı zarar limitleri.
- Önce hesabın küçük bir kısmıyla başla.

**Asla:**
- İşlem başına %2'den fazla risk.
- Uzun süre kaldıraçlı CFD tutmak (swap getirisini yer).
- Token platformunda saatlik işlem.
- Lisanssız yurt dışı broker. SPKn 109/2 kapsamında hizmet vermek suç ve yatırımcı koruma altında değil.

## 6. Döngü şimdi ne yapıyor?

| İş | Sıklık | Ne değiştirebilir |
|---|---|---|
| `self-improve.yml` | Her hafta | `params.yaml`, ancak sadece mühürlü yeni veride de daha iyiyse. Değişiklik olmasa da her hafta ileriye dönük test raporu yazıyor. |
| `research.yml` | Her ay | Sadece raporlar: strateji varyantları (mühürlü veriye dokunmadan) ve haber kaynaklarının durumu |
| `validate.yml` | Her ay | Sadece raporlar: rastgeleye karşı test, platform maliyetleri, 25 yıllık günlük karşılaştırma, Monte Carlo |
| `ci.yml` | Her değişiklikte | 30 test. Otomatik branch'lerin sadece parametre ve rapor değiştirdiğini kontrol ediyor. |
