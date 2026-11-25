# G-1.2 / Phase 1 — Görev yaşam döngüsü sözleşmesi

Bu aşama yalnızca görev durumlarını ve yapısal geçiş uygunluğunu tanımlar.
Çalışan bir dağıtık görev yönetim sistemi veya yürütme motoru değildir.

## Durumlar ve geçişler

`TaskStatus`, Python 3.12 ile uyumlu standart `StrEnum` kullanır. Serileştirilmiş
değerler sırasıyla `created`, `assigned`, `running`, `completed`, `cancelled`'dır.
`COMPLETED` ve `CANCELLED` terminaldir. Ek yaşam döngüsü durumu yoktur.

| Başlangıç / Hedef | CREATED | ASSIGNED | RUNNING | COMPLETED | CANCELLED |
| --- | --- | --- | --- | --- | --- |
| CREATED | — | NORMAL | — | — | CANCEL |
| ASSIGNED | — | REASSIGN | NORMAL | — | CANCEL |
| RUNNING | — | REASSIGN | — | NORMAL | CANCEL |
| COMPLETED | — | — | — | — | — |
| CANCELLED | — | — | — | — | — |

`—`, tüm niyetlerde reddedilen geçiştir. Diğer hücreler yalnızca belirtilen
niyetle yapısal olarak uygundur. `TransitionIntent` değerleri görev durumu değil,
istenen işlemi tanımlayan ayrı bir sözleşmedir:

- `NORMAL`: varsayılan normal ilerleme.
- `CANCEL`: açık iptal isteği; yalnızca terminal olmayan durumlardan `CANCELLED`'a.
- `REASSIGN`: açık yeniden atama isteği; yalnızca `ASSIGNED` veya `RUNNING`'den `ASSIGNED`'a.

Aynı durumun tekrar bildirilmesi yeni geçiş değildir. Tek istisna olan
`ASSIGNED → ASSIGNED`, sıradan bildirim olarak reddedilir; yalnızca açık
`REASSIGN` niyetiyle aday yeniden atama olarak değerlendirilir. Terminal
durumların tekrar bildirimi de yeni geçiş sayılmaz. Tekrar bildirimlerini
karşılama ve idempotency politikası bu aşamada uygulanmaz.

## Saf doğrulama ve yetkilendirme sınırı

```python
from edge_middleware.models.task_lifecycle import (
    TaskStatus,
    TransitionIntent,
    is_valid_transition,
)

assert is_valid_transition(TaskStatus.CREATED, TaskStatus.ASSIGNED)
assert not is_valid_transition(TaskStatus.ASSIGNED, TaskStatus.ASSIGNED)
assert is_valid_transition(
    TaskStatus.ASSIGNED,
    TaskStatus.ASSIGNED,
    intent=TransitionIntent.REASSIGN,
)
```

`is_valid_transition(current, target, *, intent=TransitionIntent.NORMAL) -> bool`
yalnızca enum üyelerini kabul eder; başka tipler için `False` döndürür.
Serileştirilmiş girdilerin enum'a dönüştürülmesi çağıranın sorumluluğudur.
Fonksiyon sabit ve değiştirilemez bir geçiş kümesine bakar; girdilerini,
görev durumunu veya sahibini değiştirmez. Saat okumaz, ağ veya veri tabanı
kullanmaz ve görev çalıştırmaz. Aynı girdiler her zaman aynı sonucu verir.

`True`, yalnızca yapısal uygunluk demektir. İşlemin güvenli biçimde
yetkilendirildiğini, quorum/lease/fencing kontrolü yapıldığını, girdilerin
hazır olduğunu veya bir sonucun yetkili kabul edildiğini göstermez. Açık niyet
de tek başına izin sağlamaz. Sahiplik, yetkilendirme ve güvenli uygulama sonraki
koordinasyon katmanlarının ayrı sorumluluklarıdır.

## Dağıtık sistem kuralları

- Bağlantının kesilmesi doğrudan görev durumunu değiştirmez.
- Görev durumu, düğüm bağlantı durumu, görev sahipliği ve yürütme girişimi farklı
  kavramlardır. Bir görevin farklı yürütme girişimleri olabilir; bu sözleşme
  girişim veya sahiplik kaydı tutmaz.
- Bir görevin atanmış olması, gerekli girdilerin hazır olduğu anlamına gelmez.
- Bir görevin tamamlandığının bildirilmesi, sonucun yetkili olarak kabul edildiği
  anlamına gelmez. Yapısal `RUNNING → COMPLETED` uygunluğu sonuç onayı değildir.
- Rutin görevlerde ağ bölünmesi sırasında mükerrer yürütme mümkündür. Bu sözleşme
  tam bir kez yürütme garantisi vermez.
- Kritik görevlerde geçerli quorum onayı ve fencing olmadan yeni sahiplik
  verilmez. Bu kural ilk atama ve yeniden atama için de geçerlidir; bu modül
  sahiplik vermez ve bu kontrolleri uygulamaz.
- Manuel onay quorum yerine geçmez.
- Kritik iptal yalnızca bir durum değişikliğiyle gerçekleştirilemez. Güvenli
  durdurma ve yetki kontrolleri sonraki aşamalarda tasarlanmalıdır; `CANCEL`
  niyeti yürütmenin durduğunu kanıtlamaz.

## Sonraki aşamalarla entegrasyon

- Zamanlayıcı, aday geçişin yapısını bu fonksiyonla kontrol edebilir. Atama
  kararı için bağlantı, kaynak ve girdi erişilebilirliğini ayrıca değerlendirmelidir.
- Koordinasyon katmanı sahiplik değişimini, kritik görev quorum onayını,
  lease ve fencing kontrollerini ayrıca tasarlamalıdır. Yapısal uygunluk ile
  durumun uygulanması arasında oluşabilecek eşzamanlı değişimler de burada
  ele alınmalıdır; bu fonksiyon atomik güncelleme sağlamaz.
- Yürütme katmanı yürütme girişimlerini, girdi hazırlığını ve güvenli durdurmayı
  ayrı tutmalıdır. Sonuç kabul katmanı, tamamlanma bildirimini kabul etmeden
  önce sahiplik ve yürütme girişiminin yetkisini doğrulamalıdır.
- Senkronizasyon katmanı tekrar bildirimlerini ve mükerrer sonuçları ele alan
  idempotency/uzlaştırma politikasını ayrıca tanımlamalıdır.

REST API/FastAPI, atama algoritması, yürütme motoru, CRDT, quorum, lease yönetimi,
fencing token üretimi, idempotency motoru, PQC, veri tabanı ve gerçek ağ
haberleşmesi bu aşamada uygulanmamıştır.

## Testler

Repo kökünden:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/models/test_task_lifecycle.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Bu komutlar mevcut Python 3.12 sanal ortamını kullanır; `-p no:cacheprovider`,
ortamdaki önbellek dizini erişim hatasını önlemek için yalnızca pytest önbelleğini
kapatır. Pytest yapılandırması `src` dizinini import yoluna ekler. Testler beş enum
değerini ve JSON serileştirmesini, 25 durum çiftini üç niyetin her biriyle
(75 kombinasyon), varsayılan niyeti, terminal durumları, tekrar bildirimlerini
ve geçersiz tipleri doğrular. Tüm kombinasyonlar tekrar çalıştırılarak
determinizm ve girdilerin değişmediği kontrol edilir; dosya, ağ, veri tabanı
erişimi ve yaygın saat okuma çağrıları engellenirken de aynı sonuçlar beklenir.
Yan etkisizlik sınırı ayrıca modülün yalnızca `enum` bağımlılığı ve sabit geçiş
kümesi üzerinden incelenebilir.
