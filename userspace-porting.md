# Userspace Porting Targets (non-normative)

> Externalized companion to [verification-maximal-os.md](verification-maximal-os.md).
> This is a **non-normative roadmap**, not part of the specification: a curated list of the first userspace applications slated for porting, each mapped to the normative mechanism (§N of that document) it must be re-targeted onto.
> It is the userland analogue of [Evaluated Architectural Alternatives](architectural-alternatives.md), and, like it, carries no normative weight — every target still enters through the Tier-2/Tier-1 admission discipline of §13, and a name on this list is a *statement of intent*, not a grant of exception.

"Porting" here is a term of art.
There is **no Linux-personality shim and no legacy VM** (§2, §14): a foreign binary does not run, ever.
Every entry below is therefore a **source-level re-target** — recompiled against the WASI-shaped capability libc (§14) straight to native RV64+CHERI, its ambient-authority assumptions stripped and re-expressed as explicit capabilities (§8), admitted only once it carries the proof its tier demands (§13).
The selection is **uniformly Rust** by design: safe Rust is memory-safe by construction (§5, §14), so a `#![forbid(unsafe_code)]` port is the cheapest path to the mandatory Tier-2 memory-safety certificate (§13) — the certifying Rust→RV64+CHERI toolchain (§18) discharges it automatically, and rustc/LLVM never enter the trust base.

## Roster

- **COSMIC Desktop** — the shell, with its `cosmic-comp` compositor promoted to the reference §12 display server (compositor: Tier-1; shell applets: Tier-2).
- **Zed** — the reference editor/IDE; a software-rendered Tier-2 app.
- **coreutils / findutils / diffutils** from uutils — the seed corpus for §14's capability-native core utilities (Tier-2).
- **gitoxide** — the pure-Rust Git, re-targeted as the capability-native version-control engine; its object store re-homes onto §10's verified CoW B-tree (native dedup, reflinks, snapshots — Git's packfiles and `gc` shed) and its pack/wire decoders are a §5 Narcissus obligation (Tier-2).
- **Servo** — the contained, per-origin browser engine of §14 (Tier-2 origin compartments).
- **GGUF inference runtime** — the §12 optional inference server on the M-class cores: the `burn` deep-learning framework re-targeted onto a net-new M-class GEMM backend (`burn`'s pluggable backend trait is the clean seam), not a from-scratch build (Tier-1).

---

## The porting discipline — four obstacles every target meets

Independent of the application, the same four substrate mismatches are re-targeted the same way, so they are stated once here and referenced per target below:

1. **`unsafe` must go.**
   FFI shims, GPU bindings, and hand-rolled synchronization are inadmissible in app logic (§5): each `unsafe` site is either deleted with the POSIX/GPU assumption that motivated it or routed through the formally verified HAL (§5).
   A dependency that cannot shed its `unsafe` — a C library behind a `-sys` crate — is itself a sub-port.
2. **GPU dependence becomes software compute.**
   There is no fixed-function GPU, no Vulkan/Metal/wgpu path, no CUDA (§15).
   Rendering, compositing, and codecs move to software on the V-class cores; matrix/AI work moves to the M-class GEMM units (§15) — both under the §12 display/inference model, never a driver.
3. **Ambient POSIX authority becomes explicit capabilities.**
   No `fork`/`exec`, no uid/gid, no `/proc`, no CWD-relative path resolution (§2, §8).
   Process trees become the service manager's static supervision tree (§12); path-based file access becomes a manifest-backed private namespace (§14); "spawn a helper" becomes a capability-delegated compartment reached over a ring (§12).
4. **No runtime code generation, anywhere.**
   Compilation is an off-device build step (the certifying toolchain, §5/§18), never an on-device service; nothing on the device JITs (§14), so any embedded script/Wasm engine runs **pure-interpreter**.

---

## Targets

### COSMIC Desktop — the shell, and the reference compositor

System76's Rust desktop — the `libcosmic`/`iced` toolkit, the `cosmic-comp` compositor on smithay, cosmic-text — assumes Wayland-over-Linux: DRM/KMS scanout, a GPU through wgpu/OpenGL, evdev/libinput.
Re-targeted, **`cosmic-comp` becomes the reference §12 display server**: it already embodies the "surfaces are plain memory, input and output are mediated" model that §12 mandates, so Wayland's global-registry ambient objects are replaced by **per-surface and per-input capabilities** (keylogging and screen-scraping become unexpressible, §12), DRM/KMS is replaced by the firmware-free scanout controller behind a static IOMMU window (§12, §15), and the wgpu/OpenGL renderer falls back to **software compositing on V-class cores** (§12, obstacle 2).
Because the compositor mediates between mutually distrusting clients — many origins' and apps' surfaces and input events — it is a cross-domain **Tier-1** server carrying the §13 information-flow theorems that decide which surface may observe which input; the panel, launcher, settings, and applets are ordinary **Tier-2** apps built on `libcosmic`. libinput/evdev collapse to register-slave scan drivers (§12), and `fork`-spawned session helpers become supervision-tree compartments (obstacle 3).

**Disposition:** adopt `cosmic-comp` as the reference display-server seed and `libcosmic`/`iced` as the app toolkit; the GPU renderer is the single largest rewrite (software rasterization on V-class cores), and the Wayland surface model is kept as *vocabulary* while its enforcement moves to capabilities.

### Zed — the reference editor/IDE

Zed Industries' Rust editor rides the GPUI framework, which is GPU-first (Metal / `blade` / Vulkan) over a platform `unsafe` layer; Zed spawns language servers as subprocesses, drives syntax with tree-sitter (a C library), and ships networked collaboration.
Re-targeted: GPUI's renderer moves to **software on V-class cores** — the same substrate COSMIC and Servo need, built once and shared — and its platform `unsafe` routes through the verified HAL (§5, obstacle 1).
The LSP subprocess model has no `fork`/`exec` (§2): each language server becomes a **capability-delegated Tier-2 compartment reached over a ring** (§12), started by the service manager's static supervision tree (§12), not by the editor's ambient authority (obstacle 3). tree-sitter's C core is a `-sys` FFI dependency and thus inadmissible as-is — either contained behind the verified HAL or replaced by a pure-Rust grammar runtime; note that parsing *local* source is **not** the §5 attacker-facing-wire mandate (which governs remote formats), so tree-sitter stays ordinary contained code, not a Narcissus obligation.
Collaboration rides the §12 IPv6/TLS network stack; file and clipboard access is powerbox-mediated (§14).

**Disposition:** Tier-2, gated on the shared software-render substrate and on shedding the tree-sitter and GPU `-sys` crates; the editor core — rope, multi-buffer, diagnostics, git — ports as clean safe Rust.

### coreutils / findutils / diffutils — reimplemented capability-native core utilities, based on uutils

These reimplement GNU coreutils/findutils/diffutils in Rust — yet §14 mandates core utilities **reimplemented, not ported**, and that tension is the whole story.
Their pure-computation core — the `sort`/`wc`/`cut`/`cat` byte plumbing, `diff`'s Myers algorithm, `find`'s predicate matcher — is exactly reusable safe Rust and transfers verbatim.
Everything that assumes POSIX ambient authority does not: `chmod`/`chown`/`id`/`groups` (no uid/gid, §2/§8), `kill`/`ps`/`nice` (no ambient process table or signals, §2), `mount`/`mknod`/symlink semantics against a global VFS (the "filesystem" is a manifest-backed private namespace, §14), and every `nix`/`libc` `unsafe` FFI call that reaches for a syscall (§5, obstacle 1) — all are **deleted or re-expressed** as capability operations (obstacle 3).
So the three projects are adopted not as a *port* but as the **seed corpus** for §14's capability-native reimplementation: their algorithms populate the utilities while their POSIX surface is discarded, which honors "reimplemented, not ported" by construction rather than by exception.

**Disposition:** Tier-2; harvest the computational core, drop the ambient-authority commands wholesale, and re-issue the survivors against the capability libc — the closest thing on this list to a clean lift, precisely because the hard part is subtraction.

### gitoxide — the capability-native version-control engine

Sebastian Thiel's gitoxide (the `gix` crate family, with the `ein`/`gix` CLIs) is a from-scratch pure-Rust Git — and Git, structurally, is a VerifiedOS mechanism wearing POSIX clothes: its object database — blobs, trees, commits, tags, each named by the hash of its own bytes — is precisely the content-addressed **Merkle DAG** of §10, the very lineage that store is modeled on, so re-targeting keeps Git's data model as *vocabulary* and moves its enforcement — and its storage — onto the substrate.
Five seams dominate.
**(1) The hash is SHA-1 — inadmissible.**
A verification-maximal store cannot content-address by a collision-broken function (SHAttered), even SHA-1DC-hardened; the port is **SHA-256-only through the §5 verified crypto core** (Git's SHA-256 object format made mandatory), so object-graph integrity rests on the same verified hash as §10.
**(2) The pack/wire protocol is attacker-facing.**
A `fetch`/`clone` pulls a remote's pkt-line stream, packfile, and pack index over §12's IPv6/TLS network, and a hostile remote controls those bytes *together with* hashes that match them — so the pkt-line framing, the pack/idx decode, the delta-instruction stream, and the tree/commit/tag object decoders are §5 **Narcissus** verified copy-once parsers (like GGUF's container, and pointedly *unlike* Servo's deliberately-contained content parsers); only opaque blob payloads pass through as content.
The DEFLATE codec beneath them is Narcissus's residual — a hardened pure-Rust inflate (`zlib-rs`/`miniz_oxide`, shedding the `-sys` zlib), memory-safe but not proof-carrying.
**(3) Git shells out constantly; nothing may.**
`upload-pack`/`receive-pack`, credential and `ssh` helpers, `gpg`/`ssh-keygen` for signature checks, clean/smudge filters, hooks, pager, and editor are all `fork`/`exec` (§2) — each becomes a capability-delegated compartment on the service manager's supervision tree, reached over a ring (§12, obstacle 3); signature *verification* in particular routes to the §5 crypto core rather than exec-ing `gpg`.
Path-relative `.git`, the index, the ref store, and working-tree checkout become a manifest-backed private namespace (§14), powerbox-mediated for anything outside it.
**(4) The `unsafe` is mmap.** gitoxide is already `#![forbid(unsafe_code)]` across its own crates; the residual `unsafe` lives in `memmap2`, used to map packs — deleted for capability file reads against the §14 namespace or routed through the verified HAL (§5, obstacle 1).
**(5) Git's on-disk storage layer is redundant against §10.**
Loose objects, packfiles, delta chains, `gc` repacking, and zlib are Git's *own* reimplementation of content-addressing, dedup, and compression on a dumb POSIX filesystem — and each is already a native, **verified** primitive of the store, which §10 spells out exactly: *dedup is content-addressed extent sharing, reflinks are refcounted CoW extent sharing, snapshots are retained roots keyed by snapshot-version, and checksums are the per-extent AEAD tags*.
So the port stores each object as a plain uncompressed extent and lets the store do the rest: identical objects and their shared blocks collapse by **content-addressed dedup** — superseding Git's delta chains (extent-granular rather than byte-level, the ratio cost being the one §10 already books when it drops compression), and **bounded to gitoxide's confidentiality domain**, since §10 forbids cross-domain dedup as a content-equality oracle.
`checkout` then materializes a working tree by **reflink** from those extents — O(1), copy-on-write on first write, possible *only because* the object is stored uncompressed (there is nothing to reflink out of a zlib-deflated pack) — while `gc` evaporates.
The security ledger improves twice: the on-disk DEFLATE of seam (2) vanishes (objects rest uncompressed, exactly §10's stance that removing compression is a *security gain*, not a mere scope cut, leaving only the transient *wire* inflate at fetch), and crash-safety and integrity leave gitoxide's own fsync-and-rename dance for §10's **verified** L0 journal, per-extent AEAD, and L3 data-noninterference.
No second structure is needed: §10's *"everything is a b-tree"* unification absorbs both of Git's stores at once — immutable objects as content-addressed, dedup-shared, AEAD-sealed extents, and mutable refs, the index, and the reflog as keys in the same keyspace, the reflog falling out of snapshot-versioning for free.
Being neither a GUI nor a JIT host, gitoxide clears obstacles 2 and 4 for free; what remains is the subtraction of ambient authority — the coreutils shape — joined by a move the coreutils lift has no analogue for: collapsing Git's bespoke object store onto the verified §10 store.

**Disposition:** Tier-2; adopt gitoxide's safe-Rust core — object model, ref store, revision walk, diff/merge — as a near-clean lift, **re-home storage onto the §10 store** so its native content-addressed dedup, refcounted-CoW reflinks, and O(1) snapshots subsume loose objects, packfiles, delta chains, and `gc` (packing survives only as a *wire* codec, never an on-disk format, and crash-safety is inherited from the verified journal rather than re-implemented), gate admission on the §5 Narcissus proof for the pack/pkt-line/idx/delta and object decoders, mandate **SHA-256-only** through the verified crypto core with SHA-1 dropped, shed the `memmap2`/zlib `-sys` dependencies, and collapse the hook/helper/credential/signing subprocess menagerie into supervision-tree compartments (§12).

### Servo — the contained browser engine

The Rust browser engine is §14's browser made real. Its per-origin architecture — the constellation, per-origin script and layout — maps directly onto §14's **per-origin capability compartments**, so an origin RCE yields only that origin's authority and nothing else.
Three obstacles dominate.
**(1) The JS engine is the gating sub-project.**
Servo embeds SpiderMonkey (`mozjs`) — C++, JIT, and a vast `unsafe` binding surface — and §14 forbids JIT on anything network-facing (interpreters run pure, obstacle 4).
SpiderMonkey-in-interpreter-mode is still unverifiable C++ that cannot carry the Tier-2 safe-Rust certificate, so the spec-coherent target is a **pure-Rust, interpreter-only engine** (Boa-lineage), accepting its web-incompleteness as the honest cost; `mozjs` restricted to its C interpreter behind CHERI containment is the pragmatic, *non-conforming* interim.
This is the browser's defining unresolved tension, recorded rather than hidden.
**(2) WebRender is GPU-first** and falls back to software rendering on C/V-class cores under §12 (§14, obstacle 2).
**(3) Content parsers stay contained, not verified.** html5ever, the CSS parser, and the JS front end all consume attacker-controlled input, but §14's stance is that the browser is *unverifiable, therefore maximally contained* — so these remain memory-safe Rust inside the origin compartment; the §5 Narcissus mandate binds the *network wire* (TLS/HTTP, §12), not the DOM.
File and clipboard access is powerbox-only (§14).

**Disposition:** Tier-2 per-origin compartments; adopt Servo's engine and compartment model, treat the pure-interpreter JS engine as the hard gating dependency, and reuse the shared software-render substrate.

### GGUF inference runtime — the M-class inference server

GGUF is llama.cpp's GPT-Generated Unified Format, the de facto container for quantized local models.
Unlike the others this is not a clean application lift but a **framework re-target grafted onto a net-new hardware backend**: the `burn` deep-learning framework carried across as safe Rust, with the M-class GEMM engine written as a custom `burn` backend beneath it.

llama.cpp itself (C++, with CUDA/Metal/Vulkan backends and heavy `unsafe`) is rejected as a base on every §5/§15 axis — but the alternative is a re-target, not a from-scratch runtime.
The Rust ecosystem offers three candidates, and the choice among them is settled by the one genuinely net-new artifact here, the **M-class backend**: `candle` (HuggingFace) is GGUF-native and minimal but bakes its devices (CPU/CUDA/Metal) into enum-dispatched storage, so a new accelerator is invasive surgery; `mistral.rs` sits on `candle` and piles on the largest feature surface — paged attention, a sampler zoo, MoE routing — precisely the data-dependent-timing surface (b) below wants *minimized*.
**`burn` is the fit:** its defining abstraction is a backend-agnostic `Backend` trait, so the M-class systolic GEMM engine drops in as one bounded trait implementation while the model definitions, tensor graph, and quantization/dequant logic above it are reused verbatim as safe Rust (its training/autodiff machinery, dead weight for inference, is shed).
The result is the concrete instantiation of §12's optional **inference server**: a Tier-1 compartment that owns the M-class cores (§15: systolic 32×32 int8 / 16×16 bf16 GEMM, VLEN=1024, software-managed scratchpad), exposes quantized-inference sessions over rings (§12), takes GGUF models as content-addressed store objects (§10), and zeroizes per-session memory on teardown (§12).
Two spec hooks are load-bearing.
**(a) The GGUF container parser is attacker-facing** — a downloaded model is untrusted input — so its header/metadata/tensor-map decode is a §5 **verified copy-once parser** (Narcissus), *unlike* the browser's deliberately-contained content parsers — and it is authored fresh regardless of framework, since neither `burn` nor `candle` ships a distrust-hardened GGUF front end.
**(b) Timing.**
Dense-GEMM decode over a fixed model geometry is naturally data-independent (favorable for the §15 `Zkt`/`Zvkt` posture), but token-dependent sampling, KV-cache-length-dependent work, and any mixture-of-experts routing are genuine data-dependent channels; a session carrying secret-labeled prompts (§8/§13) therefore either scopes a constant-time obligation onto exactly those paths, or the flow theorems (§8, §13) must forbid secret material from reaching it.
No CUDA/GPU path exists (§15); throughput is the honest M-class envelope (§15 capacity honesty), not datacenter-class.

**Disposition:** adopt `burn` as the safe-Rust framework and write the M-class GEMM engine as a custom `burn` backend — the single net-new artifact, the systolic units having no existing backend — shedding `burn`'s training/autodiff; verify the GGUF parser (§5), route all matrix work through the M-class capability-operand movers (§15, no private DMA), and treat sampling/routing data-dependence as the residual to bound or label-fence.
`candle`/`mistral.rs` are the rejected re-target alternatives — GGUF-native but enum-baked backends, `mistral.rs` maximizing the very data-dependent surface (b).

---

## Shared prerequisites

All six gate on the same handful of net-new artifacts, so they are sequenced behind them rather than each solving them privately:

- **The certifying Rust→RV64+CHERI toolchain (§18)** is the hard, no-fallback prerequisite for *building or admitting any of them* — userspace availability gates on it exactly as desktop instantiation gates on CHERI silicon (§18).
- **A software rendering/compositing library on V-class cores** — the substrate COSMIC's compositor, Zed's GPUI, and Servo's WebRender all collapse onto — is built once under the §12 display model and shared across the three GUI targets.
- **The WASI-shaped capability libc (§14)** and its manifest-backed namespace is the common on-ramp every source-level re-target compiles against.
- **The reference display server** (COSMIC's `cosmic-comp`, above) that the other GUI apps present surfaces to under per-surface / per-input capabilities (§12).

---

## Deterministic simulation testing — catching what the certificate does not prove

The Tier-2 admission floor (§13) certifies *memory safety* — CHERI enforcing spatial bounds at runtime while the certificate discharges the temporal-safety, CFI, and no-runtime-codegen residual — and says nothing about *behavioral* correctness: gitoxide's delta resolution and merge, Servo's pure-interpreter event loop, `cosmic-comp`'s surface-to-input mediation, and Zed's language-server orchestration are all memory-safe-by-certificate yet logic-correct-by-nothing.
That un-proven behavioral space — the bugs no one thinks to write a test for — is where a **deterministic simulation testing** harness earns its keep in continuous integration, and the [golden-model implementation plan](implementation-plan.md) already supplies the one artifact such a harness is otherwise hardest to build: a **deterministic, full-system substrate**.
The Sail C-backend emulator is that substrate by construction, the CertiCoq→Wasm host-side reference is a second one for fast iteration, and the plan already leans on **differential testing against the Sail golden model** as its bring-up oracle — simulation testing is that same move made systematic: fault-injecting, coverage-guided, and replay-exact.
Four properties of the machine make it unusually amenable:

1. **The nondeterminism is designed out, not suppressed.**
   Static-only branch prediction with zero mutable predictor state, `Ztso` fixed ordering, no `LR`/`SC` reservation set, a static supervision tree in place of `fork`/`exec`, and the admission-test-3 rule that *no hidden state survives a partition switch* (§15) delete — at the ISA and OS level — the very nondeterminism sources a conventional simulator spends its effort papering over, so a replay is bit-exact and a failing schedule reproduces on the first attempt rather than as a flaky heisenbug.
2. **The specification is already the property oracle.**
   The invariants worth asserting are written down as theorems: the §8/§13 information-flow properties (no surface observes another's input, no secret reaches a data-dependent path), §10 RefFS linearizability ⋈ liveness, and §12 capability confinement.
   A run that violates one is a defect with a deterministic witness, not a symptom to be chased.
3. **Fault injection has native hooks.**
   Crash-consistency is exercised against §10's Perennial-verified journal crash semantics; toxic-wire robustness is exercised by fuzzing the §5 Narcissus decoders — gitoxide's pack/pkt-line/idx stream, the GGUF container header — the empirical complement to the copy-once proof, aimed at exactly the attacker-facing surfaces that proof governs.
4. **The oracle is free and doubled.**
   The same workload runs on both golden models — CertiCoq→Wasm host-side ⋈ purecap-on-Sail — and any divergence between them is itself a defect; the safe-Rust targets additionally take source-level `cargo-fuzz` and property testing *before* re-target, upstream of the substrate entirely.

**Discipline:** this is a bring-up gate and a defense-in-depth net, never an axiom.
Simulation testing is *unsound* — it exhibits bugs, it does not prove their absence — so it occupies exactly the slot the specification reserves for mature-but-unsound tooling (Binsec/Rel for constant-time, riscv-formal BMC for refinement, aiT for WCET): path-bounded evidence that gates a pull request and accelerates the un-proven behavioral space, but that never enters the trust base and never stands in for a §13 obligation.
Its one structural advantage over that tooling is that the substrate it runs on is not an approximation of the target — the **RTL ⊑ Sail** refinement proves the silicon refines the very model the tests execute on, closing the "does the simulator match production?" gap that black-box simulation testing must always leave open.
