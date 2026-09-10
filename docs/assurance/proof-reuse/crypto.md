# Cryptography, masking and numerical proof reuse

This inventory records primary-source readings on 2026-09-10. A strong reference here has identifiable authors, a precise claim and an accessible proof artifact; a paper, production deployment or an upstream green badge alone does not establish that this project's obligation is proved. The entries distinguish established developments from research candidates and record the actual acquisition barrier. No foreign development listed here is replayed or incorporated by this inventory. Branch links identify the edition read on that date when a commit is not recorded. The admitted prover is the version in [the Rocq lock](../../../tools/opam/rocq.lock), currently 9.2.0; historical 8.20 and 9.1 measurements in [the third-party register](../../../THIRD-PARTY.md) are historical evidence.

The governing obligations are [the requirements register](../../requirements-register.md): R-05-059 separates functional correctness, binary constant time and security reductions; R-05-060 selects Fiat-Crypto; R-05-061 records the interim F*/Z3 route; R-05-062/R-05-063 require a direct binary constant-time judgment; R-05-004a and R-15-053a add composition and the glitch/transition probing model. Cryptographic reductions also retain R-05-077a's entropy preconditions. A theorem in another prover is a proof source until a checked bridge reaches these statements.

The completed M3.4a, M3.4c-i and M3.4d items in [the implementation plan](../../implementation/implementation-checklist.md) supply [Keccak](../../../proofs/Keccak.v), [SHA-256/HMAC](../../../proofs/Sha256.v), [HMAC-DRBG](../../../proofs/HmacDrbg.v), [AES-GCM](../../../proofs/AesGcm.v) and [the ROM verifier statement](../../../proofs/RomVerifier.v). Their headers explicitly limit the claims: the primitive files are functional references, and the ROM file has no SLH-DSA verification algorithm. Their compilation and known-answer examples do not close the remaining refinement, security or constant-time obligations. These files remain useful comparison targets even where a milestone is checked.

## Native Rocq and Coq developments

### Fiat-Crypto arithmetic and serialization

**Established reference; prospective reuse under M3.4c-ii.** Andres Erbsen, Jade Philipoom, Jason Gross, Robert Sloan and Adam Chlipala, *Simple High-Level Code for Cryptographic Arithmetic: With Proofs, Without Compromises*, IEEE S&P 2019. [Paper and publication](https://doi.org/10.1109/SP.2019.00005). The project already pins `e6946985`; the current upstream `master` resolves to `bf60a06a0a944770f39ed916fdce4326c5f44608` at this reading. Updating the pin is not needed to use the existing artifact.

The Coq development proves arithmetic transformations and code generation. For a concrete reusable boundary, [`src/Arithmetic/Freeze.v`](https://github.com/mit-plv/fiat-crypto/blob/e6946985/src/Arithmetic/Freeze.v) carries `eval_freeze_to_bytesmod`, `eval_from_bytesmod` and their partition lemmas, relating field representations and bytes. These address R-05-060 and the serialization/refinement seams of M3.4c-ii; they do not prove curve-protocol security, masking, or the CHERI binary's timing. The required next step is a reproducible pinned generator emission with the selected modulus and representation, followed by a relation to the consumer's representation, not an arbitrary generated C file copied into a proof directory.

**Terms:** upstream [`COPYRIGHT`](https://github.com/mit-plv/fiat-crypto/blob/e6946985/COPYRIGHT) offers `MIT OR Apache-2.0 OR BSD-1-Clause`; the existing repository election is Apache-2.0. [`LICENSE-APACHE`](https://github.com/mit-plv/fiat-crypto/blob/e6946985/LICENSE-APACHE) and [`AUTHORS`](https://github.com/mit-plv/fiat-crypto/blob/e6946985/AUTHORS) are read. Any emission must retain the applicable notice and identify the generator pin and recipe. This is the strongest compatible implementation candidate, but running and integrating its generator is the existing M3.4c-ii work, not a completed consequence of finding it.

### Alix Trieu's verified NTT

**Peer-reviewed native proof; acquisition and port remain open.** Alix Trieu, *Formally Verified Number-Theoretic Transform*, IACR Communications in Cryptology 2(4), 2026, [DOI 10.62056/ahbn-4tw9](https://doi.org/10.62056/ahbn-4tw9). [Artifact record 18504002](https://zenodo.org/records/18504002) contains a source archive and a [README](https://zenodo.org/records/18504002/files/README.md?download=1), tested with Coq 8.20.1, OCaml 5.0.0 and Fiat-Crypto `af03839247c545987c20e99342ab2bbfcd517863`.

The README identifies `NTT/PolynomialCRT.v`, `NTT/NTT.v` with `decompose_is_bitrev`, `NTT/GallinaNTT.v`, `NTT/BedrockNTT.v` and `NTT/BedrockNTTCT.v`. `MLKEM_Barrett.v`, `MLKEM_Signed.v` and `MLDSA_Montgomery.v` instantiate complete/incomplete transform generation. This directly shortens M3.4b's polynomial/NTT work and R-05-067's implementation obligations. It supplies neither full ML-KEM/ML-DSA schemes nor their security reductions, and its CT theorem does not discharge R-05-062's bespoke binary judgment.

**Terms:** the live Zenodo API returns no license field; the README gives build/import instructions but no standard license instrument. The article's CC BY grant is a publication grant and is not silently extended to the separate archive. The existing [third-party disposition](../../../THIRD-PARTY.md#start-froms-read-and-declined) therefore stands. The personal fork's older branches are not established as the deposited edition. **Disposition:** retain as a high-priority proof source; no code copied, and no assertion that permission is absent everywhere. A clear grant for the deposited sources, followed by a 9.2/assumption audit, is the missing acquisition evidence.

### VST SHA-256 and HMAC refinement

**Established native reference; not a drop-in.** Andrew W. Appel, *Verification of a Cryptographic Primitive: SHA-256*, ACM TOPLAS 2015, and the Princeton VST contributors. [`sha/`](https://github.com/PrincetonUniversity/VST/tree/f384d2db/sha) at the already-read `f384d2db` includes a Gallina SHA-256 specification, Clight code and VST refinement. A concrete theorem is `body_SHA256_Final` in [`verif_sha_final.v`](https://github.com/PrincetonUniversity/VST/blob/f384d2db/sha/verif_sha_final.v), proving the body against `SHA256_Final_spec` through `semax_body`.

This provides a model for the refinement missing from [Sha256.v](../../../proofs/Sha256.v), M3.4c-i and R-05-059. The representations differ: local SHA-256 uses MSB-first Boolean lists; VST uses its integer/byte and C-memory framework. A bridge must preserve padding, length limits, endianness and API state. C correctness neither supplies binary CT nor HMAC's PRF reduction.

**Terms:** [`LICENSE`](https://github.com/PrincetonUniversity/VST/blob/f384d2db/LICENSE) assigns the test-suite directories including `sha` to BSD-2-Clause, with the full instrument in [`LICENSE-OPAM`](https://github.com/PrincetonUniversity/VST/blob/f384d2db/LICENSE-OPAM), copyright Andrew W. Appel et alia. The repository also contains separately governed CompCert files. [The existing route analysis](../../../THIRD-PARTY.md) records package incompatibility and extensionality/proof-irrelevance assumptions, and that opam installation does not install these examples. Those assumptions conflict with the presently empty declaration, regardless of the permissive `sha` license. Reuse the statement/proof architecture until a scoped bridge is admitted.

### VST and FCF HMAC-DRBG

**Established reduction plus implementation refinement; native but incompatible as an immediate import.** Katherine Q. Ye, Matthew Green, Naphat Sanguansin, Lennart Beringer, Adam Petcher and Andrew W. Appel, *Verified Correctness and Security of mbedTLS HMAC-DRBG*, ACM CCS 2017. [Author-hosted paper](https://www.cs.princeton.edu/~appel/papers/verified-hmac-drbg.pdf). The development joins a probabilistic security proof with C verification in Coq. At VST `f384d2db`, [`hmacdrbg/verif_hmac_drbg_generate.v`](https://github.com/PrincetonUniversity/VST/blob/f384d2db/hmacdrbg/verif_hmac_drbg_generate.v) contains `generate_correct` and `body_hmac_drbg_generate`; the `hmacfcf/` material is the related security development.

This is the closest established source for [HmacDrbg.v](../../../proofs/HmacDrbg.v), R-15-241d and R-05-077a. The local post-draw ordering and reseed-freshness statements are not distributional security; this upstream supplies a route toward such a statement. The concrete security theorem's supported calls, reseeding model, entropy assumptions and idealized HMAC must be matched, especially lifecycle-triggered reseeds and interval bounds. It does not prove the physical conditioner or independent noise sources of R-15-241b/R-15-241c/R-15-241e.

**Terms:** the `hmacdrbg`/`hmacfcf` test-suite portions use the VST BSD-2-Clause instrument above; FCF and other submodules retain their own terms. The same VST/CompCert compatibility and axiom barriers apply. No FCF dependency closure is conveyed or represented as license-cleared here.

### SSProve game-based reductions

**Established foundational framework with concrete native examples.** Philipp G. Haselwarter, Exequiel Rivas, Antoine Van Muylder, Théo Winterhalter, Carmine Abate, Nikolaj Sidorenco, Cătălin Hrițcu, Kenji Maillard and Bas Spitters, *SSProve: A Foundational Framework for Modular Cryptographic Proofs in Coq*, TOPLAS 2023; CSF 2021 conference version. [Publication](https://doi.org/10.1145/3594735). Read commit `c6d7d4bc3a0a671c92899aa49dfcfb065d1bdbbd`.

[`theories/Crypt/examples/PRFPRG.v`](https://github.com/SSProve/ssprove/blob/c6d7d4bc3a0a671c92899aa49dfcfb065d1bdbbd/theories/Crypt/examples/PRFPRG.v) contains `hyb_security_based_on_prf` and `security_based_on_prf`; sibling examples include `PRFMAC.v`, `KEMDEM.v` and `PKE/ElGamal.v`. These are reusable reduction patterns for R-05-059/R-05-077a and the still-open probabilistic half of M3.4, not proofs of the frozen suite merely because their games are similar.

**Terms and compatibility:** [`LICENSE`](https://github.com/SSProve/ssprove/blob/c6d7d4bc3a0a671c92899aa49dfcfb065d1bdbbd/LICENSE) is MIT, copyright 2021 SSProve. [`rocq-ssprove.opam`](https://github.com/SSProve/ssprove/blob/c6d7d4bc3a0a671c92899aa49dfcfb065d1bdbbd/rocq-ssprove.opam) requires core/stdlib at least 9.0 and below 9.2. [`theories/Crypt/Axioms.v`](https://github.com/SSProve/ssprove/blob/c6d7d4bc3a0a671c92899aa49dfcfb065d1bdbbd/theories/Crypt/Axioms.v) and the README disclose extensionality, proof irrelevance and choice-related dependencies. License compatibility does not remove either barrier; no package installed.

### CoqCryptoLine arithmetic verification

**Peer-reviewed checker proof; selective source, not an admitted optimization route.** Ming-Hsien Tsai, Yu-Fu Fu, Jiaxiang Liu, Xiaomu Shi, Bow-Yaw Wang and Bo-Yin Yang, *CoqCryptoLine: A Verified Model Checker with Certified Results* and *Certified Verification for Algebraic Abstraction*, CAV 2023. [Author-hosted publication list and papers](https://homepage.iis.sinica.edu.tw/~bywang/publication.html). [`src/Verify.v`](https://github.com/fmlab-iis/coq-cryptoline/blob/master/src/Verify.v) contains `verify_ssa_sound`, `verify_dsl_sound`, `rngred_spec_sound` and `algred_spec_sound`.

The [upstream README](https://github.com/fmlab-iis/coq-cryptoline) specifies Coq at least 8.13 and below 8.16 plus MathComp and certificate-checking dependencies. This is useful for validating the NTT arithmetic ideas in M3.4b and distinguishing untrusted solver output from checked certificates. The NTT verification work by Vincent Hwang and coauthors, [TCHES 2022](https://doi.org/10.46586/tches.v2022.i4.718-750), verifies concrete Kyber/Saber/NTRU arithmetic, not a full ML-KEM security reduction.

**Terms:** no grant is established by the root README, source header or attempted root `LICENSE` read. This is an unresolved license review, not a conclusion from GitHub's badge. **Disposition:** source only. A new assembly-equivalence-checker route would also conflict with R-05-064/R-05-068; this inventory does not reopen it.

## Other proof assistants and implementation evidence

### HACL* primitive specifications and refinements

**Established deployed reference, in F*/Low*.** Marina Polubelova, Karthikeyan Bhargavan, Jonathan Protzenko, Benjamin Beurdouche, Aymeric Fromherz, Natalia Kulatova and Santiago Zanella-Béguelin, *HACLxN: Verified Generic SIMD Crypto*, CCS 2020. [Paper](https://project-everest.github.io/assets/haclxn.pdf). This is the upstream's preferred citation for the current implementation lineage, rather than treating the rewritten library as identical to its CCS 2017 version.

At the already-pinned `504c2987`, [`specs/Spec.SHA3.fst`](https://github.com/hacl-star/hacl-star/blob/504c2987/specs/Spec.SHA3.fst) supplies a concrete SHA-3 specification. The [project README](https://github.com/hacl-star/hacl-star) identifies memory safety, functional correctness and secret independence proofs for SHA-2/SHA-3, HMAC/HKDF, AES-GCM and classical curves. These give independent specification/refinement comparisons for M3.4a/c/d and local Keccak/AES/SHA files.

**Terms:** [`LICENSE`](https://github.com/hacl-star/hacl-star/blob/504c2987/LICENSE) is Apache-2.0; generated C additionally has an MIT option according to upstream. Preserve each primitive's authorship metadata on any acquisition. **Disposition:** the existing pin remains an oracle/reference. F*/Z3 assumptions, representation conversion, the compiler boundary and the bespoke target still need bridges; secret independence here does not prove R-05-062 directly. Copying a C artifact would not import its proof into Rocq.

### EverCrypt and Vale AES-GCM

**Established assembly/refinement source; target mismatch.** Jonathan Protzenko, Bryan Parno, Aymeric Fromherz, Chris Hawblitzel, Marina Polubelova and the coauthors named in [*EverCrypt: A Fast, Verified, Cross-Platform Cryptographic Provider*](https://project-everest.github.io/assets/evercrypt.pdf), IEEE S&P 2020. Vale's assembly proofs and HACL* are combined behind the same specifications in the HACL* tree; the [manual](https://hacl-star.github.io/) identifies the AES-GCM API and verification architecture.

This is a strong comparison for [AesGcm.v](../../../proofs/AesGcm.v), R-10-024 and M3.4d: AES/GHASH and mode composition are relevant, but the x86 AES-NI/PCLMUL implementation is not the project's RVV/CHERI binary or masked datapath. Dynamic provider selection also does not match the composition-fixed suite. The [integration manual](https://hacl-star.github.io/Obtaining.html) identifies unverified native `UInt128` implementations in some generated-C configurations, with a verified alternative; that choice must be visible in any acquisition record.

**Terms:** same HACL* Apache-2.0 instrument at `504c2987`; per-file notices and dependency terms remain applicable. **Disposition:** proof architecture and oracle, not a drop-in and not a claimed AES-GCM reduction theorem.

### Formosa SHA-3 and sponge security

**Established published proof, with a current-tree caveat.** José Bacelar Almeida, Cécile Baritel-Ruet, Manuel Barbosa, Gilles Barthe, François Dupressoir, Benjamin Grégoire, Vincent Laporte, Tiago Oliveira, Alley Stoughton and Pierre-Yves Strub, *Machine-Checked Proofs for Cryptographic Standards: Indifferentiability of Sponge and Secure High-Assurance Implementations of SHA-3*, CCS 2019. [Publication](https://doi.org/10.1145/3319535.3363211). This combines an EasyCrypt sponge-security argument with implementation work; indifferentiability still assumes an idealized underlying permutation and is not a proof that Keccak is ideal.

The present [`formosa-keccak`](https://github.com/formosa-crypto/formosa-keccak/tree/fe5d22fa85672ffbe5cfb4845037b50cf2eaa1f7) at `fe5d22fa85672ffbe5cfb4845037b50cf2eaa1f7` has `proof/amd64/` and explicitly calls itself work in progress. The consuming ML-KEM README says SHA-3 correctness is currently assumed during refactoring. Therefore the paper's assurance cannot be attached wholesale to this current tree.

**Terms:** [`LICENSE`](https://github.com/formosa-crypto/formosa-keccak/blob/fe5d22fa85672ffbe5cfb4845037b50cf2eaa1f7/LICENSE) explicitly offers `CC0-1.0 OR Apache-2.0`. **Disposition:** useful security/specification source for R-15-058, R-05-059 and M3.4a; recover and replay the publication's exact proof edition before using it as evidence. No Coq-native Keccak proof is established by this search.

### Formosa ML-KEM correctness and IND-CCA

**Established scheme-level reference in EasyCrypt/Jasmin.** José Bacelar Almeida and the coauthors listed in [*Formally Verifying Kyber, Episode V: Machine-Checked IND-CCA Security and Correctness of ML-KEM in EasyCrypt*](https://doi.org/10.1007/978-3-031-68379-4_12), CRYPTO 2024, with Episode IV implementation correctness at TCHES 2023. Read `475b87434506280fdfa1a1ba5da0af3787e00579` of [`formosa-mlkem`](https://github.com/formosa-crypto/formosa-mlkem/tree/475b87434506280fdfa1a1ba5da0af3787e00579).

`proof/security/` holds the abstract reduction; `proof/spec/` connects the FIPS 203 transcription; [`proof/correctness/1024/ref/MLKEM_KEM.ec`](https://github.com/formosa-crypto/formosa-mlkem/blob/475b87434506280fdfa1a1ba5da0af3787e00579/proof/correctness/1024/ref/MLKEM_KEM.ec) includes `mlkem_kem_correct_kg`. This is directly relevant to open M3.4b, R-05-061/R-05-067 and R-05-059's reduction layer. The current README retains an underlying SHA-3 correctness assumption, disjoint memory premises and compiler/type-system CT claims. Those do not close the CHERI binary judgment or physical leakage model.

**Terms and version:** no whole-tree grant is established from its root files, `shell.nix` or the inspected proof header. This does not inherit libjade's grant. `shell.nix` pins Jasmin 2026.03.1 and EasyCrypt `0b07a19be15a23cb1c679e70f60d5b6e280caf7a`; dependencies have separate editions and terms. **Disposition:** high-priority specification/proof source; no unlicensed code incorporation and no claim that a license cannot be found elsewhere.

### SPHINCS+ tight security proof

**Established scheme-security reference, not an executable SLH-DSA verifier.** Manuel Barbosa, François Dupressoir, Andreas Hülsing, Matthias Meijers and Pierre-Yves Strub, *A Tight Security Proof for SPHINCS+, Formally Verified*, ASIACRYPT 2024, proceedings 2025. [Paper](https://eprint.iacr.org/2024/910), [artifact](https://github.com/MM45/FV-SPHINCSPLUS-EC/tree/a28e4c53897a4bb57b575a177225862d48f824b7). At `a28e4c53897a4bb57b575a177225862d48f824b7`, [`proofs/SPHINCS_PLUS.ec`](https://github.com/MM45/FV-SPHINCSPLUS-EC/blob/a28e4c53897a4bb57b575a177225862d48f824b7/proofs/SPHINCS_PLUS.ec) states `EUFCMA_SPHINCS_PLUS`, with modular FORS/Merkle/XMSS components.

This is the strongest inspected security-proof source for [RomVerifier.v](../../../proofs/RomVerifier.v), R-05-058a's SLH-DSA-SHAKE-256s choice, R-05-059 and R-09-005. An explicit relation from the actual FIPS 205 encoding/parameters and executable verifier to this abstract scheme remains necessary; hash-family assumptions remain hypotheses. No WOTS/FORS/tree verification routine is obtained by importing the theorem alone.

**Terms:** [`LICENSE`](https://github.com/MM45/FV-SPHINCSPLUS-EC/blob/a28e4c53897a4bb57b575a177225862d48f824b7/LICENSE) is MIT, copyright 2024 MM45. Upstream reports replay with EasyCrypt r2026.02, Z3 4.13.4 and Alt-Ergo 2.6.0. **Disposition:** compatible proof source for a Rocq port; not locally replayed and not silently promoted to the frozen verifier's theorem.

### libcrux ML-KEM and ML-DSA

**Actively maintained implementation proof source; per-module assurance required.** The libcrux and hax teams, [upstream library](https://github.com/cryspen/libcrux), now redirected to `celabshq/libcrux`. The read `main` [`Readme.md`](https://github.com/cryspen/libcrux/blob/main/Readme.md) describes Rust extracted through hax into F* for runtime safety and functional correctness, with separate `libcrux-ml-kem` and `libcrux-ml-dsa` crates and HACL*-derived components.

This corresponds to R-05-061's explicit interim route and M3.4b's independent oracle. Each selected module's proof status and call closure must be read before claiming full scheme correctness; the existence of an ML-DSA crate does not demonstrate a complete sign/verify security reduction. No precise whole-scheme theorem or compatible Rocq import is established in this reading, so this entry is an implementation candidate, not a new discharge.

**Terms:** the root [`LICENSE`](https://github.com/cryspen/libcrux/blob/main/LICENSE) is Apache-2.0. The crate notices, generated dependencies and hax/F* toolchain must accompany a concrete acquisition. **Disposition:** retain the expressly interim boundary; reference/oracle only here. This source is more relevant than treating every Jasmin ML-DSA implementation as already verified.

### s2n-bignum machine-code arithmetic

**Established machine-code correctness source in HOL Light.** John Harrison and the AWS/s2n-bignum contributors, [`s2n-bignum`](https://github.com/awslabs/s2n-bignum). A precise example on the read `main` is [`arm/proofs/bignum_montmul_p256.ml`](https://github.com/awslabs/s2n-bignum/blob/main/arm/proofs/bignum_montmul_p256.ml), containing `BIGNUM_MONTMUL_P256_CORRECT` and `BIGNUM_MONTMUL_P256_SUBROUTINE_CORRECT` over the actual instruction model. This is stronger than a source-level arithmetic example and makes representation, bounds, memory and calling-convention premises visible.

Use it to review R-05-060 arithmetic and M3.4b's low-level NTT proof shape. The project also contains SHA-3 and ML-KEM/ML-DSA assembly components, but its README warns that some general descriptions differ for those components. Its [soundness analysis](https://github.com/awslabs/s2n-bignum/blob/main/SOUNDNESS.md) is the acquisition boundary, not the phrase constant-time style. The AArch64/x86 model, HOL kernel and ordinary ABI do not match the admitted CHERI-RV64 route.

**Terms:** [`LICENSE`](https://github.com/awslabs/s2n-bignum/blob/main/LICENSE) offers Apache-2.0, ISC or MIT-0. **Disposition:** compatible mathematical/proof reference, not a foreign assembly leaf under R-05-068 and not a replacement for the mandated Fiat-Crypto path.

### AWS-LC SAW/Cryptol and Coq specification checks

**Maintained implementation-verification reference with unusually explicit limits.** AWS and Galois contributors, [`aws-lc-verification`](https://github.com/awslabs/aws-lc-verification), read `master`. `SAW/scripts/x86_64/docker_entrypoint_aes_gcm.sh` is a concrete AES-GCM replay entry point; `Coq/docker_entrypoint.sh` checks properties of Cryptol specifications. [`README.md`](https://github.com/awslabs/aws-lc-verification/blob/master/README.md) and [`SPEC.md`](https://github.com/awslabs/aws-lc-verification/blob/master/SPEC.md) identify the proved API operations and restrictions.

This directly informs review of R-10-024, M3.4d and [AesGcm.v](../../../proofs/AesGcm.v). The AES-GCM table explicitly records fixed IV/tag sizes, message-length restrictions, additional-data and specification gaps, assumed memory management and induction assumptions. The current SHA/HMAC table covers SHA-384/512 variants, so it is not evidence for local SHA-256 merely because the family name matches. SAW bitcode refinement is not a uniform theorem over all inputs/lengths when the entry says otherwise, nor a reduction proof.

**Terms:** root [`LICENSE`](https://github.com/awslabs/aws-lc-verification/blob/master/LICENSE) is Apache-2.0; the submodule closure is not cleared by that fact. **Disposition:** strong comparison for proof scope and API failure behavior, no imported artifact. The current project directs new assembly work to s2n-bignum and C safety work to CBMC in the native PQ repositories.

## Masking and numerical candidates with distinct limits

### Boolean masking, NI/SNI and maskVerif

**Established peer-reviewed technique and concrete checked gadgets; no Rocq composition import established.** Gilles Barthe, Sonia Belaïd, François Dupressoir, Pierre-Alain Fouque, Benjamin Grégoire and Pierre-Yves Strub, *Verified Proofs of Higher-Order Masking*, EUROCRYPT 2015; the CCS 2016 SNI work additionally includes Rébecca Zucchini. [Author's publications](https://fdupress.net/publications/). The [maskVerif project](https://cryptoexperts.com/maskverif/) documents t-probing/NI/SNI modes and concrete DOM AES and Keccak S-box examples, with hardware-glitch and software-transition variants; its ESORICS 2019 publication names Barthe, Belaïd, Gaëtan Cassiers, Fouque, Grégoire and François-Xavier Standaert.

These are direct proof sources for the open post-M10 Boolean masking item, R-05-004a and R-15-053a. A t-SNI/NI gadget result in its selected model is not the required arbitrary-order PINI composition theorem for a complete implementation under both glitches and transitions. Neither the physical model's truth nor R-17-058d's combined fault reduction follows from a successful gadget check.

**Terms:** a license-cleared source edition and a kernel-replayable proof artifact are not established in this reading. **Disposition:** authoritative algorithm/model reference and possible external checker evidence, not a directly imported theorem. Record exact models and orders when using its examples; do not turn the project's finite benchmark table into a universal statement.

### Prime-field masking in Lean 4

**Research candidate, not independently vetted gold-standard evidence.** Ray Iskander and Khaled Kirah's QANARY artifact line includes [prime-field composition](https://arxiv.org/abs/2604.25878) and [k-stage composition](https://arxiv.org/abs/2605.02856). The read [`qanary-k-stage-composition-arXiv-2605.02856`](https://github.com/rayiskander2406/qanary-k-stage-composition-arXiv-2605.02856) identifies `KStageComposition.lean` and `pfpini_pipeline_composition_k_stages`; its `lean-toolchain` pins Lean 4 `v4.30.0-rc1` and it depends on sibling artifacts and Mathlib.

It is relevant to the existing post-M10 arithmetic-composition source reading and R-15-053a. The statement bounds preimage cardinality for single-wire observations with fresh masks between stages. The paper expressly distinguishes the checked cardinality statement from the informal translation to a conditional-probability bound. This is not an arbitrary-order Boolean PINI proof, a combined glitch/transition theorem, a physical security measurement, or R-17-058d's effective/ineffective-fault reduction. No independent replication is established here.

**Terms:** [`LICENSE`](https://github.com/rayiskander2406/qanary-k-stage-composition-arXiv-2605.02856/blob/master/LICENSE) is MIT, copyright 2026 Ray Iskander and Khaled Kirah. **Disposition:** examine the formal statement as a research lead before porting; license compatibility and absence of `sorry` are not enough to confer the user's requested quality label.

### Flocq and Interval arithmetic

**Established native numerical foundations; reference dependencies rather than copied code.** Sylvie Boldo, Guillaume Melquiond and the Flocq contributors, [Flocq](https://flocq.gitlabpages.inria.fr/); Guillaume Melquiond and contributors, [Interval](https://coqinterval.gitlabpages.inria.fr/). Flocq's `Generic_fmt.round` and fixed/floating-point formats provide rounding semantics and error bounds; Interval's [`Interval.Interval.Float`](https://coqinterval.gitlabpages.inria.fr/interval/html/Interval.Interval.Float.html) provides verified interval arithmetic and tactics for enclosures involving elementary functions. The published Interval 4.11.4 compatibility line starts at Coq 8.13; it does not establish replay in this project's locked environment.

These are relevant to R-15-040c and R-15-083, the frozen nearest-even vector-FP behavior, and the compiler/RTL refinement work that must preserve it. They do not model the bespoke instruction encodings, zero-extension divergence, or physical FPU implementation. A real-number theorem's classical assumptions must be enumerated before entering R-05-163/R-05-164's gate; this is not an empty-context arithmetic drop-in by default.

**Terms:** the Flocq project states LGPL; Interval's source header explicitly states CeCILL-C and refers to its `COPYING` instrument. These are not cleared for vendoring under this repository's no-reciprocal-tracked-content policy. **Disposition:** established proof/model references, with exact release, complete instrument and dependency/axiom review owed before any linked proof build or extraction is proposed.

## Negative and bounded results

The inspected [`formosa-mldsa` README](https://github.com/formosa-crypto/formosa-mldsa) explicitly says its code has not been formally verified for memory safety, constant time, speculative constant time or functional correctness. It is excluded as a gold-standard proof example at this reading, regardless of the Jasmin name. Conversely, the [native ML-DSA releases](https://github.com/pq-code-package/mldsa-native/releases) describe CBMC memory/type-safety and undefined-behavior coverage; those are useful bounded safety results, not a claimed complete functional-correctness or EUF-CMA proof.

The search does not establish a reusable complete Rocq proof of ML-KEM, ML-DSA, SLH-DSA-SHAKE-256s verification, the full Keccak implementation, the arbitrary-order Boolean masking composition, or the project's combined fault/probing reduction. This is a result of the inspected sources and compatibility requirements, not a universal nonexistence theorem. No suitable existing proof found here replaces the entropy-source, conditioner or first-silicon characterization obligations. The compatible candidates above need explicit semantic bridges and replay before they can replace local proof obligations; no requirement is closed by this inventory.
