# G-1.2 / Phase 4 — Dağıtık durum veri sözleşmesi

`TaskDefinition` çağıranın sağladığı sabit görev tanımıdır. `TaskStateObservation`
bir düğümün aynı göreve ilişkin yerel görünümünü, `ExecutionState` ise bir
çalışanın tek bir yürütme girişimine ilişkin raporunu taşır. Bir görev için birden
fazla düğüm gözlemi ve birden fazla yürütme girişimi birlikte bulunabilir.
`InputAvailabilityObservation`, H2 için girdiye ilişkin yerel bayt sayısını bu
durum kayıtlarından bağımsız taşır. [TaskDefinition sözleşmesi](task_definition_and_dependencies.md)

## Yürütme girişimi

`ExecutionStatus`, `pending`, `running`, `succeeded`, `failed` ve `cancelled`
değerlerini JSON string olarak serileştiren bir `StrEnum`'dur. Girişimin
`SUCCEEDED` raporu sonuç üretiminin ardından gelebilir. Mantıksal görevin
`COMPLETED` kabulü, yetkili sonuç kabulüne bağlıdır. Girişimin `FAILED` veya
`CANCELLED` raporu girişimi kapsar. Mantıksal göreve ilişkin karar ayrı verilir.

| Alan | Tip ve birim | Üretici ve kapsam | İleride değerlendirilecek senkronizasyon |
| --- | --- | --- | --- |
| `task_id` | `str` | Görev tanımının kimliğini veren çağırandan gelir. Rapor bu mantıksal göreve bağlanır. | Görev tanımıyla kimlik üzerinden eşleştirme. |
| `execution_id` | `str` | Girişimi oluşturan bileşenin verdiği kimlik. Bir görevde farklı denemeler farklı kimlikler taşır. | Girişim kayıtlarını kimlikle ilişkilendirme. |
| `worker_node_id` | `str` | Raporlayan çalışanın düğüm kimliği. Girişim gözleminin kaynağını belirtir. | Kaynak bazında tutma ve daha sonra kaynak kimliğini doğrulama. |
| `status` | `ExecutionStatus` | Çalışan, girişimin raporladığı durumu bildirir. | Aynı girişimin aynı kaynak akışındaki raporları değerlendirme. |
| `progress_bps` | `int` veya `None`, baz puan | Çalışan ölçebildiğinde `0–10000` arasında ilerleme bildirir. `10000` yüzde 100, `None` bilinmeyen ilerlemedir. | Yalnızca ilgili girişimin raporunda saklama. |
| `started_at` | UTC `datetime` veya `None` | Çalışanın bildirdiği girişim başlangıç zamanı. | Teşhis amacıyla raporla birlikte taşıma. |
| `finished_at` | UTC `datetime` veya `None` | Çalışanın bildirdiği girişim bitiş zamanı. | Teşhis amacıyla raporla birlikte taşıma. |
| `failure_code` | `str` veya `None` | Çalışanın girişim için bildirdiği makinece okunabilir hata kodu. | Kod ile kaynak girişimi birlikte taşıma. |
| `source_revision` | Negatif olmayan `int`, birimsiz | Çalışan, kendi kaynak örneği içinde `(task_id, execution_id, worker_node_id)` akışı için sağlar. | Kaynak örneği ve akış doğrulanınca akış içi tekrarları tanıma. |
| `observed_at` | UTC `datetime` | Çağıranın, kaynak raporunun gözlem zamanı olarak sağladığı fiziksel zaman. | Teşhis amacıyla kaynak raporuyla birlikte taşıma. |

Bir `SUCCEEDED` kaydında kısmi veya bilinmeyen ilerleme geçerlidir. Başlangıç ve
bitiş zamanı birbirinden bağımsız olarak bilinmeyebilir. Hata kodu verilmişse
boş olamaz. Kod sözlüğü ve durum geçişleri sonraki Execution sözleşmesine aittir.

## Mantıksal göreve ilişkin yerel gözlem

| Alan | Tip ve birim | Üretici ve kapsam | İleride değerlendirilecek senkronizasyon |
| --- | --- | --- | --- |
| `task_id` | `str` | Çağıranın görev tanımından aldığı kimlik. | Görev tanımıyla kimlik üzerinden eşleştirme. |
| `observer_node_id` | `str` | Gözlemi üreten düğümün kimliği. | Raporları düğüme göre ayrı tutma ve kaynağı doğrulama. |
| `observed_status` | `TaskStatus` | Gözlemci düğümün o görev için gördüğü durum. | Düğüm bazında rapor saklama ve yetki kaydıyla ayrı değerlendirme. |
| `known_execution_ids` | `tuple[str, ...]` | Gözlemcinin bildiği girişim kimlikleri. Boş tuple, bu gözlemde girişim kimliği bildirilmediğini ifade eder. | Kimlik referanslarını girişim kayıtlarıyla ilişkilendirme. |
| `source_revision` | Negatif olmayan `int`, birimsiz | Gözlemci, kendi kaynak örneği içinde `(task_id, observer_node_id)` akışı için sağlar. | Kaynak örneği ve akış doğrulanınca akış içi tekrarları tanıma. |
| `observed_at` | UTC `datetime` | Çağıranın yerel gözlem için sağladığı fiziksel zaman. | Teşhis amacıyla gözlemle birlikte taşıma. |

Bir gözlemdeki `COMPLETED` ve `CANCELLED` değerleri gözlemcinin gördüğü durumu
korur. Geçerli sonuç kabulü ve iptal ayrı yetki kayıtlarına dayanır. Bir düğümün
bildiği girişim listesi kısmi olabilir.

## Düğüme yerel girdi erişilebilirliği

| Alan | Tip ve birim | Üretici ve kapsam | İleride değerlendirilecek senkronizasyon |
| --- | --- | --- | --- |
| `node_id` | `str` | Yerel girdi gözlemini sağlayan düğümün kimliği. | Erişilebilirlik raporlarını düğüm kapsamında tutma. |
| `task_id` | `str` | Çağıranın görev tanımından aldığı kimlik. | Tanımla ilişkilendirme. |
| `input_id` | `str` | Çağıranın görevdeki girdi referansından kullandığı kimlik. | Görev kapsamında Input/Output kayıtlarıyla eşleştirme. |
| `expected_content_hash` | `str` veya `None`, SHA-256 | Çağıranın tanım veya girdi bağından sağladığı beklenen içerik özeti. Öneksiz 64 onaltılık hane, küçük harfle saklanır. | Bilinen içerik sürümlerini ayrı tutma ve Phase 6 bağını doğrulama. |
| `expected_size_bytes` | Negatif olmayan `int` veya `None`, bayt | Çağıranın girdi tanımı veya bağından aldığı beklenen toplam boyut. | Aynı içerik bağındaki beklenen boyutla karşılaştırma. |
| `available_verified_bytes` | Negatif olmayan `int`, bayt | Gözlemci düğümün yerelde doğrulanmış olarak bildirdiği bayt miktarı. | Düğüm, görev, girdi ve içerik sürümü kapsamında rapor saklama. |
| `source_revision` | Negatif olmayan `int`, birimsiz | Gözlemci, kendi kaynak örneği içinde `(node_id, task_id, input_id, expected_content_hash)` akışı için sağlar. | Kaynak örneği ve akış doğrulanınca akış içi tekrarları tanıma. |
| `observed_at` | UTC `datetime` | Çağıranın yerel girdi gözlemi için sağladığı fiziksel zaman. | Teşhis amacıyla gözlemle birlikte taşıma. |

Toplam boyut biliniyorsa yerel sayı onu aşamaz. Bilinmeyen boyut için hazır olma
oranı hesaplanamaz. Sayının toplam boyuta eşit olduğu durumda dahi tam içerik
doğrulaması ve görevin yürütülebilirliği ayrı koşullara bağlıdır. Farklı içerik
sürümlerinin bayt sayıları toplanmaz. `None` hash, içerik kimliğinin bilinmediğini
ifade eder. İki bilinmeyen hash aynı içeriği kanıtlamaz ve hash sonradan
belirlendiğinde önceki bayt sayısı yeni sürüme kendiliğinden bağlanmaz.

## Revizyon ve fiziksel zaman

`source_revision` çağıranın sağladığı kaynak içi bir sayaç değeridir. Kapsamı,
yukarıdaki kayıt anahtarı ve sayacı üreten sürecin o anki örneğiyle sınırlıdır.
Değer global epoch, fencing token, version vector veya düğümler arası sıra
olarak yorumlanamaz. Model bir önceki kayda bakmadan revizyonun tipini ve
aralığını doğrular. Süreç yeniden başladığında sayaç sıfırlanabilir ya da aynı
düğüm kimliğiyle çakışabilir. İleriki senkronizasyon sözleşmesi için üreticinin
sağladığı ve süreç örneği boyunca sabit kalan bir `source_incarnation_id` alanı
önerilir. Bu alan eski ve yeni sayaç akışlarının karışmasını önlemeye yönelik
bir kaynak kimliği olur. Akışların karşılaştırılması, kaynak örneğinin
ayırt edilebilmesine bağlıdır.

Zamanlar çağıran tarafından sağlanır ve UTC'ye normalleştirilir. Aynı düğümde
bile duvar saati ayarlanabilir. Başlangıç, bitiş ve gözlem zamanları birbirinden
bağımsız doğrulanır. Olay sırası veya yetki çıkarımı bu alanlara dayanamaz.

## Senkronizasyon ve yetki sınırları

- **Görev tanımı referansları** `task_id` ve `input_id`, tanım ve girdi bağıyla
  eşleştirilir. Tanım değişiklikleri ve kimlik çakışmaları sürüm ve bütünlük
  sözleşmelerine aittir.
- **Düğüme özgü gözlemler** Yerel `observed_status`, bilinen girişimler ve
  girdiye ilişkin ölçümler kaynak düğüm kapsamında değerlendirilir.
- **Yürütme girişimine özgü gözlemler** `execution_id` ve `worker_node_id`
  durum, ilerleme, zamanlar ve hata kodunun kapsamını belirler. Ayrı
  girişimlerin ilerlemesi `max` ile birleştirilemez.
- **Birleştirilebilir aday durum verileri** Kaynağı, kaynak örneği ve kayıt
  anahtarı doğrulanmış gözlem kayıtları ileride senkronize edilebilir. Çatışan
  `COMPLETED` ve `CANCELLED` gözlemleri korunur. Enum sırası ve fiziksel zaman
  Last-Write-Wins ölçütü olarak kullanılmaz. Phase 4 yalnızca kayıt yapısını
  sağlar.
- **Yetki ve olay kaydı gerektiren durumlar** Kritik sahiplik, geçerli sonuç
  kabulü ve iptal Phase 5 Authority Event kayıtlarına bağlanır. Sonuç üretimi
  ve sonucunun yetkili biçimde kabulü ayrı olaylardır. Kritik sahiplik kararı
  gözlemlerden veya CRDT durumundan türetilmez.
- **Yerel ve geçici bilgiler** Anlık bağlantı ve erişilebilirlik ölçümleri
  yerel kararlarda kullanılabilir. Bağlantı kaybı, görev veya girişim
  başarısızlığına kanıt oluşturmaz. Girdi bayt sayısı da gözlemden sonra
  değişebilen yerel bir ölçümdür.

Phase 6 Input/Output sözleşmeleri, `task_id` ve `input_id` üzerinden tanımdaki
girdi bağını, beklenen içerik kimliğini, chunk bitmap'ini, hash doğrulamayı ve
blok deposunu ele alır. Phase 4 H2 için düğüm başına mevcut bayt gözlemi
sağlar. İçeriğin hazır sayılması ve bu bilginin bir atama kararına etkisi ayrı
değerlendirilir.

## Yapısal doğrulama

Üç gözlem modeli dondurulmuş ve `slots` kullanan dataclass'lardır. Yanlış tipler
`TypeError`, geçersiz değerler `ValueError` üretir. Boş veya yalnızca boşluk
içeren kimlikler ve hata kodları reddedilir. Sayısal alanlar `bool` kabul etmez.
Durum alanları kendi enum üyelerini gerektirir. Zaman damgaları saat dilimi
bilgisi taşımalıdır. Bilinen girişim kimlikleri sıralı bir koleksiyondan tuple'a
kopyalanır ve yinelenen kimlikler reddedilir. SHA-256 biçimi Phase 3 ile uyumludur.

Kayıtların doğruluğu için kaynak doğrulaması, referansların varlığı, sayacın
geçmişi, içerik doğrulaması, görev geçişi ve yetki gibi dış bilgiler gerekir.
Bu sözleşme bunlara ilişkin kanıt üretmez.

## Örnek gözlemler

| Olay | Kayda alınan gözlemler | Yorum |
| --- | --- | --- |
| `node-a` ile bağlantı kesiliyor | `task-1` için son rapor `attempt-1`, `RUNNING`, `8500` baz puan. | Elde bulunan bilgi son rapordur. Sonraki girişim durumu bilinmiyor. |
| `task-1` yeniden atanıyor | `node-b`, `attempt-2` için `RUNNING` ve `1500` baz puan raporluyor. İki rapor da kaynak revizyonu `4` taşıyabilir. | Girişimler ve sayaç akışları ayrı kalır. Yeni girişimin ilerlemesi yüzde 15'tir. |
| Düğümler aynı görevi farklı görüyor | `node-a` `COMPLETED`, `node-b` `CANCELLED` görüyor. `attempt-2` ayrıca `SUCCEEDED` raporlamış olabilir. | Her gözlem kendi kaynağına aittir. Sonuç kabulü veya iptal için yetki kaydı gerekir. |
| Aynı girdi kimliği için iki sürüm görülüyor | `node-b`, ilk sürümden 80 bayt, başka bir hash'e sahip sürümden 20 bayt bildiriyor. | İki sayı ayrı içerik sürümlerine aittir. Toplam boyutu bilinmeyen sürüm için oran verilmez. |
