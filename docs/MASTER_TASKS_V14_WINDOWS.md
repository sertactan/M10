# V14 — Windows üretim hazırlığı ve dağıtım kararı

12 Ekim 2026 (JST). V13 `18.build` kapısı **VERIFIED** olarak korundu; kabul edilmiş EXE SHA-256 `b57b392bf774e2f5a398b429f70a748c9130c1ab0689e20946b5d890ba6be23c`. Yeni PyInstaller işi yapılmadı. V13 kurulum ve kaldırma kanıtları geçerlidir. Bu paket 1.0.6.0, imzasız ve `PRIVATE_TEST_ONLY` tohumları içerir; üretim dağıtım adayı değildir.

Özel [V14 üretim hazırlığı makbuzu](E:/M10/.master_tasks_v14_private/windows/release_readiness_v1.json) SHA-256 `8fe15b28515e6fa607e846f34cfb22fc89ecd342d4329e0ef671cbadbc2d8609`, çevrimdışı tekrar **PASS**. Paket içindeki tohum hashleri V13 özel test tohumlarıyla eşleşir. Paket dosya adlarında ham SEC gövdesi, `.env` veya SQLite DB bulunmadı; gömülü config dosyalarında bilinen özel anahtar belirteçleri bulunmadı. Bu tarama genel bir sır yokluğu garantisi değildir. Gömülü US tohumu `SEC_MIRROR_EDGARTOOLS`, tarih `2026-06-01`; mevcut yayın kapısı `Release requires directly fetched SEC US seed` sonucuyla beklendiği gibi reddetti. Dağıtım onayı da mevcut değil.

Bu nedenle **18.deployment OPEN**. Test verisi içermeyen üretim paketi ancak şu somut sırayla hazırlanabilir:

1. Son 30 gün içinde doğrudan SEC'den alınmış, kaynağı ve SHA-256 değeri mühürlenmiş US referans tohumu.
2. Aynı tohum hashlerine bağlı kaynak/lisans değerlendirmesi ve kullanıcı dağıtım kararı.
3. Bu girdilerle izole yeni EXE/yükleyici, hash ve kurulu kopya Qt kabulü.
4. Canlı uygulama hedefi, DB yedeği, gerekirse migration ve geri alma adımlarının ayrı onayı.

Canlı 9.208.872.960 bayt `operational.db` için son değişiklik zamanı `2026-10-10 16:23:10 UTC` olarak gözlendi. Canlı kurulum, migration ve PR merge yapılmadı. Kullanıcının V14 talimatı bu işlemler için onay sayılmaz.
