# Proof reuse: parsing, formats, media and WebAssembly

This inventory qualifies published proof developments against this project's actual obligations. Research and source inspection date: **2026-09-10**. A strong published example is not an already discharged VerifiedOS requirement. No external parser, interpreter or proof term is incorporated by this document, and no candidate below is rebuilt in the project's Rocq switch. Source inspection, upstream claims and local qualification are distinguished explicitly.

## Local consumers and the qualification boundary

[The register](../../requirements-register.md) requires Narcissus descriptors and copy-once parsing at R-05-042 through R-05-051, a separate admissible-byte injectivity theorem at R-05-051a through R-05-051c, and schema-derived UPER parsing at R-05-048, R-05-049 and R-18-029. R-05-044 excludes shipped F*/Z3-generated parsers; R-05-045 permits EverParse as an untrusted oracle. A permissive licence does not override either rule. Decoder correctness against a descriptor does not establish the descriptor's fidelity to a published standard, and `decode (encode value) = value` does not establish that two accepted encodings cannot denote the same value.

[HandlerGraph.v](../../../proofs/HandlerGraph.v) states the composition obligations over R-12-013a and R-12-024b through R-12-024f, including the admitted-format condition. It does not parse content or settle the open ambiguous-handler selection policy. [CopyRingService.v](../../../proofs/CopyRingService.v) proves abstract ring lifecycle invariants, including `publish_keeps_the_invariant`, `take_keeps_the_invariant` and `the_invariant_survives_every_interleaving`. Parser libraries do not replace those concurrency proofs or supply their missing byte-memory realization. The relevant plan consumers are [Q2b/Q2c, M6.3, M6.5 and M7.1](../../implementation/implementation-checklist.md); [the IDL profile](../../languages/idl-profile.md) supplies the wire mapping's local interface. `CJ-FORMAT` and `CJ-IDL` remain unauthored specifications where [the crown-jewel inventory](../crown-jewels.md) says so.

R-14-013a through R-14-013d require interpreter refinement and robust guest confinement over the same pinned subset, including numeric semantics; SIMD is admitted only as far as the tracked mechanization supports it. These are separate from Wasm type preservation, a Wasm binary parser, and the host-side CertiRocq oracle. The [TAL specification](../../languages/typed-assembly-language.md) remains the native admission boundary. A Wasm theorem does not prove CHERI-TAL soundness, host-function correctness, CHERI memory confinement, fixed capacity or WCET.

## Candidate records

### Narcissus: primary same-language starting point

**Authorship and vetting.** Benjamin Delaware, Sorawit Suriyakarn, Clément Pit-Claudel, Qianchuan Ye and Adam Chlipala, [*Narcissus: Correct-by-Construction Derivation of Decoders and Encoders from Binary Formats*, ICFP 2019](https://doi.org/10.1145/3341686). Its evaluated network-stack integration is stronger evidence than an unreviewed parser example.

**Artifact.** `mit-plv/fiat` revision `b7757d28f68c39c3c58192a27f217064b0b35e3b`. [Common/Specs.v](https://github.com/mit-plv/fiat/blob/b7757d28f68c39c3c58192a27f217064b0b35e3b/src/Narcissus/Common/Specs.v) defines `CorrectDecoder`, `CorrectEncoder`, `CorrectDecoder_id` and their relationships. `src/Narcissus/Examples/NetworkStack/` contains Ethernet, ARP, IPv4, UDP and TCP developments; `Examples/DNS/` and `Examples/ICMP_Packet.v` extend the exemplar set. The [README](https://github.com/mit-plv/fiat/blob/b7757d28f68c39c3c58192a27f217064b0b35e3b/README.md) says the library is mostly unmaintained and only the `fiat-core`, `parsers`, and `parsers-examples` targets are maintained for Coq CI. Those target names alone do not establish current Narcissus/Rocq 9.2 compatibility.

**Terms and disposition.** [LICENSE](https://github.com/mit-plv/fiat/blob/b7757d28f68c39c3c58192a27f217064b0b35e3b/LICENSE) is MIT, copyright MIT, naming Delaware, Pit-Claudel, Jason Gross and Chlipala. Retain that notice for copied source. Best candidate for R-05-042/R-05-043/CJ-FORMAT, but qualification still needs the selected descriptor, current compiler compatibility, closed assumptions and the copy-once bounded imperative refinement. No complete UPER front end or local canonical manifest proof is supplied by these network examples.

### VUPER: unusually close UPER research candidate

**Authorship and vetting.** Xiaotian Zhou, Kai Tu, Ali Ranjbar, Yilu Dong, Gang Tan and Syed Rafiul Hussain, [*VUPER: Verified ASN.1 UPER Parser*](https://arxiv.org/abs/2608.09094v1). The August 2026 record identifies an extended version of a paper accepted to ACM CCS 2026. Its age and acceptance should both be recorded; this is not a long-maintained production library.

**Artifact.** `SyNSec-den/VUPER` revision `1543c5ab2d19ae803c43436dc17bd82ba2e2e484`. [parser_artifact](https://github.com/SyNSec-den/VUPER/tree/1543c5ab2d19ae803c43436dc17bd82ba2e2e484/parser_artifact) supplies Coq 8.20/OCaml 4.14 setup, an ASN.1-to-Coq compiler, combinators and extraction. `asn1parser/src/Formats/Comb.v` defines `format_correct_surj`, `format_correct_inj_same`, `format_correct_inj_diff` and `format_correct`; `Array/ByteBufferProp.v` proves bit-buffer properties. The NR-RRC, LTE and ITS differential campaigns make it particularly relevant to R-05-048 through R-05-051 and R-18-029.

**Terms and disposition.** No root licence or licence under `parser_artifact` is found in the inspected tracked source listing. The paper's licence does not grant rights to that code; licences attached to vendored differential-test decoders do not cover VUPER. **Reference only, no incorporation.** `AbsArray.v` has module-interface axioms requiring a concrete implementation discharge; their presence is not itself an admission, and no `Print Assumptions` closure is established here. The compiler targets this library and OCaml extraction, so equivalence to the required Narcissus descriptors and bounded Clight path remains work. Version-aware compatibility and bit-slice injectivity need comparison with the project's whole-admissible-byte canonicity statement.

### Cheerios: small Coq serialization contracts

**Artifact and authorship.** The Verdi team's [Cheerios](https://github.com/uwplse/cheerios/tree/5c9318c269f9cae1c1c6583a44405969ac0be0dd), revision `5c9318c269f9cae1c1c6583a44405969ac0be0dd`, is a reusable verified serialization library. `theories/Core/Core.v` defines the `Serializer` class and `serialize_deserialize_id_spec`; `BasicSerializers.v` supplies proofs such as `bool_serialize_deserialize_id` and `positive_serialize_deserialize_id`. Its [package metadata](https://github.com/uwplse/cheerios/blob/5c9318c269f9cae1c1c6583a44405969ac0be0dd/coq-cheerios.opam) requests Coq >=8.14 and development `coq-struct-tact`, not a tested local Rocq 9.2 closure.

**Terms and fit.** [LICENSE](https://github.com/uwplse/cheerios/blob/5c9318c269f9cae1c1c6583a44405969ac0be0dd/LICENSE) is BSD-2-Clause, copyright 2014-2020 Verdi Team. Same-language exemplar for CJ-IDL, bounded value encodings and R-13-003 manifests. Its principal round-trip class does not require every accepted byte string to be the unique encoding, and its generic representations do not supply this project's descriptors, resource bounds or Clight lowering. **Adaptation candidate**, not a replacement for R-05-051a.

### Vermillion: total LL(1) parsing in Coq

**Authorship and vetting.** Sam Lasser, Chris Casinghino, Kathleen Fisher and Cody Roux, [*A Verified LL(1) Parser Generator*, ITP 2019](https://tyconmismatch.com/papers/itp2019_ll1.pdf). The proof covers table generation and parsing, including termination on invalid input.

**Artifact and terms.** `slasser/Vermillion` revision `0b60114b27f4f92272129f381ec01e593273e6f2`. [Proofs/EndToEnd.v](https://github.com/slasser/Vermillion/blob/0b60114b27f4f92272129f381ec01e593273e6f2/Proofs/EndToEnd.v) provides `parseTableOf_sound` and `parseTableOf_complete`; `Parser_sound.v`, `Parser_complete.v`, `Parser_safe.v` and `Determinism.v` supply the parser layer. README reports Coq 8.8.1. [LICENSE](https://github.com/slasser/Vermillion/blob/0b60114b27f4f92272129f381ec01e593273e6f2/LICENSE) is BSD-3-Clause, copyright 2017 `slasser`, including the non-endorsement condition.

**Disposition.** Strong same-language proof pattern for bounded textual descriptors or a descriptor compiler and for rejecting malformed content under R-12-024f. The lexer, chosen grammar, numeric conversions, bounded resource theorem and native lowering are separate. Grammar unambiguity does not imply canonical serialization: distinct textual spellings can still denote equal values. No direct integration.

### CoStar: broader grammars and explicit ambiguity

**Authorship and vetting.** Lasser, Casinghino, Fisher and Roux, [*CoStar: A Verified ALL(*) Parser*, PLDI 2021](https://doi.org/10.1145/3453483.3454053). Soundness/completeness and error-free termination apply to non-left-recursive grammars; empirical linear performance is not a general worst-case bound.

**Artifact and terms.** `slasser/CoStar` revision `a213d4d7ef738cc56e5e73e84ca465f0e80f4583`. [parser/Parser_complete.v](https://github.com/slasser/CoStar/blob/a213d4d7ef738cc56e5e73e84ca465f0e80f4583/parser/Parser_complete.v) supplies `parse_complete`; `Parser_sound.v` includes `multistep_sound_unambig` and `multistep_sound_ambig`. README tests Coq 8.11.2, CoLoR 1.7.0 and OCaml 4.11.1. [LICENSE](https://github.com/slasser/CoStar/blob/a213d4d7ef738cc56e5e73e84ca465f0e80f4583/LICENSE) is BSD-3-Clause, copyright 2019 Samuel Lasser.

**Disposition.** JSON/XML experiments and explicit ambiguity are useful references for CJ-FORMAT and input grammar review. They do not choose the ambiguous handler-routing policy that `HandlerGraph.v` deliberately leaves unsettled, nor prove fixed pool/WCET bounds. Port or oracle candidate only; no shipped parser-generator change is made.

### EverParse and LowParse: industrial proof architecture, oracle-only here

**Authorship and vetting.** Tahina Ramananandro, Antoine Delignat-Lavaud, Cédric Fournet, Nikhil Swamy, Tej Chajed, Nadim Kobeissi and Jonathan Protzenko, [*EverParse: Verified Secure Zero-Copy Parsers for Authenticated Message Formats*, USENIX Security 2019](https://www.usenix.org/conference/usenixsecurity19/presentation/delignat-lavaud). The [PLDI 2022 follow-on](https://fstar-lang.org/papers/EverParse3D.pdf), by Swamy, Ramananandro, Aseem Rastogi, Irina Spiridonova, Haobin Ni, Dmitry Malloy, Juan Vazquez, Michael Tang, Omar Cardona and Arti Gupta, describes deployed binary-parser hardening.

**Artifact and terms.** `project-everest/everparse` revision `e1bfead60deba35db696059c78e77aa406135cdc`; [src/lowparse](https://github.com/project-everest/everparse/tree/e1bfead60deba35db696059c78e77aa406135cdc/src/lowparse) contains `LowParse.Spec.Base.fst`, `LowParse.Low.Base.Spec.fst` and verified combinators. F*/Low*, Z3 and KaRaMeL are the proof and extraction stack; this survey does not qualify a reproducible dependency closure. The actual [LICENSE](https://github.com/project-everest/everparse/blob/e1bfead60deba35db696059c78e77aa406135cdc/LICENSE) is Apache-2.0. Preserve applicable source copyright, licence and change notices if any derivative is later made.

**Disposition.** Directly useful independent test oracle under R-05-045/R-05-051, including NAS or other format descriptors one implements separately. R-05-044 prevents importing its generated parser as the shipping proof path. Zero-copy over a stable buffer is not this project's copy-once protocol against a concurrently mutable delegated buffer.

### ASN1*: actual DER non-malleability

**Authorship and vetting.** Haobin Ni, Delignat-Lavaud, Fournet, Ramananandro and Swamy, [*ASN1*: Provably Correct, Non-Malleable Parsing for ASN.1 DER*, CPP 2023](https://www.normalesup.org/~ramanana/research/everparse/cpp2023/).

**Artifact.** The inspected EverParse revision above contains [src/ASN1](https://github.com/project-everest/everparse/tree/e1bfead60deba35db696059c78e77aa406135cdc/src/ASN1). `ASN1.Spec.Set.fst` includes `tot_parse_byte_sorted_list_correct`, `parse_asn1_set_of` and explicit injective parser kinds; `ASN1.X509.fst` supplies `parse_cert`. Its README specifies verification and OCaml extraction through the EverParse environment. The root Apache-2.0 instrument applies to this source; no different local licence is found.

**Disposition.** A strong exemplar for R-05-051a/b and certificate-related DER parsing, particularly the uniqueness and ordering obligations absent from ordinary round-trip libraries. It covers DER, not UPER or aligned PER. Its F* proof does not pass through the Rocq kernel and R-05-044 still controls shipping. Use the proof structure and an independent oracle; a local Narcissus correspondence and all descriptor-specific cases remain required.

### EverCBOR, PulseParse and EverCDDL: deterministic CBOR

**Authorship and vetting.** Ramananandro, Gabriel Ebner, Guido Martínez and Swamy, [*Secure Parsing and Serializing with Separation Logic Applied to CBOR, CDDL, and COSE*](https://arxiv.org/abs/2505.17335). The paper explicitly distinguishes deterministic CBOR non-malleability and well-formed CDDL from unrestricted formats.

**Artifact.** At the same Apache-2.0 EverParse revision, [src/cbor/spec](https://github.com/project-everest/everparse/tree/e1bfead60deba35db696059c78e77aa406135cdc/src/cbor/spec) contains raw-format, ordering and API contracts. `raw/everparse/CBOR.Spec.Raw.Format.fst` proves `parse_cbor_map_equiv` and ordering properties; `src/lowparse/pulse` holds PulseParse and `src/cddl` the schema tool. F*/Pulse proofs underlie emitted C and Rust. The repository provides separate build commands that consume already emitted source; running those commands alone would not recheck the proof.

**Disposition.** Particularly useful R-05-051a/b exemplar for signed manifests, pack metadata and cache keys **if CBOR is selected**. Deterministic subset choice, duplicate keys, map ordering, numeric representations and exact consumed input must become explicit in the local descriptor. Apache licensing is compatible in form, but F*/Z3 transport is outside the current shipping route. No CBOR format is selected by this inventory.

### RecordFlux: SPARK message and state-machine examples

**Authorship and vetting.** Tobias Reiher, Alexander Senier, Jerónimo Castrillón and Thorsten Strufe, [*RecordFlux: Formal Message Specification and Generation of Verifiable Binary Parsers*](https://arxiv.org/abs/1910.02146), with the maintained [AdaCore artifact](https://github.com/AdaCore/RecordFlux/tree/d13da982a2277eda4850fe7875e2a6d723d8bd0f).

**Artifact and terms.** Revision `d13da982a2277eda4850fe7875e2a6d723d8bd0f`. `rflx/templates/rflx_template-rflx_arithmetic.ads` carries SPARK postconditions and `Always_Terminates`; grammar examples and generated-message tests exercise the schema-to-code approach. `doc/user_guide/10-introduction.rst` names SPARK Pro 24.2 or 25.0 for generated-code verification. The actual root [LICENSE](https://github.com/AdaCore/RecordFlux/blob/d13da982a2277eda4850fe7875e2a6d723d8bd0f/LICENSE) is **Apache-2.0**; older accounts calling RecordFlux AGPL do not describe this inspected edition. The VS Code extension has its own licence and is outside the candidate proof surface.

**Disposition.** Useful bounded bitfield/TLV and protocol-state-machine exemplar for R-05-050, CJ-IDL and R-12-024f. A SPARK contract is not a Rocq proof, and a generator that emits verifiable code is not automatically a proved semantics-preserving compiler. Oracle/research reference, with no change to the Narcissus/Lustre routes.

### Verified QOI: an actual image codec correctness example

**Authorship and vetting.** Mario Bucev and Viktor Kunčak, [*Formally Verified Quite OK Image Format*, FMCAD 2022](https://repositum.tuwien.at/bitstream/20.500.12708/81370/1/Bucev-2022-Formally%20Verified%20Quite%20OK%20Image%20Format-vor.pdf).

**Artifact and terms.** `epfl-lara/bolts` revision `a02ca7fdb7c6aa554629007a11f0ddcf4e9f51ee`, [qoi/verified/encoder.scala](https://github.com/epfl-lara/bolts/blob/a02ca7fdb7c6aa554629007a11f0ddcf4e9f51ee/qoi/verified/encoder.scala), `decoder.scala` and `common.scala`. `decodeEncodeIsIdentityThm` states recovery of dimensions, channels and original pixels. Stainless proves Scala contracts, termination and absence of ordinary runtime errors; the README excludes out-of-memory. Current README expects a recent Stainless development edition rather than a pinned prover release. Root [LICENSE](https://github.com/epfl-lara/bolts/blob/a02ca7fdb7c6aa554629007a11f0ddcf4e9f51ee/LICENSE) is Apache-2.0. Benchmark C headers and sample images have distinct provenance and are not included in this source qualification.

**Disposition.** Valuable R-12-024f image-pipeline proof exemplar, especially encoder/decoder loop relations. Neither QOI selection, bounded-memory admission, native code refinement nor canonicity follows. QOI is not a JPEG/PNG/AV1 proof, and Stainless proof obligations are not importable Rocq terms. No direct integration.

### WasmCert-Coq: type safety and interpreter refinement with concrete boundaries

**Authorship and vetting.** Conrad Watt, Xiaojia Rao, Jean Pichon-Pharabod, Martin Bodin and Philippa Gardner, [*Two Mechanisations of WebAssembly 1.0*, FM 2021](https://conrad-watt.github.io/papers/watt2021.pdf), and the subsequent maintained development.

**Artifact.** `WasmCert/WasmCert-Coq` revision `5e6df8d60c94aa5dbeff633f5eb48caa6c64c225`. [theories/type_preservation.v](https://github.com/WasmCert/WasmCert-Coq/blob/5e6df8d60c94aa5dbeff633f5eb48caa6c64c225/theories/type_preservation.v) proves `t_preservation`; `type_progress.v` defines and proves `t_progress_interp_ctx` using `interpreter_ctx.v`'s proof-carrying `run_one_step_ctx`. The progress theorem assumes the provided host-function implementation satisfies its relational host semantics. Package metadata says version 2.2.1, Coq/Rocq >=9.0 and <9.2, Flocq 4.x, MathComp and Parseque dependencies.

**Terms.** [LICENSE.txt](https://github.com/WasmCert/WasmCert-Coq/blob/5e6df8d60c94aa5dbeff633f5eb48caa6c64c225/LICENSE.txt) is MIT for the main development, naming Bodin, Gardner, Pichon, Rao and Watt, with **LGPL-2.1-or-later exceptions** for `compcert/` numerics and `src/Parray/`. The package's single MIT metadata field is not the full source licence decomposition.

**Disposition.** Principal same-language curation candidate for CJ-WASM/CJ-WASM-SOUND. Its README calls the binary parser unverified. `theories/simd_execute.v` uses `Parameter app_vunop_str` and related external operations; `wasm_parray.v` declares array interface properties. These need a target-specific assumption audit and concrete realizations. The development's Wasm 2.0 plus selected extensions and opaque SIMD execution do not by themselves close R-14-013d's complete semantic/refinement obligation. No library pin alone retires robust host confinement, fixed memory planning or local interpreter lowering.

### Iris-Wasm: the robust-confinement theorem family

**Authorship and vetting.** Xiaojia Rao, Aïna Linn Georges, Maxime Legoupil, Conrad Watt, Jean Pichon-Pharabod, Philippa Gardner and Lars Birkedal, [*Iris-Wasm: Robust and Modular Verification of WebAssembly Programs*, PLDI 2023](https://doi.org/10.1145/3591265).

**Artifact.** `logsem/iriswasm` revision `e37f8387a1171d104d78a2f77f9e637e090cf3d4`. [theories/iris](https://github.com/logsem/iriswasm/tree/e37f8387a1171d104d78a2f77f9e637e090cf3d4/theories/iris) contains `logrel/iris_interp_instance_alloc.v` (`interp_instance_alloc`), `examples/stack/stack_robust.v` (`instantiate_client`), and the verified `valid_push`, `valid_pop`, `valid_new_stack` clients. The README maps paper theorems to these symbols. Its current opam metadata requests Coq >=8.20.1, Iris >=4.3.0 and CompCert >=3.15 among its dependencies; that is not local compatibility evidence.

**Terms and disposition.** [LICENSE](https://github.com/logsem/iriswasm/blob/e37f8387a1171d104d78a2f77f9e637e090cf3d4/LICENSE) is MIT, copyright 2024 Logic and Semantics at Aarhus University. Dependency and inherited-file notices still need decomposition before importing a closure. This is a closer R-14-013a robust guest-confinement exemplar than type safety alone: adversarial modules are constrained by explicit interfaces in its Wasm 1.0 host model. Adapting the logical relation to the pinned subset, manifest host calls and actual CHERI-bounded interpreter is substantial work. It supplies no proof about `HandlerGraph.v`'s native nodes merely because both systems have modules.

### WasmCert-Isabelle: independently mechanized comparison

Conrad Watt's reviewed [AFP WebAssembly entry](https://isa-afp.org/entries/WebAssembly.html) accompanies the CPP 2018 lineage. Its session includes `Wasm_Soundness`, `Wasm_Checker_Properties`, `Wasm_Interpreter_Properties` and the explicit `Wasm_Axioms` interface. AFP describes a verified type checker and interpreter, with only partial extraction support in this entry. It is an Isabelle/HOL development, not a Rocq library; an exact compatible Isabelle release is not established in this survey.

The entry's actual [AFP licence instrument](https://isa-afp.org/LICENSE) is BSD-3-Clause for BSD-marked files, with contributing-author notices and non-endorsement. **Independent theorem/specification comparison** for R-14-013b and numeric/host assumption review, not a source import. The 2018 entry is not evidence of full current Wasm 3.0, SIMD or the platform's host-confinement theorem. Same-language WasmCert-Coq is the nearer curation route; independent formalization is valuable evidence for checking the agreement gap.

## Sources that inform the search but are not qualified imports

**SpecTec and the official specification.** [The official adoption announcement](https://webassembly.org/news/2025-03-27-spectec/) describes generation of Rocq definitions and then-current Wasm 1.0 soundness work. The inspected `WebAssembly/spec` revision `95dffb694caa11c3663203f2756dda9bf24c2021` contains `specification/wasm-3.0` and `wasm-latest`, but no tracked `.v` proof files. Its root [LICENSE](https://github.com/WebAssembly/spec/blob/95dffb694caa11c3663203f2756dda9bf24c2021/LICENSE) delegates by directory, including Apache-2.0 for SpecTec and W3C terms for document material; the inspected tree has no `spectec/LICENSE` to complete that named pointer. No blanket licence conclusion or full soundness-import claim is drawn from it. It is the required tracked **semantic upstream** for R-14-013b/d; locating and checking the exact generated proof artifact and admitted-version frontier remains necessary. A soundness statement printed in the specification is not the complete Rocq proof.

**Verified Protocol Buffers.** Qianchuan Ye and Benjamin Delaware's [CPP 2019 paper](https://doi.org/10.1145/3293880.3294105) verifies a realistic Protocol Buffers subset in Coq and validates against official conformance tests. Its deliberately many-to-one accepted encodings make it a useful counterexample to equating codec correctness with R-05-051a. A source revision and applicable source licence are not established here, so this is a published proof reference only, not an import candidate.

**DEFLATE.** Christoph-Simon Senjak and Martin Hofmann's [*An Implementation of Deflate in Coq*, FM 2016](https://arxiv.org/abs/1609.01220) proves canonical prefix-code machinery and encoder/decoder inversion. It is relevant inside some archive/image/document families, but the word *canonical* in a Huffman code construction does not assert a unique compressed representation of each decompressed value. A redistributable source revision, licence and current Coq build are not qualified here. No claim of a whole ZIP, PNG or document parser follows.

**ASN1SCC and Stainless.** Mario Bucev, Samuel Chassot, Simon Felix, Filip Schramka and Viktor Kunčak's [ASN.1/ACN case study](https://arxiv.org/abs/2412.07235) links the generator to `maxime-esa/asn1scc` and generated proofs to `epfl-lara/fovcom`. It proves runtime safety and inversion for the base library and records, with sums/arrays described as further steps. This is valuable R-05-048/R-18-029 reference and oracle work; no blanket compiler correctness, whole-ASN.1 inversion or source-licence qualification is claimed. It uses Stainless/Scala, not the required Coq-to-Narcissus path.

## Format coverage and remaining gaps

These are search dispositions, not new format selections or a substitute for CJ-FORMAT's missing enumeration.

| Required family or consumer | Closest qualified evidence | What is still owed here |
| --- | --- | --- |
| Cellular RRC UPER/aligned PER | VUPER; ASN1SCC case study | Licensed source for VUPER, complete selected ASN.1 semantics, aligned-PER coverage, verified Narcissus front end and bounded copy-once lowering |
| 5G NAS IEI/TLV | Narcissus combinators; RecordFlux/EverParse as independent exemplars | Hand-transcribed TS 24.501 descriptor and the specifically required differential-oracle coverage |
| 802.11 MLME and USB; APDU/TPDU | Narcissus binary combinators | Each actual grammar, legal source material, bounded tables and full descriptor fidelity review; Ethernet is not MLME and DER is not APDU |
| IDL, pack and manifest; content addresses and cache keys | Narcissus; Cheerios; ASN1*/EverCBOR non-malleability | Exact local descriptor, rejection of all alternate encodings, full-input consumption, copy-once memory proof and R-05-051a theorem |
| Image and archive formats | QOI functional proof; DEFLATE published proof | Actual selected format inventory and complete bounded parsers; codec-subalgorithm proofs do not establish container validity |
| Media/audio/video | General binary combinators | No qualified complete Coq codec proof identified for a selected format; codec choice, format grammar, numeric kernels and WCET remain separate |
| Fonts | General binary combinators | No qualified complete font parser/rasterizer proof identified; grammar and rendering safety remain separate |
| Documents and textual schemas | Vermillion and CoStar JSON/XML examples | Selected document formats, lexers, depth/size limits, canonical identity encodings and semantic processing |
| Model-shape descriptors and media graph bindings | Narcissus and canonical-format exemplars | Exact nonrecursive model schema and canonicity; no weight correctness claim, no handler-selection policy chosen |
| Wasm guest content | WasmCert-Coq, Iris-Wasm, independent Isabelle proofs | Pinned subset, verified binary parser, concrete numerics/SIMD and array models, host-manifest relation, bounded native interpreter refinement and robust confinement |

The immediate integration decision is therefore **inventory and cited proof interfaces only**. Importing a new development without a matching consumer theorem would add licensing and dependency burden while leaving the actual obligation unchanged. The first practical adaptation targets are Narcissus descriptor qualification, a licensed UPER correspondence study, and a WasmCert/Iris-Wasm assumption and version audit. Existing local proofs remain intact; none is relabelled complete because an external theorem has a similar name.
