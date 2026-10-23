# Pinned proof-reference consumers

The gitlinks below select source references for existing work. They add no proof
dependency, build step, shipped implementation or discharged requirement. The
[third-party register](../../THIRD-PARTY.md#pinned-as-submodules) owns their selected
revisions and terms; the subject records own the qualification findings. Only
URLs and gitlinks are conveyed here. No upstream code or dependency closure is
copied into the authored tree.

Read the selected sources online through the immutable links below, or acquire
only the named repositories with:

```console
git submodule update --init -- upstream/perennial upstream/s2n-bignum upstream/vasn
git ls-files -s -- upstream/perennial upstream/s2n-bignum upstream/vasn
```

Use the index-selected commits. `--remote` would change the selection and
`--recursive` would acquire dependencies outside this reading. Perennial's
`master` branch setting identifies its Rocq lineage; its default Lean lineage
does not provide the required crash logic. Normal gates initialize none of these
references or execute their scripts.

## Storage: write permissions and recovered state

[`upstream/perennial`](../../upstream/perennial) selects the Rocq PoWER
correspondence edition. Start at
[`src/program_proof/verus/wrs.v`](https://github.com/mit-pdos/perennial/blob/65884f2494ce65c5369094050dfb7eca19299152/src/program_proof/verus/wrs.v):
`wpc_Simulate` separates `P` over the durable/current disks from the durable-disk
crash predicate `Pcrash`, with an explicit `Pcfupd` crash update and write-preservation premises;
`wp_wr_sm` relates these to an abstract recovered state. These are the selected
interface shapes for M5.3's crash proof and M5.4's transaction join, as
[SYS-POWER](../assurance/proof-reuse/systems.md#sys-power-write-permissions-joined-to-a-crash-invariant-in-perennial)
records.

The next consumer remains [StorageRecovery.v](../../proofs/StorageRecovery.v)
under the [selected complete-prefix recovery policy](storage-recovery-policy.md).
Its byte decoder, authenticated transaction completeness, nonce reservation,
checkpoint/acknowledgment ordering and retained-root predicates need to populate
the interface. The [block-device contract](../../interfaces/block-device-contract.md)
permits bit tears; the donor's `wpc_Write` whole-old/whole-new outcome and
`wpc_Barrier_disk` require a persistence adapter before a local device theorem can
use this shape. Locked-prover compatibility, the exact dependency closure and a
native assumption/kernel audit remain prerequisites for any proof import.

## Cryptography: functional results and public event traces

[`upstream/s2n-bignum`](../../upstream/s2n-bignum) supplies two concrete comparisons:

| Source and statements | Existing consumer and next comparison |
| --- | --- |
| [`arm/proofs/mlkem_ntt.ml`](https://github.com/awslabs/s2n-bignum/blob/45ad6720d0a86b588661f2d699cc383d0ff89e71/arm/proofs/mlkem_ntt.ml): `MLKEM_NTT_SUBROUTINE_CORRECT`, `MLKEM_NTT_SUBROUTINE_SAFE` | M3.4b's [PqArith.v](../../proofs/PqArith.v) and [MlKem.v](../../proofs/MlKem.v): compare coefficient representation, twiddle tables, range premises and the arithmetic postcondition before lowering. |
| [`arm/proofs/sha3_keccak_f1600.ml`](https://github.com/awslabs/s2n-bignum/blob/45ad6720d0a86b588661f2d699cc383d0ff89e71/arm/proofs/sha3_keccak_f1600.ml): `SHA3_KECCAK_F1600_SUBROUTINE_CORRECT`, `SHA3_KECCAK_F1600_SUBROUTINE_SAFE` | M7.1f's [boot-crypto consumer](../../firmware/crypto/README.md), [Keccak.v](../../proofs/Keccak.v) and [C permutation](../../firmware/crypto/keccak.c): compare the 24-round permutation, state layout and constants separately from padding, sponge and signature verification. |

The `_SAFE` statements make the event list a function of public pointers, code,
stack and return placement and bound memory accesses independently of secret
coefficients or state. Use this separation when defining the local binary
judgment for R-05-062/R-05-063. The
[`SOUNDNESS.md` limits](https://github.com/awslabs/s2n-bignum/blob/45ad6720d0a86b588661f2d699cc383d0ff89e71/SOUNDNESS.md)
and [crypto qualification](../assurance/proof-reuse/crypto.md#s2n-bignum-machine-code-arithmetic)
remain applicable: HOL Light/AArch64 execution is not CHERI-RV64/Sail execution,
and modeled instruction/address observations do not establish physical timing or
masking. No assembly leaf or alternative to Fiat-Crypto is admitted by this pin.

## ASN.1: an independent PER comparison source

[`upstream/vasn`](../../upstream/vasn) supplies the
[`vasn/src/uper/format.rs`](https://github.com/zhouxt1/vasn/blob/5db5727c06a3e996be6f87c3f0fa19d37817b739/vasn/src/uper/format.rs)
and
[`vasn/src/aper/format.rs`](https://github.com/zhouxt1/vasn/blob/5db5727c06a3e996be6f87c3f0fa19d37817b739/vasn/src/aper/format.rs)
interfaces. Their `surjective`, `injective`, `weak_injective` and `is_format`
predicates expose decoded values, consumed bits and the `SameVer`/`DiffVer`
distinction. `SameVer` injectivity concerns the consumed encoding; discarding
unknown extensions does not establish whole-input canonicity.

The next consumer is R-18-029's ASN.1-to-Narcissus front end, still outside the
priced work in [the proof map](../assurance/unassigned-proof-map.md#4-wire-formats-the-wasm-guest-and-the-radio-reference-machines).
After selecting and qualifying its Narcissus descriptor, compare fragmentation,
alignment, extensions, consumed bits and refusal behavior over identical schema
and input identities. An executable oracle additionally needs its Verus,
`vbits`/`vsimd`, dependency and schema-source terms read, an isolated build and
input/output identity capture. The
[vasn qualification](../assurance/proof-reuse/parsers.md#vasn-licensed-per-proof-and-differential-oracle-candidate)
retains the compiler and primitive-contract trust boundary. This pin adopts no
parser route, proves no descriptor fidelity and supplies no Rocq or bounded
Clight refinement.
