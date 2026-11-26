# G-1.2 / Phase 2 — Görev güvenliği ve devredilebilirlik

`resolve_task_policy` bir görevin güvenlik sınıfından ve devredilebilirlik
biçiminden statik politika gereksinimlerini üretir. Politika, çalışma anında
atama, yeniden deneme veya devir izni vermek için gereken kontrollerin bir
bölümünü tanımlar.

## Güvenlik sınıfı

Güvenlik sınıfı, görev önceliği ve son teslim zamanı birbirinden bağımsızdır.
`TaskSecurityClass` değerleri Python 3.12 uyumlu bir `StrEnum` ile tanımlanır.

- `ROUTINE` (`routine`) için ağ bölünmesi sırasında mükerrer yürütme tolere
  edilir. Tekrar yürütme kabul edilemez ek yan etkilere yol açmamalıdır ve
  mantıksal görev sonucu tekilleştirilmelidir. Devredilebilirlik ve çalışma anı
  koşulları elverdiğinde yerel yeniden atama mümkündür. Bu sınıf küresel tekil
  epoch varsayımı olmadan çalışabilir.
- `CRITICAL` (`critical`) için tek yetkili sahip gerekir. Hem ilk sahiplik hem
  yeni sahiplik verilmesi, düğümler arası devir dahil, quorum onayına bağlıdır.
  Quorum yoksa yeni sahiplik verilmez. Manuel onay ve lease süresinin dolması
  quorum gereksinimini karşılamaz. Sahiplik değiştikçe fencing token artmalıdır.
  Token, hem sonuç kabul noktasında hem yan etkiyi gerçekleştiren kaynakta
  doğrulanır. Sonuç kabulü ayrıca mantıksal görev başına tekilleştirilir.

## Devredilebilirlik

`TaskTransferability`, düğümler arası devir biçimini `StrEnum` ile tanımlar.
İlk atama, aynı düğümde yeniden deneme, yeniden atama ve düğümler arası devir
ayrı işlemlerdir.

- `RESTART` (`restart`) başka düğümde sıfırdan yürütmeyi destekler. Kritik
  görevlerde devir için önceki yan etkilerin güvenli biçimde ele alınması gerekir.
- `CHECKPOINT` (`checkpoint`) başka düğümde doğrulanmış ve uyumlu bir
  checkpoint üzerinden devam etmeyi destekler. Geçerli checkpoint yoksa bu
  devir biçimi kullanılamaz ve kendiliğinden `RESTART` uygulanmaz. İlk yürütme
  için bu politika bir checkpoint gerektirmez.
- `NON_TRANSFERABLE` (`non_transferable`) düğümler arası devri dışlar. İlk
  atama ve aynı düğümde yeniden deneme kendi koşullarıyla değerlendirilir.

## Politika alanları ve matris

`TaskPolicyRequirements`, `frozen=True` ve `slots=True` ile tanımlanmış bir
dataclass'tır. Tablodaki sayılar aşağıdaki alan sırasına karşılık gelir.

| No | Alan | `True` değerinin anlamı |
| --- | --- | --- |
| 1 | `duplicate_execution_tolerated` | Kabul edilemez ek yan etki oluşmadığı sürece mükerrer yürütme tolere edilir. |
| 2 | `result_deduplication_required` | Bir mantıksal görevin sonucu yalnızca bir kez kabul edilmelidir. Kritik görevlerde bu kontrol quorum ve fencing ile birlikte uygulanır. |
| 3 | `quorum_required_for_new_ownership` | İlk sahiplik ve sonraki her yeni sahiplik için quorum onayı gerekir. |
| 4 | `result_fencing_required` | Fencing token sonuç kabul noktasında doğrulanmalıdır. |
| 5 | `resource_fencing_required` | Fencing token yan etkiyi gerçekleştiren kaynakta doğrulanmalıdır. |
| 6 | `inter_node_transfer_supported` | Görevin yapısı düğümler arası devri destekler. Çalışma anında ayrıca yetkilendirme gerekir. |
| 7 | `checkpoint_required_for_transfer` | Düğümler arası devir doğrulanmış ve uyumlu checkpoint gerektirir. |
| 8 | `safe_restart_required_for_transfer` | Başka düğümde sıfırdan yürütmeden önce önceki yan etkiler güvenli biçimde ele alınmalıdır. |

`False`, ilgili alanın bu kombinasyonda gereksinim veya destek belirtmediğini
gösterir. Örneğin, 8. alanın `False` olması diğer işlemlerin güvenliğini çalışma
anında değerlendirme gereğini ortadan kaldırmaz. Altı kombinasyonun tümü
temsil edilebilir. Bir kombinasyonun seçilmesiyle yürütme veya devir yetkisi
oluşmaz.

| Güvenlik sınıfı | Devredilebilirlik | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ROUTINE` | `RESTART` | True | True | False | False | False | True | False | False |
| `ROUTINE` | `CHECKPOINT` | True | True | False | False | False | True | True | False |
| `ROUTINE` | `NON_TRANSFERABLE` | True | True | False | False | False | False | False | False |
| `CRITICAL` | `RESTART` | False | True | True | True | True | True | False | True |
| `CRITICAL` | `CHECKPOINT` | False | True | True | True | True | True | True | False |
| `CRITICAL` | `NON_TRANSFERABLE` | False | True | True | True | True | False | False | False |

## Mimari sınırlar ve entegrasyon

1. `is_valid_transition` yapısal geçiş uygunluğunu sorgular ve geçersiz girdide
   `False` döndürür. [Phase 1 sözleşmesi](task_lifecycle.md)
2. Phase 2 içindeki `resolve_task_policy`, geçerli iki enum üyesinden bir
   politika nesnesi üretir. Ham string, `None` veya başka bir enum türünün
   üyesiyle çağrıldığında `TypeError` üretir. Serileştirilmiş veriyi enum
   üyelerine dönüştürmek çağıranın sorumluluğudur. Çözümleyici aynı girdiler
   için eşit değerler üretir. Global durumu değiştirmeden ve saat, ağ, dosya
   ya da veri tabanı erişimi olmadan çalışır.
3. Çalışma anında zamanlayıcı, yapısal geçiş ve devir desteğini aday işlemleri
   değerlendirirken kullanır. Koordinasyon katmanı, yeni kritik sahiplikte
   quorum onayını, lease durumunu ve artan fencing token'ı ele alır. Sonuç kabul
   katmanı mantıksal sonucu tekilleştirir ve kritik token'ı doğrular. Yan etkiyi
   uygulayan kaynak aynı doğrulamayı kendi işlem sınırında yapar. Yürütme
   katmanı checkpoint'in geçerliliğini ve uyumluluğunu veya kritik yeniden
   başlatmada önceki yan etkilerin güvenli biçimde ele alındığını doğrular.
