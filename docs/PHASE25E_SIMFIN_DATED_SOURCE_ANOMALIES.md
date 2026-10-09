# Faz 25e — Tarihli kaynak fiyat anomalileri, bağımsız kurumsal işlem kanıtı öncesi inceleme paketi

## 10 Ekim 2026 Windows Faz25d sonuçları

- Gerçek 21 aylık SimFin araştırma havuzu: **3.557 SimFinId**
- Benzersiz düzeltme veya aşırı düzeltilmiş fiyat hareketi araştırma adayı: **133**
- **P1 çoklu uyarı: 6**; **P2 faktör uyarısı: 88**; **P3 yalnızca aşırı Adj.Close aylık sınır hareketi: 39**
- Faktör değişimi görülen benzersiz adaylar: **94**; birden fazla uyarı türündeki adaylar: **6**
- Bu üç uyarıdan birini üretmeyen **3.424** kaydın hiçbirine 'clean/canonical' sertifikası verilmez.
- Bağımsız split, temettü, delisting, PIT kimlik ve düzeltilmiş getiri sertifikası: **0**.

## Faz25e ne yapar?

\`scripts/phase25e_simfin_dated_source_anomalies.py\` yalnızca **önceden indirilen yerel SimFin 415 MB CSV**, önceki özel \`phase25b\`, \`phase25c\`, \`phase25d\` JSON denetimleri ve 21 aylık ücretsiz PIT liste arşivini okur. Önceki SHA256/satır/tam 21 aylık dönem/olay sayısı kanıtlarının uyumunu kontrol eder.

133 uyarı adayını bir kez tarayarak:
1. **P1 altı adayın gerçek ticker ve SimFinId'lerini** kısa çıktıya ekler.
2. \`Close / Adj. Close\` değerindeki en az %5 aylık min–maks faktör aralığı için **kaynak ekstrem tarihlerini**, kaynak kapanışları ve oranları verir.
3. Takip eden iki ayın ilk/son kaynak gözlemleri arasında **%5+ faktör farkının hangi kesin gözlemlerden hesaplandığını** gösterir.
4. Aylık sınır gözlemleri arasında **%50+ Adj.Close hareketini** ilk/son kaynak günleriyle verir.
5. Her aday için hesaplanan olay sınıfı sayısını **Faz25d'deki gerçek özel iş listesi ve Faz25c metrikleriyle birebir uzlaştırır**.

### Kritik metodoloji sınırı

Bir ayın minimum/maksimum \`Close/Adj. Close\` faktör değerlerinin tarihleri **gerçek split/temettü işlem tarihi** değildir. Ay sınırındaki yakın gözlemler de olay ex-date, gerçek borsa oturumu veya SEC kabul zamanı kanıtı değildir. Bu işlem **bağımsız kurumsal işlem olayı doğrulamaz**. Olay olmayan 3.424 aday otomatik güvenilir sayılmaz.

## Windows PowerShell

\`\`\`powershell
cd E:\M10
git pull --ff-only

$file = "$env:USERPROFILE\Downloads\us-shareprices-daily\us-shareprices-daily.csv"

.\.venv\Scripts\python.exe -m scripts.phase25e_simfin_dated_source_anomalies --input "$file"
\`\`\`

Özel rapor:
\`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25e\simfin_dated_source_anomaly_packets.json\`.

Beklenen **kaynağın değişmemiş olması şartıyla** \`unique_review_candidates:133\`, \`P1_candidate_count:6\`; diğer gerçek olay adetlerini otomatik hesaplar. Hata durumunda eski raporlar korunur; araç fail-closed durur. CSV 415MB olduğundan Windows donanıma göre birkaç dakika sürebilir. Repo yalnızca **kod/test/rehber** içerir; kullanıcı özel verisi GitHub'a gönderilmez.

## Sonraki aşama

Faz25f: Önce P1 altı hissenin olay tarihleri için **doğrudan SEC, şirket yatırımcı ilişkileri, FINRA/borsa ve kurumsal işlem/temettü duyurularından** bağımsız kanıt kaydı (kaynak URL, erişim/kamuya açıklama anı, duyuru/işlem tarihi, verinin lisansı); sonrasında P2/P3 genişletme. Veri olmadan doğrulanmış split veya temettü sayısı uydurulmaz. Devamında delisting, resmi piyasa seansı, geçmiş CIK ve look-ahead-safe geri test zorunlu.

Ücretsiz veri tercihine sadık kalınır. Üretim \`operational.db\`, mevcut SEC finansalları (~12.3M kayıt), SimFin CSV ve kanonik Meridyen formülleri **değiştirilmez**. Bu araç, internet veya ücretli API kullanmaz, model eğitimi yapmaz ve hiçbir hissenin geçmişe dönük performans sonucunu kanonikleştirmez.
