# Authored C language profile

The active authored C uses modern declarations and explicit initialization within
the compiler and semantic boundary of each consumer. This profile is a maintenance
policy; the [scalar source-value contract](contracts/compiler-source-values.md)
and [purecap ABI](contracts/purecap-abi.md) own target admissibility and layout.
[The plan](../../PLAN.md#c-modernization) owns modernization scope and acceptance.

## Language boundaries

| Consumer | Language boundary |
| --- | --- |
| Authored component host builds and native C controls | ISO C17, strict prototypes, existing warnings as errors and applicable sanitizer controls |
| Contained purecap compiler | Its admitted scalar CompCert-C profile: C99 constructs and supported C11 frontend features, subject to its source-value and backend restrictions |
| C refinement through VST | The selected Clight AST and semantics, with frontend correspondence and the stock-to-contained semantics bridge established separately |
| Sail runtime, imported sources and external experiments | Their existing build contracts and pinned source identities |
| Generated C and headers | Their owning generators and consumers' language profiles |

The [CompCert language manual](https://compcert.org/man/manual005.html) describes
C99 support with selected C11 additions, including `_Static_assert`, `_Alignof`
and `_Generic`. Its [language options](https://compcert.org/man/manual003.html)
accept C99, C11 and C18 modes; selecting a mode does not supply every feature of
that standard. C17/C18 is the host baseline, not a claim that the target implements
all of C17. C23 syntax needs a qualified frontend and consumer before adoption.

VST consumes Clight generated from C, as the
[`clightgen` guide](https://github.com/AbsInt/CompCert/blob/master/export/README.md)
describes. Thus the relevant limit is the supported source-to-Clight translation
and the proof's semantics. The repository's
[C-refinement qualification](../assurance/c-refinement-foundation-qualification.md)
and [semantics bridge](../assurance/c-semantics-bridge.md) record the open
foundation and correspondence obligations. Authored C and passing differentials
do not by themselves supply VST refinement proofs.

## Source conventions

- Declare locals near their first use and initialize them there when evaluation
  order and failure behavior permit it. Put an induction variable in its `for`
  initializer when its value is not needed after the loop. Keep an explicit
  outer variable when a later decision uses the terminating index.
- Qualify immutable local values and read-only inputs with `const` where that
  expresses the existing access contract. Keep stored pointer types, capability
  representations and public function interfaces consistent with their owners.
- Use designated struct initializers when field names clarify a record. Preserve
  existing zero initialization, including omitted fields, and avoid depending on
  padding bytes. Explicit bounded copies retain their ordering and alias behavior.
- Use prototypes, including `(void)` for no arguments. Host compilation enables
  `-Wstrict-prototypes` alongside the existing warning policy.
- Use compile-time assertions for layout or capacity relationships already fixed
  by an owner. A new assertion must not silently select an unresolved composition
  parameter or assume that host and purecap pointer layouts agree.
- Keep fixed-width wire fields and existing integer predicate interfaces. A change
  to `bool`, an enum, `size_t`, alignment, `restrict` or a static array-parameter
  bound can change a contract and needs its own justification. C23 aliases and
  attributes are not required for modern declarations or initialization.

The [kernel's compiler findings](../../kernel/README.md#under-the-contained-compiler)
explain restrictions beyond standard C. The
[atomic interface](../../copy-service/include/vos_copy_atomic.h) deliberately
uses C11 atomics on the host and separately bound ISA operations on the target.
Host pointer-to-integer overlap checks are host seams; the target source-value
contract does not admit pointer round trips through `uintptr_t`.

## Source identities and validation

Edit generated C through its generator. Preserve imported model/runtime sources,
retained execution snapshots and the firmware bytes fixed by the
[signature campaign](../../firmware/crypto/README.md#hosted-target-campaign) and
[target chain](contracts/boot-handoff.md#9-the-target-chain) unless the change also
performs their required restaging and acceptance. Cosmetic edits alone do not
justify invalidating those campaigns.

Refresh affected package bindings and composition views through their owners.
Update mutation seeds when a changed declaration moves their exact source anchor;
the seed must still produce the same executable defect. Run focused existing
controls and follow the [hosted validation handoff](../../AGENTS.md#tool-execution-and-validation).
Host native compilation is distinct from compiling and executing target components
with the contained compiler. A deferred target campaign supplies no target verdict.
