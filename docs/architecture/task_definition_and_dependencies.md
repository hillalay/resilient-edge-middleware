# G-1.2 / Phase 3 — Görev tanımı, kaynak gereksinimleri ve bağımlılıklar

`TaskDefinition` mantıksal bir görevin sabit tanımını taşır. Kimliği ve
oluşturulma zamanını çağıran sağlar. Aynı tanım farklı düğümlerde aynı kimlik,
kaynak gereksinimleri ve bağımlılıklarla değerlendirilebilir. Sahiplik ve
yürütme değiştikçe bu tanımı yeniden yazmak gerekmez.

## Görev tanımı

| Alan | Tip | Anlamı |
| --- | --- | --- |
| `task_id` | `str` | Çağıranın sağladığı benzersiz mantıksal görev kimliği. Snapshot içinde benzersizlik denetlenir. |
| `task_type` | `str` | Uygulamadan bağımsız görev türü kimliği. |
| `security_class` | `TaskSecurityClass` | Phase 2 güvenlik sınıfı. |
| `transferability` | `TaskTransferability` | Phase 2 devredilebilirlik biçimi. |
| `resource_requirements` | `ResourceRequirements` | Statik CPU, RAM, tahmini hesaplama süresi ve yetenek gereksinimleri. |
| `input_refs` | `tuple[InputRequirementRef, ...]` | Gerekli girdi referansları. Varsayılan boş tuple. |
| `dependency_task_ids` | `tuple[str, ...]` | Doğrudan önkoşul görev kimlikleri. Varsayılan boş tuple. |
| `priority` | `int` | Birimsiz, 0–100 aralığında (uçlar dahil) öncelik değeri. Büyük değer daha yüksek önceliği ifade eder. |
| `created_at` | `datetime` | Çağıranın sağladığı oluşturulma zamanı. UTC olarak saklanır. |
| `deadline_at` | `datetime` veya `None` | İsteğe bağlı son teslim zamanı. UTC olarak saklanır ve oluşturulma zamanına eşit ya da ondan sonra olabilir. |

Öncelik, güvenlik sınıfı ve son teslim zamanı birbirinden bağımsızdır. İki
zaman alanı da saat dilimi bilgisi gerektirir. Farklı saat dilimi ofsetleri
UTC'ye çevrilir ve karşılaştırma UTC üzerinden yapılır.

## Kaynak gereksinimleri

| Alan | Tip | Birim ve anlamı |
| --- | --- | --- |
| `min_cpu_millicores` | Pozitif `int` | CPU kapasite gereksinimi. 1000 millicore bir CPU birimine karşılık gelir. Bu değer işlemci hızını ölçmez. |
| `min_ram_bytes` | Pozitif `int` | Asgari RAM miktarı, bayt cinsinden. |
| `estimated_compute_ms` | Pozitif `int` | Referans koşullarındaki tahmini hesaplama süresi, milisaniye cinsinden. Farklı donanımlarda gerçek yürütme süresi değişebilir. |
| `required_capabilities` | `frozenset[str]` | Gerekli yetenek kimlikleri. Sıra önemsizdir ve tekrarlar tek öğeye indirgenir. Varsayılan boş küme. |

Referans hesaplama maliyeti görev tanımında saklanır. Cihaza özgü süre
tahminleri, düğümün kullanılabilir kapasitesi ve gerçek CPU/RAM ölçümleri
çalışma anında ayrı olarak ele alınır.

## Girdi referansları

| Alan | Tip | Anlamı |
| --- | --- | --- |
| `input_id` | `str` | Görev içindeki benzersiz mantıksal girdi kimliği. |
| `content_hash` | `str` veya `None` | Önek içermeyen 64 onaltılık haneli isteğe bağlı SHA-256 özeti. Küçük harflerle saklanır. |
| `size_bytes` | Negatif olmayan `int` veya `None` | Bayt cinsinden beklenen toplam boyut. `0` boş veriyi, `None` bilinmeyen boyutu ifade eder. |

Hash ve boyut birbirinden bağımsız olarak bilinmeyebilir. Örneğin, bir
önkoşulun daha sonra üreteceği çıktı için yalnızca `input_id` verilebilir.
Referans, girdinin hangi düğümde bulunduğu ya da doğrulandığı hakkında bilgi
taşımaz. Çıktının girdi kimliğine bağlanması ve içeriğin doğrulanması sonraki
Input ve Output sözleşmelerinin sorumluluğudur.

## Doğrulama ve hata sözleşmesi

- Alanın veya koleksiyon öğesinin tipi yanlışsa `TypeError` üretilir. Ham
  string yerine ilgili enum üyeleri gerekir. Sayısal alanlar gerçek `int`
  değerleri kabul eder ve `bool` değerlerini reddeder.
- Alanın tipi doğru, değeri geçersizse `ValueError` üretilir. Boş ya da
  yalnızca boşluk içeren kimlikler, pozitif olmayan kaynak ölçüleri, sınır dışı
  öncelik, geçersiz hash biçimi, negatif boyut, saat dilimsiz veya UTC'ye
  çevrilemeyen zaman ve oluşturulma öncesindeki deadline bu gruptadır.
- Kimlikler olduğu gibi saklanır ve tam metin eşleşmesiyle karşılaştırılır.
  Görev kendi kimliğine bağımlı olamaz. Aynı görevde tekrarlanan girdi veya
  bağımlılık kimlikleri `ValueError` üretir.
- Üç model de dondurulmuş ve `slots` kullanan dataclass'lardır. Sıralı girdi
  ve bağımlılık koleksiyonları tuple'a, yetenek koleksiyonu frozenset'e
  kopyalanır. Çağıranın sonradan yaptığı koleksiyon değişiklikleri tanımı etkilemez.

## Bağımlılık grafiği

A, B'ye bağımlıysa A'nın başlayabilmesi için B'nin geçerli tamamlanma
koşulunu sağlaması gerekir. `validate_task_dependencies` tam bir tanım snapshot'ını
doğrular. Başarılı doğrulama `None` döndürür. Bağımsız görevler, boş snapshot
ve birbirine bağlı olmayan birden çok DAG bileşeni geçerlidir.

1. Tanımlar `task_id` ile indekslenir. Yanlış eleman tipi `TypeError`,
   tekrarlanan kimlik `TaskDependencyError` ve `duplicate_task_id` nedenini üretir.
2. Doğrudan referanslar kontrol edilir. Kendine bağımlılık `self_dependency`,
   snapshot'ta bulunmayan bir bağımlılık `missing_dependency` olarak bildirilir.
3. Standart kütüphanedeki `TopologicalSorter.prepare()` doğrudan ve dolaylı
   döngüleri arar. Bir döngü bulunduğunda `TaskDependencyError`, `cycle` nedeni
   ve `görev -> önkoşul` yönünde kapalı bir yol içerir.

`TaskDependencyError`, `ValueError` alt sınıfıdır ve `reason` alanını taşır.
Doğrulama aynı sırada verilen girdiler için deterministiktir ve ilk hatada
durur. Beklenen zaman ve ek bellek karmaşıklığı, V görev ve E doğrudan
bağımlılık için `O(V + E)`'dir. Doğrulama görevleri değiştirmez, çalışma
sırası üretmez ve görevlerin tamamlanma durumunu sorgulamaz. Dağıtık ağda
bir düğümün kısmi kaydında eksik olan referans, tek başına görev tanımının
geçersiz olduğunu göstermez.

## Örnekler

Bağımsız `collect-1` görevi ile onun henüz üretilmemiş girdisine ihtiyaç duyan
`aggregate-1` görevi birlikte geçerli bir snapshot oluşturur.

```python
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from edge_middleware.models.resource_requirements import ResourceRequirements
from edge_middleware.models.task_definition import InputRequirementRef, TaskDefinition
from edge_middleware.models.task_dependencies import validate_task_dependencies
from edge_middleware.models.task_policy import (
    TaskSecurityClass,
    TaskTransferability,
    resolve_task_policy,
)

created = datetime(2026, 11, 26, 9, tzinfo=UTC)
collect = TaskDefinition(
    task_id="collect-1",
    task_type="collect",
    security_class=TaskSecurityClass.ROUTINE,
    transferability=TaskTransferability.RESTART,
    resource_requirements=ResourceRequirements(250, 134_217_728, 1500),
    priority=30,
    created_at=created,
)
aggregate = TaskDefinition(
    task_id="aggregate-1",
    task_type="aggregate",
    security_class=TaskSecurityClass.CRITICAL,
    transferability=TaskTransferability.CHECKPOINT,
    resource_requirements=ResourceRequirements(500, 268_435_456, 2500),
    priority=60,
    created_at=created,
    deadline_at=created + timedelta(minutes=5),
    input_refs=[InputRequirementRef("collected-events")],
    dependency_task_ids=["collect-1"],
)

assert validate_task_dependencies([collect, aggregate]) is None
assert resolve_task_policy(
    aggregate.security_class, aggregate.transferability
).checkpoint_required_for_transfer
```

Aşağıdaki çağrılar birbirinden bağımsız geçersiz örneklerdir.

```python
replace(collect, priority=101)                     # ValueError
replace(aggregate, dependency_task_ids=["aggregate-1"])  # ValueError
validate_task_dependencies([aggregate])            # missing_dependency
validate_task_dependencies([                       # cycle
    replace(collect, dependency_task_ids=["aggregate-1"]), aggregate,
])
```

## Çalışma anı ve deney entegrasyonu

- Phase 1 yapısal geçişleri doğrular. Phase 2 politikası tanımdaki güvenlik
  sınıfından ve devredilebilirlikten türetilir. `TaskDefinition` bu politikayı
  ikinci bir veri kaynağı olarak saklamaz.
- Güncel sahip, fencing token, lease, yürütme girişimi, ilerleme, bağlantı ve
  girdi mevcudiyeti tanımın ömründen bağımsız değişir. Bu verilerin sahipliği
  sonraki State, Authority Event, Execution, Input ve Output sözleşmelerine
  aittir. Tanım güncellemeleri ve farklı düğümlerde aynı kimliğe sahip
  tanımların uzlaştırılması sonraki sürüm ve bütünlük politikalarının
  sorumluluğudur.
- Resmî H1 ve H2 hipotez metinleri repo içinde bulunmadığından, deneyler için
  şu eşleştirme varsayılmıştır. H1'de kaynak duyarlı atama karşılaştırmalarına
  sabit CPU, RAM, yetenek ve referans süre gereksinimleri sağlanır. H2'de girdi
  ve bağımlılık duyarlı karşılaştırmalara tekrar kullanılabilir DAG yapıları,
  girdi kimlikleri, isteğe bağlı hash ve boyut ile deadline verisi sağlanır.
  Gerçek kaynak, bağlantı, girdi mevcudiyeti ve yürütme ölçümleri deney
  katmanında toplanır.
