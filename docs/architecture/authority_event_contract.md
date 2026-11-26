# G-1.2 / Phase 5 — Yetki olayları ve sahiplik veri sözleşmesi

`TaskDefinition` görevin sabit tanımını taşır. `TaskStateObservation` bir düğümün
gördüğü görev durumunu, `ExecutionState` bir yürütme girişiminin raporunu taşır.
`RoutineOwnershipClaim` bir düğümün sahiplik iddiasını, `CriticalOwnershipEvidence`
ise dışarıdaki bir quorum kararına bağlanacak beklenen yetki bağlamını taşır.
`AuthorityEvent` gerçekleştiği bildirilen bir kararı kaydeder. İddianın, kanıt
referansının veya olayın oluşturulması tek başına yetki sağlamaz.

TÜBİTAK önerisinin 2.2 bölümü yerel rutin atamaları ve quorum gerektiren kritik
sahipliği ayrı ele alır. 2.3 bölümü ilk kritik sahiplik ve devirde quorum ile
artan fencing token, ayrıca iki noktada fencing doğrulaması öngörür. 2.5 bölümü
yetki olaylarını olay günlüğüne, birleştirilebilir durum verisini δ-CRDT'ye ve
girdi/çıktı içeriğini içerik adresli bloklara bağlar. Bu modelde gözlemler ve
yetki olayları ayrı veri sözleşmeleridir. [TÜBİTAK proje önerisi](<../../TUBITAK_2209A_Edge_Proje_Onerisi (2).docx>)

## Olay ve payload sözleşmesi

| Ortak alan | Tip ve anlamı |
| --- | --- |
| `event_id` | Çağıranın verdiği boş olmayan `str` olay kimliği. |
| `task_id` | İlgili mantıksal görevin `str` kimliği. Payload'daki görev referansları bu kimlikle eşleşir. |
| `security_class` | Görevin `TaskSecurityClass` değeri. Sahiplik veya yetki referansının tipi bu sınıfla eşleşir. |
| `event_type` | `AuthorityEventType`, bildirilen işlemin türü. |
| `issuer_node_id` | Kararı bildiren tarafın `str` düğüm kimliği. Kimliğin doğrulanması ayrı bir sorumluluktur. |
| `issued_at` | Çağıranın sağladığı saat dilimi bilgili `datetime`. UTC olarak saklanır. |
| `payload` | Aşağıdaki olay türüne uygun dondurulmuş kayıt veya tipli referans. |

`AuthorityEventType` bir `StrEnum`'dur. Tablodaki değerler serileştirme
değerleridir. Her satır yalnızca belirtilen payload modelini kabul eder.
Referanslar aynı göreve ait olmalıdır. Bir modelde tanımlanmayan alanlar ve
başka bir olayın payload modeli kabul edilmez.

| Olay türü | Zorunlu payload ve koşullar | Yasak kombinasyonlar |
| --- | --- | --- |
| `ownership_granted` | `ROUTINE` için `RoutineOwnershipClaim`. `CRITICAL` için `GRANT` kapsamlı `CriticalOwnershipEvidence`. | Önceki sahiplik referansı veya `TRANSFER` kapsamı. |
| `ownership_transferred` | `ROUTINE` için önceki claim referansını taşıyan `RoutineOwnershipClaim`. `CRITICAL` için önceki yetki kaydını taşıyan `TRANSFER` kapsamlı `CriticalOwnershipEvidence`. | Eksik önceki sahiplik referansı veya `GRANT` kapsamı. |
| `lease_renewed` | `Lease` ve `predecessor_lease_id`. Lease, olayın güvenlik sınıfına uygun sahiplik referansı taşır. | Önceki lease referansı bulunmayan ilk lease kaydı. |
| `ownership_released` | Bırakıldığı bildirilen `RoutineClaimRef` veya `CriticalAuthorizationRef`. | Yeni sahiplik kaydı veya görev iptal onayı. |
| `ownership_revoked` | Geri alındığı bildirilen `RoutineClaimRef` veya `CriticalAuthorizationRef`. | Yeni sahiplik kaydı veya görev iptal onayı. |
| `result_accepted` | `ResultAcceptance`. `execution_id`, `output_manifest_id` ve güvenlik sınıfına uygun `ownership_ref` zorunludur. | Yürütme gözlemi, iptal isteği veya sahiplik referansı bulunmayan sonuç kaydı. |
| `cancellation_confirmed` | `CancellationConfirmation`. `request_id` zorunludur. `ownership_ref` isteğe bağlıdır ve verilirse güvenlik sınıfıyla eşleşir. | `CancellationRequest` veya başka bir olayın payload modeli. |

`event_id` için küresel benzersizlik varsayılmaz. Aynı olay kimliğiyle farklı
payload gelmesi bir çakışmadır. Olay günlüğü bu durumu mükerrer mesaj olarak
atmak yerine kapsamı ve içeriği denetlemelidir. Olay sırası veya yetki fiziksel
zaman damgasından ya da enum sırasından çıkarılamaz. `event_id` ve
`issuer_node_id` alanları domain kararına aittir. Mesaj kimliği, taşıyıcı
gönderici, protokol sürümü, imza ve yeniden iletim bilgileri mesaj zarfında
belirlenecektir.

## Sahiplik ve quorum referansları

| Kayıt | Alanlar ve kapsam |
| --- | --- |
| `RoutineOwnershipClaim` | Zorunlu `claim_id`, `task_id`, `owner_node_id` ve isteğe bağlı `execution_id` alanları `str`'dir. İsteğe bağlı `predecessor_claim`, aynı görevdeki farklı bir `RoutineClaimRef`'tir. |
| `RoutineClaimRef` | `task_id`, `owner_node_id`, `claim_id` üçlüsüyle yerel iddiaya başvurur. Alanlar `str`'dir. |
| `CriticalOwnershipEvidence` | `authorization_id`, `task_id`, `owner_node_id`, `membership_configuration_id` alanları `str`'dir. `fencing_token` pozitif `int`'tir. `scope` bir `CriticalOwnershipScope`, `quorum_decision_ref` bir `QuorumDecisionRef`'tir. `predecessor_authorization` devirde aynı görevdeki farklı bir `CriticalAuthorizationRef` olmalıdır. |
| `CriticalAuthorizationRef` | `task_id` ve `authorization_id` metin alanlarıyla kritik yetki kaydına başvurur. |
| `QuorumDecisionRef` | Dış quorum kararının `decision_id` adlı `str` referansını taşır. |

Rutin tarafta iki bağlantısız düğüm aynı görev ve yerel `claim_id` ile farklı
iddialar oluşturabilir. Düğüm kimliği referansları ayrı tutar. Bu model yerel
revizyon veya küresel tekil epoch gerektirmez. Yerel teklif, zaman aşımı,
yeniden atama ve mantıksal sonuç tekilleştirme mekanizmaları sonraki iş
paketlerinin sorumluluğudur.

Kritik kayıtta beklenen quorum bağı, `task_id`, `owner_node_id`,
`membership_configuration_id`, `fencing_token` ve `scope` alanlarından oluşur.
`GRANT` (`grant_ownership`) ilk sahipliği, `TRANSFER` (`transfer_ownership`)
önceki yetki kaydına bağlanan yeni sahipliği kapsar. Dış karar çözümlendiğinde
bu beş alanın eşleşmesi, kararın geçerliliği ve token'ın yetkili geçmişe göre
artışı koordinasyon katmanında doğrulanmalıdır. Yapısal doğrulama referans
biçimini ve token'ın pozitifliğini kapsar. Tek başına daha büyük bir token
geçerlilik sağlamaz. Rutin claim kimlikleri ile fencing token farklı
ad alanlarına ve anlamlara sahiptir.

Kritik yeni sahiplik, geçerli quorum kararına bağlıdır. Koordinatör kaybı,
azınlık bölümü, manuel onay veya lease süresinin dolması quorumun yerini
tutmaz. Üyelik yapılandırması referansla taşınır. Oy, imza, üyelik geçmişi,
quorum intersection ve güvenli yeniden yapılandırma protokolü sonraki iş
paketlerine aittir.

## Lease

`Lease` bir grantor'un bildirdiği süreyi ve sahiplik bağlamını taşır.

| Alan | Tip ve anlamı |
| --- | --- |
| `lease_id` | Çağıranın sağladığı `str` lease kimliği. |
| `ownership_ref` | İlgili `RoutineClaimRef` veya `CriticalAuthorizationRef`. Görev kimliği bu referansta bulunur. |
| `issuer_node_id` | Lease'i veren düğümün `str` kimliği. Olayın bildiricisi ayrı bir alan taşır. |
| `issued_at` | Veren tarafın bildirdiği fiziksel zaman. Saat dilimi bilgili `datetime`, UTC olarak saklanır. |
| `duration_ms` | Pozitif `int`, milisaniye cinsinden bildirilen süre. |
| `predecessor_lease_id` | Yenilemede önceki, farklı lease kaydının `str` kimliği. İlk kayıtta `None`. |

Yenileme kaydı önceki lease'i referanslar. Önceki kaydın varlığı, aynı sahiplik
bağlamına ait olması ve yenilemenin geçerliliği çalışma anında doğrulanır.
Farklı cihazların UTC saatleri lease geçerliliğini belirlemek için doğrudan
karşılaştırılmaz. Yerel monoton saat kullanımı, sapma sınırları, ağ bölünmesi
ve güvenli sonlandırma sonraki koordinasyon tasarımında belirlenir.

## Sonuç kabulü, iptal ve fencing

`ExecutionStatus.SUCCEEDED` çalışanın yürütme raporudur. `result_accepted`
olayında bildirici, belirli görevin belirli `execution_id` ve
`output_manifest_id` değerlerini ilgili sahiplik bağlamıyla ilişkilendirir.
Gerçek sonuç kabulü, girişim ile çıktı eşleşmesinin ve yetki bağlamının
doğrulanmasını gerektirir. Rutin görevde mantıksal sonuç tekilleştirilir. Kritik
görevde tekilleştirmeye ek olarak yetki ve fencing uygulanır.

`CancellationRequest`, `request_id`, `task_id`, `requester_node_id` metin
alanlarını ve UTC'ye normalleştirilen `requested_at` zamanını taşır. Sonraki
`cancellation_confirmed` olayı `request_id` üzerinden bu isteğe bağlanır. Henüz
sahiplik kaydı yoksa `ownership_ref` boş olabilir. Kritik iptalin yetkisi ve
gerekli güvenli durdurma kanıtı çalışma anında doğrulanır. Sahipliğin geri
alınması, görevin iptal edilmesinden ayrı bir olaydır. Sonuç kabulü ile iptal
çatışırsa kararı yetkili olay geçmişi belirler.

Kritik fencing iki ayrı noktada uygulanmalıdır.

1. **Sonuç kabul noktası** Sonuç kabul edilmeden önce girişimin yetki kaydı ve
   token, o görevin güncel yetkili geçmişiyle doğrulanır.
2. **Yan etkiyi gerçekleştiren kaynak** Kaynak, yeni yetkiyi güvenli biçimde
   uygulayıp kendi işlem sınırında yetkisiz ve eski token'lı istekleri
   engellemelidir. Sonuç kabul noktasındaki kontrol, bu kaynak kontrolünün
   yerine geçmez. Yeni yetki kaydının oluşturulması veya iletilmesi kaynağın
   eski işlemleri durdurduğunu kanıtlamaz.

Yetki kaydını oluşturma, iletme, doğrulama ve kaynakta uygulama ayrı
sorumluluklardır. Bu sözleşme yalnızca kayıt yapısını doğrular.

## Entegrasyon ve açık ekip kararları

| Aşama | Bağlantı noktası ve kesinleştirilecek kararlar |
| --- | --- |
| Phase 6 Input/Output | `output_manifest_id` üzerinden görev, girişim ve manifest bağı, içerik kimliği, bütünlük doğrulaması ve sonuç tekilleştirme anahtarı. Faz 5'te manifest kimliği opak bir metindir. |
| G-2.1 | Quorum karar referansının ad alanı ve çözümleme yöntemi, üyelik yapılandırması kimlikleri, kararın beş alanla eşleşmesi, geçerli üyelik ve karar kanıtının biçimi. |
| G-2.2 | Yetkili sahiplik geçmişi ve monoton token kapsamı, lease yenileme ve saat kuralları, güvenli durdurma kanıtı, sonuç ve kaynak sınırlarındaki fencing. |
| G-3.1 | Olay günlüğü ve mesaj zarfı eşlemesi, karar bildiricisi ile taşıyıcı gönderenin ayrımı, olay kimliği kapsamı, aynı kimlikle farklı içeriğin saptanması, sıralama ve yeniden oynatma politikası. |

Öneri genel iş paketlerini tanımlar. G-2.1, G-2.2 ve G-3.1 satırları alt iş
kalemleri için önerilen bağlantı noktalarıdır. Ekip sözleşmeleri kesinleştiğinde
referans biçimleri, kimlik kapsamı ve taşıma eşlemesi birlikte doğrulanmalıdır.

Alanlar, enum üyeleri, referans tipleri ve olay–payload eşleşmesi yerel olarak
doğrulanır. Yanlış tipler `TypeError`, geçersiz değerler veya uyumsuz
kombinasyonlar `ValueError` üretir. Modeller dondurulmuş ve `slots` kullanan
dataclass'lardır. Kimlikleri ve zamanı çağıran sağlar. Model geçerliliği,
consensus, quorum güvenliği, lease geçerliliği, fencing uygulaması, olay
günlüğü, idempotency veya replay koruması hakkında bir garanti vermez.
