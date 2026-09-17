# AES-GCM storage-authentication premise dossier

Q28a pilot, reviewed 2026-09-17 against repository base
`712afc03624eefbf29539c44d7bab6b8c15b2bf2`. The consumer is per-extent
authentication under R-10-022 through R-10-024. This record qualifies the
**scope of a conditional claim**, not a release key lifetime or a deployed
cryptographic implementation. Missing production inputs below refuse numerical
qualification. Q28a's dossier can be complete while that qualification is refused.

## Selected construction and claim

The pilot selects AES-256-GCM, a 96-bit IV and a 128-bit tag. These are dossier
parameters, not an amendment selecting the filesystem's production key size or
invocation budget. The algorithm owners are [FIPS 197, updated 2023-05-09](https://doi.org/10.6028/NIST.FIPS.197-upd1)
and [SP 800-38D, November 2007](https://csrc.nist.gov/pubs/sp/800/38/d/final).
The [2026-06-01 revision consultation](https://csrc.nist.gov/pubs/sp/800/38/d/r1/2prd)
is a pre-draft call with no replacement specification. Its proposed wider
block variant is outside this pilot. A future revision requires a new reading
rather than silently replacing the selected edition.

[AesGcm.v](../../proofs/AesGcm.v) supplies the functional specification:
`gcm_encrypt` with `nk = 8`, `gcm_open` with `t_bits = 128`, and the
`demo_aes256` parameter witness. The witness's fixed IV is a functional test
input, not a nonce-generation procedure. Neither the optional bound in
`AeadParameters` nor an entry in this dossier enforces a usage limit.
The correspondence domain restricts keys to 32 bytes, IVs to 96 bits, tags to
128 bits, AAD to at most `2^64 - 1` bits and each plaintext/ciphertext to at
most `128 * (2^32 - 2)` bits. Production wrappers must enforce these lengths
and the counter limit; the total Gallina functions alone are not that guard.

The candidate claim, **GCM-EXTENT-AUTH**, is rejection of a fresh forged
`(IV, AAD, ciphertext, tag)` under one uniformly selected secret domain key.
It excludes replay of an authentic tuple. The storage consumer additionally
owes an injective AAD encoding binding its domain, object/extent identity and
generation, and an authenticated index with the nonce/tag placement R-10-022a
requires. Those storage correspondences are absent here; GCM authenticity alone
does not prove freshness, rollback resistance, dedup confidentiality or the
identity of the extent a caller meant to read.

## Game and reduction source

The selected paper is Niwa, Ohashi, Minematsu and Iwata,
[*GCM Security Bounds Reconsidered*, full version, ePrint 2015/214](https://eprint.iacr.org/2015/214.pdf),
section 4 and Theorem 3, equation (29). Its classical authenticity game allows
encryption and decryption queries, distinct encryption nonces, no replay of an
encryption result to decryption and no repeated decryption query. Winning means
a non-rejected decryption. For an ideal 128-bit permutation its bound is

```text
B = (sigma + q + v + 1)^2 / (2 * 2^128)
  + 32 * (q + v) * (sigma + q + 1) * (ellN + 1) / 2^128
  + v * (ellA + 1) / 2^128.
```

Here `q` counts encryptions, `v` decryption attempts, `sigma` total encrypted
plaintext blocks, `ellN` maximum nonce blocks and `ellA` maximum AAD-plus-message
blocks across both query kinds, with each string rounded up separately to
128-bit blocks. The pilot has `ellN = 1`. This is a probability bound under
that game, not an attack-cost lower bound or quantum theorem. No paper code or
proof artifact is incorporated or locally replayed.

The proposed concrete claim is bounded by
`min(1, B + epsilon_AES + epsilon_nonce + epsilon_key)` through a hybrid:
replace the key source by uniform (`epsilon_key`), exclude IV collisions
(`epsilon_nonce`), replace keyed AES by the ideal permutation (`epsilon_AES`),
then apply the selected bound. This is the dossier's reduction plan, not a
machine-checked theorem. No term has a measured numerical value here. The
AES term is the distinguishing advantage of the simulator for this very
adversary, not generic collision resistance. It allows classical chosen-block
forward queries and a uniformly sampled 256-bit key; no inverse oracle is
needed by GCM. Simulator time, memory and total AES calls must be charged from
the admitted encrypt/decrypt workload, including failed attempts and GHASH work.
No unbounded-resource adversary receives a small AES advantage by assertion.

The register's per-extent-random nonce policy does not establish distinctness.
For independent uniform 96-bit draws the collision term is at most
`q * (q - 1) / (2 * 2^96)` by a pairwise union bound. An actual DRBG requires
its own distinguishing term and reset/fork/restore analysis before using that
formula. Linearity of a nonce value does not exclude two separately drawn equal
values. Key derivation and multiple domains also need their joint distribution
and aggregate advantage accounted for; a one-key bound is not a fleet bound.

## Claim-indexed premise ledger

These rows instantiate R-05-162a's classes for this pilot and retain their
R-17 residuals. They do not replace the complete R-18-031 release ledger.

| Premise | Class and residual | Consuming claim and status |
| --- | --- | --- |
| AES-256 forward PRP security for the simulator's declared resources | Computational-security conjecture; R-17-049, R-17-049f | GCM-EXTENT-AUTH's `epsilon_AES`; unproved, no numerical advantage assigned |
| A uniform permutation in the selected theorem | Idealized-model premise; R-17-049f | The ideal-game bound B; replacement by AES is the separate PRP hybrid, not a functional equality |
| Uniform key and collision-controlled nonce generation | Computational/entropy premises; R-05-077a, R-17-049 | The key/nonce hybrid terms; S5 and S6 retain physical-source and recording qualification, DRBG security and reset-safe usage remain unproved |
| Faithful standard transcription and storage-to-game correspondence | Machine/specification premise; R-17-016, R-17-049 | Applying the reference to an actual extent; functional vectors do not prove complete correspondence |
| Concrete classical/quantum attack resources | Concrete attack-estimate premise; R-17-049e/f | No numerical strength or years-of-security claim is made; lattice estimator fields are n/a for AES, not evidence for the lattice consumers |
| Human consent | Human premise; R-17-013 | n/a for this authenticity game; access authorization and powerbox claims have separate consumers |

GHASH requires its keyed polynomial-family bound in this construction, not
collision resistance of an arbitrary public digest. Its subkey is `AES_K(0)`;
it is not an independently supplied random hash key in the concrete system.
The same AES key masks the tag and drives counter encryption. The selected
GCM analysis handles that coupling in its ideal experiment. A generic hash
flag, an ideal Keccak premise or an HMAC PRF theorem cannot replace it.
ROM, QROM and SHAKE domain separation are n/a to this AES-GCM claim. The GHASH
input encoding, length fields and counter construction remain the standard's;
the consumer's AAD encoding and key-domain separation remain explicit joins.

## Axiom-free oracle counterexample

[OracleInstantiation.v](../../proofs/OracleInstantiation.v) defines the uniform
finite Boolean-function experiment by enumerating four equally weighted tables.
An attacker reads the answer at `false` and predicts the fresh answer at `true`.
`fresh_ideal_answer_has_two_successes` proves two successes for every such
deterministic strategy. A concrete always-false oracle admits four successes
for `guess_false`; `ideal_bound_does_not_transfer_to_every_implementation`
refutes the transferred bound. The attacker is constructed, not assumed.

All these terms are closed under the global context. Uniform weighting is in
the experiment's definition and the theorem's subject, so the empty assumption
report says nothing about a concrete hash having that distribution. This is
the R-05-162a review case, not a GCM reduction or a quantum-oracle simulation.
The actual GCM paper uses a permutation rather than this toy function; neither
model is established by a functional AES or SHA-3 proof. Replay with
`python tools/run.py proofs`; the generated portable receipt owns the compiled
symbol enumeration and assumptions.

## Attack evidence and invalidation

The dated survey selects the corrected GCM bound above. [Iwata, Ohashi and
Minematsu's 2012 proof repair](https://eprint.iacr.org/2012/438.pdf) invalidates
earlier proof reasoning; that history does not prove AES hard. This dossier
does not transplant an old bound or treat rejection of an attack as a lower
bound on all attacks. The 2015 theorem is the chosen conservative bound, not
a claim that no subsequent tighter analysis exists.

No concrete AES attack estimator is executed. Its revision, calibrated gate
costs, physical qubits, error correction, runtime, memory, success probability
and finite-size correction are **n/a: numerical qualification refused**.
Quantum chosen-oracle security, related-key attacks, nonce misuse, leakage,
faults and implementation attacks are not covered by the classical game.
Post-quantum claims need a suitable game and resource analysis of their own;
a quantum resource count is not a forecast of a machine's arrival.

| Changed input | Invalidated claim/evidence | Required owner action |
| --- | --- | --- |
| AES key size, tag/IV width or GCM edition | Parameter binding, game correspondence and B specialization | Re-read this dossier and the functional reference before qualification |
| Corrected theorem, new attack or estimator revision | Affected bound or numerical estimate, not automatically the functional vectors | R-05-059 reduction owner records attack model, resources and changed conclusion; no release until reviewed |
| Larger extent/AAD, more attempts or retained key lifetime | Resource tuple and all aggregate bounds | Storage composition supplies enforced per-key counts and recomputes qualification |
| Key/nonce derivation, reboot or snapshot behavior | Key/nonce hybrid premises | Entropy, DRBG and storage owners re-establish joint freshness and reset behavior |
| Emitted binary or source semantics | Reference-to-artifact correspondence, binary constant time and masking evidence | Revalidate the changed layer; a matching dossier does not preserve these proofs |

Release qualification re-reads primary sources and their corrections. No row
authorizes negotiated fallback, shorter tags or runtime algorithm substitution.

## Stored-secret horizon review

R-17-049g's minimum starts at each datum's creation, not at encryption, backup,
key rotation or the date of this review. The scope is durable user extents,
replicas/backups, their domain keys and recorded transfer traffic. Each datum
needs a creation-to-required-confidentiality interval of at least twenty years;
longer application obligations require separate qualification. AES-GCM
authenticity supplies no proof of that confidentiality duration.

Controlled replicas can be re-encrypted into a newly admitted generation,
with every copy and wrapped-key backup inventoried. Deleting a live key is not
proof that backup, crash or physical remnants are gone. R5/R5a and Q7 own
physical lifetime evidence. An adversary's retained ciphertext cannot be
re-encrypted away, and later migration cannot undo its exposure after a break.
Recorded key-establishment traffic retains the hybrid construction's own
assumptions; the ML-KEM and classical-hedge dossiers are still owed.

Before release the storage/update owners must supply per-key usage and failed
verification limits, replica/erasure coverage, support duration, longer-horizon
applications and the remaining finite update-counter budget. No device or
operational support commitment exists for this pilot. Generation migration
must preserve the rollback floor while leaving budget for subsequent fixes.
The ROM's SLH-DSA verifier is immutable: updating the storage cipher cannot
repair a broken ROM verifier, and reprovisioning/replacement feasibility needs
its own supported plan. These missing inputs refuse a twenty-year deployment
claim; they add neither clock-based expiry nor degraded admission.

## Acceptance and remaining consumers

Q28a's checks are answered by the fixed consumer and parameter binding, the
explicit game and reduction plan, the class-indexed ledger, the compiled oracle
counterexample, the invalidation table and the horizon review. The outcome is
**dossier accepted; numerical and deployment qualification refused**. The
unmet conditions have owners above and do not become new zero-cost work.

Separate dossiers remain for ML-KEM-1024 key establishment, ML-DSA-87 signatures,
the ROM's SLH-DSA hash family, content/Merkle and measured-boot/update digests,
keyed deduplication, KDFs and HMAC-DRBG, and each session composition consuming
them. The [crypto source inventory](proof-reuse/crypto.md) supplies starting
sources, not those dossiers. R-05-059's complete reductions, target refinement,
constant time, masking, entropy qualification, and the release ledger remain
open; this pilot confers no whole-entry discharge.
