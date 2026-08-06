# Userspace Porting Targets (non-normative)

> Externalized companion to [verification-maximal-os.md](verification-maximal-os.md).
> This is a **non-normative roadmap**, not part of the specification: an inventory of the userland the platform must have, followed by the first applications slated for porting, each mapped to the normative mechanism (§N of that document) it is authored or re-targeted onto.
> It is the userland analogue of [Evaluated Architectural Alternatives](architectural-alternatives.md) and carries no normative weight: every target still enters through the Tier-2/Tier-1 admission discipline of §13, and a name here is a *statement of intent*, not a grant of exception.

"Porting" here is a term of art.
There is **no Linux-personality shim and no legacy VM** (§2, §14): a foreign binary does not run, ever.
Every *ported* entry is therefore a **source-level re-target**, recompiled against the WASI-shaped capability libc (§14) straight to native RV64+CHERI, its ambient-authority assumptions stripped and re-expressed as explicit capabilities (§8), admitted only once it carries the proof its tier demands (§13).
Much of the userland is not ported at all: the servers §12 mandates (the next section) are **authored** against the typed IDL, because nothing upstream implements what they are.
The selection is **uniformly Rust** by design: safe Rust is memory-safe by construction (§5, §14), so a port whose whole dependency closure is `#![forbid(unsafe_code)]` is the cheapest path to the mandatory Tier-2 memory-safety certificate (§13), the certifying Rust→RV64+CHERI toolchain (§18) discharges it automatically, and rustc/LLVM never enter the trust base.
This is a selection *economy*, not a language mandate: admission gates on the binary-level certificate, not the source (§13), so a formally-verified non-Rust component, Project Everest (miTLS, HACL\*/EverCrypt) and the F\*/Low\* lineage (§5), is admissible on equal terms, its foreign-prover verification bonus assurance that never enters the trust base.

## Required system userland

The specification does not leave userland open.
§12 names a fixed set of servers without which the system cannot boot, unlock, update, consent, or render, and several are load-bearing in ways no application is: one is the sole userland-resident member of the TCB (§6), several are Tier-1 cross-domain servers carrying flow theorems (§13), and one is resident on a core of its own.
They come first because their sequencing dominates: the roster below is elective and stageable (§18), this half is not, though it is itself ordered (**Sequencing**, below).

Most of them are not ports.
There is no upstream to re-target for a powerbox, a trusted consent path, or a signed translator graph, and where an ancestor exists (systemd's supervision model, Plan 9's plumber and Factotum, BeOS's translators, bcachefs's structure) the design takes the *pattern* and supersedes the mechanism, exactly as [inspirations.md](inspirations.md) records.
The four obstacles below still bind on whatever code these do reuse, but *which crate do we start from* mostly has no answer here, and the honest cost is authoring against §12's typed IDL rather than subtraction from a POSIX original.

- **Powerbox and trusted-path agent** (§6 item 7, §8, §12), the **consent TCB**: the one userland component the non-interference theorem trusts, because it mints the single capability edge not fixed at compose time and a wrongful declassification is a legitimate capability operation CHERI cannot catch.
  It is not one program but three cooperating pieces: the powerbox itself, the agent that renders the consent surface into a region it holds by capability under the RoT-driven secure-attention indicator (§9), and the fixed threshold-and-centroid reducer, with no adaptive state, that reads raw front-end frames while the touch AFE's ownership is RoT-latched away from its driver (§12, §15).
  Authored and verified, never ported; and nothing on the roster below is admissible before it exists, since every file, camera, microphone, and device grant an application ever receives passes through it.
- **Service manager** (§12): the static supervision tree, declarative units, restart with backoff and capability re-grant, an authority *re-instantiator* that mints nothing.
  Not a Rust port at all: its control plane is the canonical synchronous Lustre program compiled through Vélus (§5, §12), so it is authored in the control-plane language and inherits structural WCET and determinism instead of being re-targeted from an existing init.
- **Credential & unlock service** (§12, §9): primary-credential matching, the biometric matcher confined to its own sub-manifest (§14), the duress credential, and the Before-First-Unlock to After-First-Unlock key-custody transition.
  Authored; the matcher is the only part with plausible upstream, and is precisely the part that must be contained.
- **Sealing & attestation service** (§12): the crypto core's userspace face (seal/unseal, quotes, reference-manifest retrieval, monotonic counters) and, as protocol-credential broker, the non-exportable typed credential capabilities TLS, WireGuard, and WebAuthn clients hold instead of a signing oracle.
  Plan 9's Factotum is the design ancestor for the protocol-code-versus-key-custody split, not a lift.
- **Rollback-manager service and UI** (§12, §9, §10, §11, §16): untrusted and non-TCB, but required, and carrying a constraint no application has.
  It is also the payload of the boot-selected recovery generation (§9), so it must build and run inside a minimal signed image with no desktop beneath it.
- **Object fabric** (§12): the contained control-plane service joining Plan 9's private namespace and plumber to BeOS's typed attributes and translators, resolving intents over a signed composition-time handler graph while minting nothing.
  Authored: there is no runtime handler registration, launcher, or content sniffing to port from.
- **Media and translator graph** (§12): the one-shot conversion chains and the streaming media templates, including the audio path (raw PCM/PDM from the front-ends, with filtering, echo cancellation, beamforming, and any Opus or AAC coding all host software, §15).
  This is the sharpest constraint in this half, and the reason the decoder story cannot live on the roster below: §12 makes **every content format such a node parses attacker-facing wire**, so image, font, archive, and media decoders are §5 Narcissus obligations enumerated in the wire-format inventory, not safe-Rust crates lifted intact.
  `image`, `symphonia`, and the pure-Rust font stack are references for the algorithms and the geometry; the parsers are re-derived.
- **Filesystem, block, and storage servers** (§12, §10): the four-layer verified stack is a §18 verification workstream rather than a port, while the availability-layer services below the §10 integrity line (replication, erasure coding, tiering, allocator and copygc, and the host-side FTL) are ordinary Tier-1 safe Rust.
- **Drivers** (§12, §15): one compartment per device, and under the sensor-front-end doctrine each carries the host-side DSP a commodity system hides inside device firmware (touch, audio, IMU, image, fingerprint), alongside the USB stack, the NIC path, and scanout.
  These are the net-new co-design booked in §17, not re-targets: the firmware-free part does not exist to port from.
- **Radio L2/L3 servers** (§12, §15): the software half of the dissolved-radio thesis, the 802.11 MLME element grammars and the cellular RRC/NAS ASN.1 UPER path, which §5 names as the most-attacked remote parse surfaces in consumer computing and holds to the Narcissus discipline, with the protocol state machines beside them as Lustre/Vélus control planes (§5, §12).
  Authored by necessity, since the firmware-free implementation is precisely what does not exist, which is the thesis: srsRAN/srsUE, OpenAirInterface, and openwifi are the feasibility existence proofs §18 names rather than lifts, and asn1scc and the Wireshark dissectors are differential oracles that enter no trust base (§5).
  This is required userland for the first release, not deferred with cellular: §18 ships Wi-Fi-only, so the 802.11 half of it is on the critical path.
- **Time service** (§12, §9): one wall clock disciplined from three graded authenticated sources (Roughtime, then NTS, then secure PTP over the hardware timestamp unit), with precision itself a capability (§8).
  `roughenough` appears below as a start-from for one source; the service that cross-checks all three, and holds the monotonic floor across a cold boot on a machine with no real-time clock, is authored.
- **Telemetry monitor and emergency-call compartment** (§12): the former permanently resident on the S-class sentinel core, the latter a zero-authority compartment reachable at Before First Unlock.
  Both small, both authored, both required.

Three §12 servers appear in the roster below rather than here, because unlike the rest of this half they have genuine start-froms: the network stack (smoltcp, hickory-dns, roughenough), the inference server (`burn`), and the reference display server (`cosmic-comp`).
The split runs through COSMIC: the **compositor** is required userland, the **shell** around it is elective.

---

## Roster: the elective applications

These are stageable behind the userland above, in the order **Sequencing** (below) sets out; §18 already fixes two points in it, shipping Wi-Fi-only and deferring the browser.

- **COSMIC Desktop**, the shell, with its `cosmic-comp` compositor promoted to the reference §12 display server (compositor: Tier-1; shell applets: Tier-2).
- **Zed**, the reference editor, a software-rendered Tier-2 app: its GPU-first framework and its C parsing runtime are both bounded re-targets, and it carries no language-support commitment.
- **coreutils / findutils / diffutils** from uutils, the seed corpus for §14's capability-native core utilities (Tier-2).
- **gitoxide**, the pure-Rust Git, re-targeted as the capability-native version-control engine; its object store re-homes onto §10's verified CoW B-tree (native dedup, reflinks, snapshots, Git's packfiles and `gc` shed) and its pack/wire decoders are a §5 Narcissus obligation (Tier-2).
- **NuShell**, the structured-data shell, re-grounded as the capability-native command interpreter: its typed value pipeline is the shell-level analogue of §12's data plane, its builtin-heavy command set shrinks the `fork`/`exec` surface, and its plugins become §12 ring-reached compartments (Tier-2).
- **Servo**, the contained, per-origin browser engine of §14 (Tier-2 origin compartments), which §18 defers past the first release.
- **GGUF inference runtime**, the §12 optional inference server on the M-class cores: the `burn` deep-learning framework re-targeted onto a net-new M-class GEMM backend (`burn`'s pluggable backend trait is the clean seam), not a from-scratch build (Tier-1).
- **Network stack**, the §12 IPv6/TLS/DNS/Roughtime compartments (**smoltcp**, **hickory-dns**, **roughenough**) retargeted onto the rings, every wire format a §5 Narcissus obligation; the TLS compartment prefers a Rust-native **hax**-verified stack (**Bertie**) over the mature F\*/Low\* **miTLS**, and the DNS/TCP compartments gate on SPARK/HOL4 differential oracles that enter no trust base (Tier-1).

---

## The porting discipline: four obstacles every target meets

Independent of the application, the same four substrate mismatches are re-targeted the same way, so they are stated once here and referenced per target below:

1. **`unsafe` must go.**
   FFI shims, GPU bindings, and hand-rolled synchronization are inadmissible in app logic (§5): each `unsafe` site is either deleted with the POSIX/GPU assumption that motivated it or routed through the formally verified HAL (§5).
   A dependency that cannot shed its `unsafe`, a C library behind a `-sys` crate, is itself a sub-port, and the audit that finds them runs over the whole dependency closure rather than the crate that names the target (below).
2. **GPU dependence becomes software compute.**
   There is no fixed-function GPU, no Vulkan/Metal/wgpu path, no CUDA (§15).
   Rendering, compositing, and codecs move to software on the V-class cores; matrix/AI work moves to the M-class GEMM units (§15), both under the §12 display/inference model, never a driver.
   The replacement is not a software implementation of a graphics API: every mature one JITs its shaders, which W^X forbids (§14), and an emulated API would reintroduce the shader-IR compiler and command-stream validator §12 excludes from the display path, for no gain, since the pixels are computed by the vector unit either way.
   What survives is the shader as a *program*: §13 already admits one, AOT-compiled and certified off-device and dispatched like any other binary, and this costs these toolkits nothing, because their shader sets are fixed at build time and none of them needs to generate one at runtime.
   The shading languages survive with it, as build-time intermediates the certifying toolchain consumes; the API question is weighed per mechanism in [Evaluated Architectural Alternatives](architectural-alternatives.md).
3. **Ambient POSIX authority becomes explicit capabilities.**
   No `fork`/`exec`, no uid/gid, no `/proc`, no CWD-relative path resolution (§2, §8).
   Process trees become the service manager's static supervision tree (§12); path-based file access becomes a manifest-backed private namespace (§14); "spawn a helper" becomes a capability-delegated compartment reached over a ring (§12).
4. **No runtime code generation, anywhere.**
   Compilation is an off-device build step (the certifying toolchain, §5/§18), never an on-device service; nothing on the device JITs (§14), so any embedded script/Wasm engine runs **pure-interpreter**.

---

## The dependency closure is the unit of work

A name on the roster is the top of a graph, not the graph.
`#![forbid(unsafe_code)]` is a property of one crate, while the admitted artifact is the whole linked image and the Tier-2 certificate (§13) is a derivation over everything in it, so the unit that must be audited, re-targeted, and admitted is the target's entire dependency closure.
For the GUI entries that is hundreds of crates, and the honest cost of a port is stated over the closure rather than over the name.

Four dispositions exhaust it, and every crate in a closure takes exactly one:

1. **Transfers.**
   Pure safe-Rust computation carrying no platform assumption recompiles and is done.
   Most of a well-factored closure is this, which is the whole reason these targets are worth starting from.
2. **Deletes with its assumption.**
   A crate that exists only to abstract a platform this design does not have goes with the assumption that motivated it: the POSIX and libc shims, the readiness-driven event loops, the thread-pool and processor-count probes, the home-directory and path resolvers, the memory-mapping wrappers.
   This is the subtractive case obstacles 1 through 3 describe, and it cascades, since deleting one such crate usually deletes a subtree.
3. **Sub-ports.**
   A `-sys` crate wrapping a C library is a port of its own, or a replacement, and there is no third option: a foreign binary never runs (§2, §14), and C inside an application image has no route to the memory-safety floor that an app-tier component can take, verified C under CompCert being the TCB's route (§5) rather than userland's.
   tree-sitter under the editor, SpiderMonkey under the browser, and zlib under the version-control engine are the named instances below.
4. **Compartments.**
   A dependency that is *memory-safe and still dangerous* is the case safe Rust does not settle, and §14 makes the disposition mandatory rather than advisory: any dependency parsing attacker-controlled input (media, image, font, archive, compression, wire formats) and any third-party library handed capabilities becomes an intra-app compartment with its own least-authority sub-manifest (§8, §14).
   Memory safety does not make a decoder correct, and linked flat such a dependency runs with the app's *whole* manifest (§14).

**The closure is also the supply-chain surface, and §13 already governs it, in two halves that need different answers.**
§3 splits the threat: *tampering*, bytes that do not correspond to the reviewed source, is answered by the source-correspondence theorem binding the installed bytes to the **exact included source closure** (§13); *subversion*, a logic backdoor present in that source, compiling cleanly and carrying a valid certificate, is answered only by compartmentalization (§13, §14), because no proof about the artifact can catch it.
Note what §13 does *not* demand: bit-for-bit reproducibility is mandatory for the base image, and with DDC for the two checker binaries no certificate can cover (§6), while every other binary is admitted on its checked source-correspondence theorem, so a closure is bound to its source rather than to a particular builder.
Build scripts and procedural macros are worth naming separately: they run on the build host, so whatever they emit must itself fall inside the included source closure that theorem binds, and a build step whose output depends on the build machine rather than on that closure is precisely what it refuses.
Most of them exist to probe a platform or to compile C, and this design deletes both.

**The per-target dispositions below are the head of a closure audit, not a substitute for one.**
The audit produces four lists rather than a verdict, and producing them is the cheapest useful early work on any of these targets, because it is mechanical and it tells you the real size of the port before anyone writes a line of it.
It also cuts both ways: the closure is larger than the name suggests, and class 2 is subtractive enough that the survivors are usually a fraction of it.

---

## Targets

One section per roster entry above.
The required userland is not repeated here: having no upstream to analyze, it carries an inventory rather than a per-target disposition.

### COSMIC Desktop: the shell, and the reference compositor

System76's Rust desktop, the `libcosmic`/`iced` toolkit, the `cosmic-comp` compositor on smithay, cosmic-text, assumes Wayland-over-Linux: DRM/KMS scanout, a GPU through wgpu/OpenGL, evdev/libinput.
Re-targeted, **`cosmic-comp` becomes the reference §12 display server**: it already embodies the "surfaces are plain memory, input and output are mediated" model that §12 mandates, so Wayland's global-registry ambient objects are replaced by **per-surface and per-input capabilities** (keylogging and screen-scraping become unexpressible, §12), DRM/KMS is replaced by the firmware-free scanout controller behind a static capability-bounded DMA window (§12, §15), and the wgpu/OpenGL path becomes **software compositing on V-class cores** (§12, obstacle 2).

**The toolkit half of that renderer largely exists upstream.**
`iced` is renderer-agnostic by construction and already ships two backends, `iced_wgpu` and a software `iced_tiny_skia` built on the very crate §12 names as the 2D start-from, so the shell and its applets reach the substrate through a seam their toolkit already has rather than through a rewrite.
The compositor is the half that needs the work, and its renderer is a backend against the shared substrate on the same terms as the other GUI targets: its shader set, like theirs, is fixed at build time and so AOT-compiles and is certified off-device (§13, obstacle 2).

Because the compositor mediates between mutually distrusting clients, many origins' and apps' surfaces and input events, it is a cross-domain **Tier-1** server carrying the §13 information-flow theorems that decide which surface may observe which input; the panel, launcher, settings, and applets are ordinary **Tier-2** apps built on `libcosmic`. libinput/evdev collapse to register-slave scan drivers (§12), and `fork`-spawned session helpers become supervision-tree compartments (obstacle 3).

**Disposition:** adopt `cosmic-comp` as the reference display-server seed and `libcosmic`/`iced` as the app toolkit, keeping the Wayland surface model as *vocabulary* while its enforcement moves to capabilities.
The largest work is not the renderer: it is shedding smithay's Linux backend layer (DRM and GBM, EGL, libinput, udev, session and seat), which goes with the assumption that motivated it (closure disposition 2), and re-grounding the compositor's mediation on per-surface and per-input capabilities under Tier-1 information-flow obligations no other target on this roster carries.

### Zed: the reference editor

Zed Industries' Rust editor rides the GPUI framework, which is GPU-first (Metal, `blade`, Direct3D) over a platform `unsafe` layer; it drives syntax with tree-sitter, whose parsing runtime is C, spawns language servers as subprocesses, and ships networked collaboration.
The first three read as blockers and are not: two are bounded re-targets, and the third is scoped out rather than solved.

**The renderer is the smallest of the three GUI re-targets, not the largest.**
GPUI is not a general graphics-API consumer but a specialized 2D scene renderer over a small fixed primitive set (rounded quads with borders and gradients, drop shadows, monochrome glyph sprites from an atlas, polychrome image sprites, underlines, filled paths, platform surfaces) drawn by on the order of a dozen hand-written shaders.
That set is signed-distance-field and blit shaped rather than triangle-mesh shaped, which is the shape a wide vector unit suits: per-pixel evaluation over a primitive's bounding box is branch-free and parallel, and filled paths are the one awkward member.
It also already carries a backend seam, having been implemented over Metal, over `blade`, and over Direct3D, so a fourth backend against the shared substrate is known-shaped work rather than a new framework.
Obstacle 4 never bites it: the shader set is fixed at build time, so it AOT-compiles and is certified off-device like any other code (§13, obstacle 2).
The other half of that backend is the platform layer (windowing, input, clipboard, frame timing), which is where GPUI's `unsafe` lives and which becomes ordinary §12 display-server client work under per-surface and per-input capabilities.

**tree-sitter is a sub-port with prior art, and the tables are why it is bounded.**
Its parsing runtime is C, so the `-sys` crate is inadmissible (closure disposition 3), but two facts keep the replacement small: the grammar *generator* is already Rust and runs off-device at build time, exactly where compilation belongs (obstacle 4), and a generated grammar is overwhelmingly static parse tables rather than code.
A safe-Rust runtime consuming those tables behind a Rust-native API is therefore bounded work against a stable data format.
ast-grep's Rust rewrite of the C runtime serves as a functional reference and differential oracle, and as evidence that the rewrite is performance-positive, but it is not the artifact to adopt: it preserves the C binary interface, which is both the constraint that forces pervasive `unsafe` and a constraint nothing here needs, since no component on this platform links that library.
The residue is the external scanners, since the grammars needing context-sensitive lexing ship hand-written C ones, so every grammar actually shipped carries a scanner rewrite with it.
Parsing *local* source is **not** the §5 attacker-facing-wire mandate, which governs remote formats, so the runtime is contained code rather than a Narcissus obligation; but source opened from a cloned repository is attacker-controlled input, so §14 makes it a mandatory intra-app compartment with its own sub-manifest (closure disposition 4) whatever language it is written in.

**No language support is promised, and the editor does not depend on any.**
The LSP subprocess model has no `fork`/`exec` (§2), so a language server becomes a capability-delegated Tier-2 compartment reached over a ring and started by the supervision tree (§12, obstacle 3) rather than by the editor's ambient authority.
That is the mechanism, not a roster commitment: a language server is admissible only as certified native code (§13), and most of the ones in demand are programs written for a runtime this platform does not host.
Language support is therefore later work, taken only where it is near-free, meaning a server already written in admissible safe Rust and a grammar needing no external scanner.
The editor is useful before any of it, and nothing else on the roster waits on it.

**An editor is not an integrated development environment here, because nothing on the device compiles.**
Compilation and proving are off-device build steps (§5, §13) and nothing JITs (§14), so there is no on-device toolchain for an editor to drive: building, certifying, and admitting happen elsewhere, and the results arrive as signed generations (§11) or admitted images (§13).
That is a property of the platform rather than of this target, and it bounds what any editor on this roster can mean.
Collaboration rides the §12 network stack; file and clipboard access is powerbox-mediated (§14).

**Disposition:** Tier-2, gated on the shared render substrate and on nothing else, language ecosystems included.
Adopt the editor core (rope, multi-buffer, diagnostics, git integration) as clean safe Rust, write a fourth GPUI backend against that substrate with the shader set AOT-compiled and certified off-device, replace the tree-sitter runtime with a safe-Rust table consumer cross-checked against both the C and ast-grep implementations, rewrite one external scanner per grammar actually shipped, and treat language servers as a later addition admitted only where near-free.

### coreutils / findutils / diffutils: reimplemented capability-native core utilities, based on uutils

These reimplement GNU coreutils/findutils/diffutils in Rust, yet §14 mandates core utilities **reimplemented, not ported**, and that tension is the whole story.
Their pure-computation core, the `sort`/`wc`/`cut`/`cat` byte plumbing, `diff`'s Myers algorithm, `find`'s predicate matcher, is exactly reusable safe Rust and transfers verbatim.
Everything that assumes POSIX ambient authority does not: `chmod`/`chown`/`id`/`groups` (no uid/gid, §2/§8), `kill`/`ps`/`nice` (no ambient process table or signals, §2), `mount`/`mknod`/symlink semantics against a global VFS (the "filesystem" is a manifest-backed private namespace, §14), and every `nix`/`libc` `unsafe` FFI call that reaches for a syscall (§5, obstacle 1), all are **deleted or re-expressed** as capability operations (obstacle 3).
So the three projects are adopted not as a *port* but as the **seed corpus** for §14's capability-native reimplementation: their algorithms populate the utilities while their POSIX surface is discarded, which honors "reimplemented, not ported" by construction rather than by exception.
One capability the POSIX originals lack falls out of the content-addressed store (§10, §13): a file-movement utility (`cp`, `mv`) or a network download client, targeting the store, transfers a self-contained pack as a **set-difference**, writing and fetching only the objects the destination lacks, each verified by hash on arrival (the Git have/want and OSTree-pull behavior), the dedup kept within a confidentiality domain as §10 requires.

**Disposition:** Tier-2; harvest the computational core, drop the ambient-authority commands wholesale, and re-issue the survivors against the capability libc, the closest thing on this list to a clean lift, precisely because the hard part is subtraction.

### gitoxide: the capability-native version-control engine

Sebastian Thiel's gitoxide (the `gix` crate family, with the `ein`/`gix` CLIs) is a from-scratch pure-Rust Git, and Git, structurally, is a VerifiedOS mechanism wearing POSIX clothes: its object database, blobs, trees, commits, tags, each named by the hash of its own bytes, is precisely the content-addressed **Merkle DAG** the §10 store is modeled on, so re-targeting keeps Git's data model as *vocabulary* and moves its enforcement, and its storage, onto the substrate.
Five seams dominate.
**(1) The hash is SHA-1, inadmissible.**
A verification-maximal store cannot content-address by a collision-broken function (SHAttered), even SHA-1DC-hardened; the port is **SHA-256-only through the §5 verified crypto core** (Git's SHA-256 object format made mandatory), so object-graph integrity rests on the same verified hash as §10.
**(2) The pack/wire protocol is attacker-facing.**
A `fetch`/`clone` pulls a remote's pkt-line stream, packfile, and pack index over §12's IPv6/TLS network, and a hostile remote controls those bytes *together with* hashes that match them, so the pkt-line framing, the pack/idx decode, the delta-instruction stream, and the tree/commit/tag object decoders are §5 **Narcissus** verified copy-once parsers (like GGUF's container, and pointedly *unlike* Servo's deliberately-contained content parsers); only opaque blob payloads pass through as content.
The DEFLATE codec beneath them is Narcissus's residual, a hardened pure-Rust inflate (`zlib-rs`/`miniz_oxide`, shedding the `-sys` zlib), memory-safe but not proof-carrying.
**(3) Git shells out constantly; nothing may.**
`upload-pack`/`receive-pack`, credential and `ssh` helpers, `gpg`/`ssh-keygen` for signature checks, clean/smudge filters, hooks, pager, and editor are all `fork`/`exec` (§2), each becomes a capability-delegated compartment on the service manager's supervision tree, reached over a ring (§12, obstacle 3); signature *verification* in particular routes to the §5 crypto core rather than exec-ing `gpg`.
Path-relative `.git`, the index, the ref store, and working-tree checkout become a manifest-backed private namespace (§14), powerbox-mediated for anything outside it.
**(4) The `unsafe` is mmap.** gitoxide is already `#![forbid(unsafe_code)]` across its own crates; the residual `unsafe` lives in `memmap2`, used to map packs, deleted for capability file reads against the §14 namespace or routed through the verified HAL (§5, obstacle 1).
**(5) Git's on-disk storage layer is redundant against §10.**
Loose objects, packfiles, delta chains, `gc` repacking, and zlib are Git's *own* reimplementation of content-addressing, dedup, and compression on a dumb POSIX filesystem, and each is already a native, **verified** primitive of the store, which §10 spells out exactly: *dedup is content-addressed extent sharing, reflinks are refcounted CoW extent sharing, snapshots are retained roots keyed by snapshot-version, and checksums are the per-extent AEAD tags*.
So the port stores each object as a plain uncompressed extent and lets the store do the rest: identical objects and their shared blocks collapse by **content-addressed dedup**, superseding Git's delta chains (extent-granular rather than byte-level, the ratio cost being the one §10 already books when it drops compression), and **bounded to gitoxide's confidentiality domain**, since §10 forbids cross-domain dedup as a content-equality oracle.
`checkout` then materializes a working tree by **reflink** from those extents, O(1), copy-on-write on first write, possible *only because* the object is stored uncompressed (there is nothing to reflink out of a zlib-deflated pack), while `gc` evaporates.
The security ledger improves twice: the on-disk DEFLATE of seam (2) vanishes (objects rest uncompressed, exactly §10's stance that removing compression is a *security gain*, not a mere scope cut, leaving only the transient *wire* inflate at fetch), and crash-safety and integrity leave gitoxide's own fsync-and-rename dance for §10's **verified** L0 journal, per-extent AEAD, and L3 data-noninterference.
No second structure is needed: §10's *"everything is a b-tree"* unification absorbs both of Git's stores at once, immutable objects as content-addressed, dedup-shared, AEAD-sealed extents, and mutable refs, the index, and the reflog as keys in the same keyspace, the reflog falling out of snapshot-versioning for free.
Being neither a GUI nor a JIT host, gitoxide clears obstacles 2 and 4 for free; what remains is the subtraction of ambient authority, the coreutils shape, joined by a move the coreutils lift has no analogue for: collapsing Git's bespoke object store onto the verified §10 store.

**Disposition:** Tier-2; adopt gitoxide's safe-Rust core, object model, ref store, revision walk, diff/merge, as a near-clean lift, **re-home storage onto the §10 store** so its native content-addressed dedup, refcounted-CoW reflinks, and O(1) snapshots subsume loose objects, packfiles, delta chains, and `gc` (packing survives only as a *wire* codec, never an on-disk format, and crash-safety is inherited from the verified journal rather than re-implemented), gate admission on the §5 Narcissus proof for the pack/pkt-line/idx/delta and object decoders, mandate **SHA-256-only** through the verified crypto core with SHA-1 dropped, shed the `memmap2`/zlib `-sys` dependencies, and collapse the hook/helper/credential/signing subprocess menagerie into supervision-tree compartments (§12).

### NuShell: the capability-native command interpreter

NuShell is a shell built on a **structured-data pipeline**: typed values, tables, records, lists, and typed primitives, flow between commands that carry typed signatures, in place of the untyped byte stream a POSIX shell pipes and re-parses at every stage.
That one choice is why it, and not a faster POSIX shell (fish, Ion), is the fit: the typed pipeline is the shell-level analogue of §12's typed data plane, so the port *deletes* the per-command text re-parsing surface, the unstructured, attacker-facing plumbing the spec minimizes everywhere else (§5), rather than carrying it across.
Four seams re-target it.
**(1) The command model already shrinks obstacle 3.**
Most of NuShell's vocabulary is in-process safe-Rust builtins operating on structured values, so a pipeline of builtins spawns no processes at all, the `fork`/`exec` surface that dominates a POSIX shell is a fraction of the whole before any re-targeting begins.
What remains, invoking an external command, has no `fork`/`exec` (§2): it becomes a **capability-delegated spawn** through the service manager's supervision tree (§12), the callee reached over a ring rather than found by a `PATH` walk over a global namespace; the environment becomes a **typed, capability-scoped record** instead of a global string map, and `cd`, globbing, and `ls` against the ambient filesystem become the manifest-backed private namespace (§14, obstacle 3).
**(2) Plugins are already compartments.**
A NuShell plugin is a separate process speaking a serialization protocol (MessagePack or JSON) over stdio, which maps almost directly onto §12: each plugin becomes a **capability-confined Tier-2 server compartment reached over a ring**, started by the supervision tree, never by the shell's ambient authority.
The plugin protocol is then an attacker-facing wire between mutually distrusting compartments, so its framing and value decode are a §5 **Narcissus** copy-once-parser obligation, and the structured values crossing it carry schema bounds like any §12 message.
**(3) The evaluator is an interpreter, and stays one.**
NuShell parses to an internal representation and evaluates it; nothing is compiled to native, so it clears obstacle 4 by construction, no on-device codegen, no JIT (§14), and the parse-and-evaluate engine ports as ordinary pure-interpreter safe Rust.
**(4) The `unsafe` goes.**
NuShell's own crates are largely safe Rust, but dependencies reaching for OS facilities, terminal control, process spawning, filesystem metadata, carry `unsafe` FFI inadmissible in app logic (§5, obstacle 1); each is deleted with the POSIX assumption behind it or routed through the verified HAL.

**Disposition:** Tier-2, re-grounded in the coreutils spirit, *reimplemented, not ported* (§14): adopt NuShell's structured-pipeline engine, typed-command model, and plugin-as-compartment protocol as the seed, and discard the POSIX-ambient residue, external spawning, the global environment, the ambient filesystem, re-expressing it as capabilities, exactly as coreutils harvests its algorithms and drops its ambient-authority commands.
It is additive where the coreutils lift is pure subtraction: the typed pipeline is a positive alignment with §12, not merely a surface to strip, and it invites pushing past where NuShell stops, making a **capability handle a first-class pipeline value**, so authority is passed and composed in the pipeline the way data already is.
fish (a faster interactive POSIX shell) and Ion (Redox's shell, Rust, but POSIX-adjacent and not capability-native) are the rejected alternatives: both spend their design budget on interaction quality while keeping the byte-stream pipe and `fork`/`exec` spawn this port exists to delete.

### Servo: the contained browser engine

The Rust browser engine is §14's browser made real. Its per-origin architecture, the constellation, per-origin script and layout, maps directly onto §14's **per-origin capability compartments**, so an origin RCE yields only that origin's authority.
Three obstacles dominate.
**(1) The JS engine is the gating sub-project.**
Servo embeds SpiderMonkey (`mozjs`), C++, JIT, and a vast `unsafe` binding surface, and §14 forbids JIT on anything network-facing (interpreters run pure, obstacle 4).
SpiderMonkey-in-interpreter-mode is still unverifiable C++ that cannot carry the Tier-2 safe-Rust certificate, so the spec-coherent target is a **pure-Rust, interpreter-only engine** (Boa-lineage), accepting its web-incompleteness as the honest cost; `mozjs` restricted to its C interpreter behind CHERI containment is the pragmatic, *non-conforming* interim.
This is the browser's defining unresolved tension, recorded rather than hidden.
**(2) WebRender is GPU-first** and falls back to software rendering on C/V-class cores under §12 (§14, obstacle 2).
**(3) Content parsers stay contained, not verified.** html5ever, the CSS parser, and the JS front end all consume attacker-controlled input, but §14's stance is that the browser is *unverifiable, therefore maximally contained*, so these remain memory-safe Rust inside the origin compartment; the §5 Narcissus mandate binds the *network wire* (TLS/HTTP, §12), not the DOM.
File and clipboard access is powerbox-only (§14).

**Disposition:** Tier-2 per-origin compartments; adopt Servo's engine and compartment model, treat the pure-interpreter JS engine as the hard gating dependency, and reuse the shared software-render substrate.
§18 places the whole program past the first release, so the gating engine question is sequenced rather than urgent: it is the one target whose deferral the specification states itself.

### GGUF inference runtime: the M-class inference server

GGUF is llama.cpp's GPT-Generated Unified Format, the de facto container for quantized local models.
Unlike the others this is not a clean application lift but a **framework re-target grafted onto a net-new hardware backend**: the `burn` deep-learning framework carried across as safe Rust, with the M-class GEMM engine written as a custom `burn` backend beneath it.

llama.cpp itself (C++, with CUDA/Metal/Vulkan backends and heavy `unsafe`) is rejected as a base on every §5/§15 axis, but the alternative is a re-target, not a from-scratch runtime.
The Rust ecosystem offers three candidates, and the choice among them is settled by the one genuinely net-new artifact here, the **M-class backend**: `candle` (HuggingFace) is GGUF-native and minimal but bakes its devices (CPU/CUDA/Metal) into enum-dispatched storage, so a new accelerator is invasive surgery; `mistral.rs` sits on `candle` and piles on the largest feature surface, paged attention, a sampler zoo, MoE routing, precisely the data-dependent-timing surface (b) below wants *minimized*.
**`burn` is the fit:** its defining abstraction is a backend-agnostic `Backend` trait, so the M-class systolic GEMM engine drops in as one bounded trait implementation while the model definitions, tensor graph, and quantization/dequant logic above it are reused verbatim as safe Rust (its training/autodiff machinery, dead weight for inference, is shed).
`burn`'s de-quantization and scaling code is the software front end that runs on the M-class VLEN=1024 vector unit (§15), unpacking arbitrarily-quantized weights (and applying the shared block-scale of MX microscaling formats) to the int8 or bf16 the systolic array consumes, so no fixed-format de-quant or block-scale hardware is required.
The result is the concrete instantiation of §12's optional **inference server**: a Tier-1 compartment that owns the M-class cores (§15: systolic 32×32 int8 / 16×16 bf16 GEMM, VLEN=1024, software-managed scratchpad), exposes quantized-inference sessions over rings (§12), takes GGUF models as content-addressed store objects (§10), and zeroizes per-session memory on teardown (§12).
Two spec hooks are load-bearing.
**(a) The GGUF container parser is attacker-facing**, a downloaded model is untrusted input, so its header/metadata/tensor-map decode is a §5 **verified copy-once parser** (Narcissus), *unlike* the browser's deliberately-contained content parsers, and it is authored fresh regardless of framework, since neither `burn` nor `candle` ships a distrust-hardened GGUF front end.
**(b) Timing.**
Dense-GEMM decode over a fixed model geometry is naturally data-independent (favorable for the §15 `Zkt`/`Zvkt` posture), but token-dependent sampling, KV-cache-length-dependent work, and any mixture-of-experts routing are genuine data-dependent channels; a session carrying secret-labeled prompts (§8/§13) therefore either scopes a constant-time obligation onto exactly those paths, or the flow theorems (§8, §13) must forbid secret material from reaching it.
No CUDA/GPU path exists (§15); throughput is the honest M-class envelope (§15 capacity honesty), not datacenter-class.

**Disposition:** adopt `burn` as the safe-Rust framework and write the M-class GEMM engine as a custom `burn` backend, the single net-new artifact, the systolic units having no existing backend, shedding `burn`'s training/autodiff; verify the GGUF parser (§5), route all matrix work through the M-class capability-operand movers (§15, no private DMA), and treat sampling/routing data-dependence as the residual to bound or label-fence.
`candle`/`mistral.rs` are the rejected re-target alternatives, GGUF-native but enum-baked backends, `mistral.rs` maximizing the very data-dependent surface (b).

### Network stack: the verified-wire network compartments

§12's network is not one program but a handful of contained compartments, the TCP/IP stack (**smoltcp**), the resolver (**hickory-dns**), the Roughtime client (**roughenough**), and TLS 1.3 (below), each retargeted onto the rings (§18) as Tier-1 servers.
Being neither GUI nor JIT hosts they clear obstacles 2 and 4 for free; what remains is obstacle 1, the `unsafe` in the packet-buffer and socket layers routes through the verified HAL (§5), and obstacle 3, the ambient BSD-socket/`connect` API becomes capability-delegated ring endpoints, the NIC reachable only by capability (§12).
What sets this target apart from the coreutils-shaped lifts is that **every one of these compartments faces the wire**, so the §5 Narcissus mandate is load-bearing rather than incidental: the TCP/IP headers, the DNS message grammar, the Roughtime request/response, and the TLS record/handshake framing are all attacker-controlled remote formats, so each is a **verified copy-once parser** (Narcissus), the class the radio L2/L3 parsers occupy, pointedly *unlike* Servo's deliberately-contained content parsers.

**TLS is the one compartment where a *verified protocol* is preferred, not merely a verified parser.**
The two formally-verified options rank by the project's own criteria (§5): the trust-base-uniform target is a Rust-native, **hax**-verified TLS (the **Bertie** lineage, Cryspen), it stays in the default Rust lane, its **hax**-extracted proofs can ride the single Coq prover (SSProve, already §5's crypto-reduction base), and its crypto is **libcrux**, already the §5 PQ interim; **miTLS** (Project Everest, F\*/Low\*) is the more mature option but rides F\*/Z3 and needs the Low\*→C lift.
Either way the protocol proof is *bonus* over the binary-level memory-safety floor every contained binary already carries (§13), never trust base, and the crypto binds to the §5 verified core rather than a bundled provider.

**Where no Coq-native verified peer exists, the resolver and the TCP stack, mature verified artifacts in *other* provers serve as differential-test oracles that enter no trust base**, exactly as §5's radio parsers cross-check against asn1scc and the Wireshark dissectors: **IRONSIDES** (SPARK/Ada verified DNS) for hickory-dns, and **AdaCore's** SPARK-verified TCP stack with Cambridge's **Huginn-TCP** conformance suite (Netsem-lineage) for smoltcp, cross-checking parse-correctness and protocol conformance on captured and fuzzed corpora (the deterministic-simulation-testing gate below).
Roughtime has no verified peer in any prover, so roughenough rides the Narcissus-parser-and-§5-crypto discipline alone.

**Disposition:** Tier-1, the crypto- and secret-touching compartments (TLS, the DNS-over-TLS path) carry the §13 constant-time and information-flow obligations, the packet plumbing is Tier-1 safe Rust; adopt smoltcp/hickory-dns/roughenough as start-froms, prefer the Bertie-lineage **hax**-verified TLS with **miTLS** the mature alternative, make every wire format a §5 Narcissus obligation, bind all crypto to the §5 core, and gate bring-up on the SPARK/HOL4 differential oracles (which never enter the trust base).

---

## Shared prerequisites

Both halves of the userland gate on the same handful of net-new artifacts, so they are sequenced behind them rather than each solving them privately:

- **The certifying Rust→RV64+CHERI toolchain (§18)** is the hard, no-fallback prerequisite for *building or admitting any of them*, userspace availability gates on it exactly as desktop instantiation gates on CHERI silicon (§18).
- **A software rendering/compositing library on V-class cores**, the substrate COSMIC's compositor, Zed's GPUI, and Servo's WebRender all collapse onto, is built once under the §12 display model and shared across the three GUI targets.
  Its interface is a dispatch of AOT-certified kernels over capability-scoped buffers rather than an emulated graphics API (obstacle 2), which is what makes the three backends re-targets of a known shape instead of three GPU stacks: each toolkit's shader set is fixed at build time, and each already has a backend seam to write against.
  It is needed earlier than any of them: the trusted-path agent and the rollback-manager UI (above) must draw before an application exists to consent about or a generation exists to roll back.
- **The WASI-shaped capability libc (§14)** and its manifest-backed namespace is the common on-ramp every source-level re-target compiles against.
- **The reference display server** (COSMIC's `cosmic-comp`, above) that the other GUI apps present surfaces to under per-surface / per-input capabilities (§12).

---

## Sequencing

Two gates order this work, not one.
The **software gate** is the prerequisites above: nothing exists before the certifying toolchain, and nothing with a surface exists before the render substrate.
The **hardware gate** is §18's own staging, which brings the die up class by class (C-class scalar with software rendering, then V-class, then M-class, then the FEC units), so a target cannot be *delivered* before the core class it runs on exists.
The two gates are not the same date: the golden model boots the whole stack at M6 of the [implementation plan](implementation-plan.md), functionally and slowly, long before any of it is deliverable, so the class order gates delivery rather than existence.

Stages, not a schedule: within a stage nothing is serialized, and each stage presupposes only the one before it.

1. **The spine**, arriving with the userland milestone (M5).
   Service manager, filesystem, block and storage servers, drivers, the radio L2/L3 servers, the network stack, sealing and attestation, the time service, the telemetry monitor.
   This is the minimum for a machine that boots, keeps state, knows the time, reaches a network, and can take a signed generation.
   The update path comes first among equals: a system that cannot be updated cannot safely be iterated on, so every later stage presupposes it.
2. **Consent and recovery.**
   The render substrate, and then its first two clients: the trusted-path agent and the rollback-manager UI, with the credential and unlock service beside them.
   The renderer's first client is the consent path, not the desktop.
   This is the stage that makes the earlier claim operational, since no application may hold a grant before the component that mints grants exists, and it is where recovery arrives, the machine now holding state worth rolling back.
3. **The headless applications.**
   coreutils, findutils and diffutils first as the seed corpus, then gitoxide and NuShell.
   They clear obstacles 2 and 4 for free, need no surface, and exercise §10's store and §12's rings harder than any GUI target will: gitoxide's re-homing onto the CoW B-tree is the sharpest test userland gives the storage stack.
   They are also the targets deterministic simulation testing can actually run (below).
4. **The desktop.**
   `cosmic-comp` as the reference display server, then the shell and applets above it, and with them the first real load on the media and translator graph: the image, font, and archive decoders a desktop cannot avoid, each a §5 Narcissus obligation rather than a lifted crate.
   An editor follows the compositor rather than preceding it, for want of a surface to draw on.
5. **Deferred by the specification itself.**
   §18 defers the **browser**, the largest porting program here and the one gated on a pure-interpreter JavaScript engine that does not yet exist.
   The **inference server** is optional in §12 and waits on M-class bring-up (M8).
   **Cellular** follows the Wi-Fi-only first release: the RRC/NAS compartments, the HARQ hard-real-time task class (§11), and the eUICC wait on FEC-unit bring-up and carrier certification.

**What would reorder this.**
The order is a consequence of exactly two things, the prerequisite with no fallback and the class order §18 fixes, so it moves only when one of those moves.
A target advances by shedding a gate, never by priority: an editor needing no surface would sit in stage 3 rather than stage 4, and an inference runtime targeting the V-class vector unit rather than the systolic array would not wait on M8.
Nothing here promises dates, and nothing here is a design cut: a later stage is later, not smaller.

---

## Deterministic simulation testing: catching what the certificate does not prove

The Tier-2 admission floor (§13) certifies *memory safety*, CHERI enforcing spatial bounds at runtime while the certificate discharges the temporal-safety, CFI, and no-runtime-codegen residual, and says nothing about *behavioral* correctness: gitoxide's delta resolution and merge, Servo's pure-interpreter event loop, `cosmic-comp`'s surface-to-input mediation, and Zed's language-server orchestration are all memory-safe-by-certificate yet logic-correct-by-nothing.
That un-proven behavioral space, the bugs no one thinks to write a test for, is where a **deterministic simulation testing** harness earns its keep in continuous integration, and the [golden-model implementation plan](implementation-plan.md) already supplies the one artifact such a harness is otherwise hardest to build: a **deterministic, full-system substrate**.
The Sail C-backend emulator is that substrate by construction, the CertiCoq→Wasm host-side reference is a second one for fast iteration, and the plan already leans on **differential testing against the Sail golden model** as its bring-up oracle, simulation testing is that same move made systematic: fault-injecting, coverage-guided, and replay-exact.
Four properties of the machine make it unusually amenable:

1. **The nondeterminism is designed out, not suppressed.**
   Static-only branch prediction with zero mutable predictor state, `Ztso` fixed ordering, no `LR`/`SC` reservation set, a static supervision tree in place of `fork`/`exec`, and the admission-test-3 rule that *no hidden state survives a partition switch* (§15) delete, at the ISA and OS level, the very nondeterminism sources a conventional simulator spends its effort papering over, so a replay is bit-exact and a failing schedule reproduces on the first attempt rather than as a flaky heisenbug.
2. **The specification is already the property oracle.**
   The invariants worth asserting are written down as theorems: the §8/§13 information-flow properties (no surface observes another's input, no secret reaches a data-dependent path), §10 RefFS linearizability ⋈ liveness, and §12 capability confinement.
   A run that violates one is a defect with a deterministic witness, not a symptom to be chased.
3. **Fault injection has native hooks.**
   Crash-consistency is exercised against §10's Perennial-verified journal crash semantics; toxic-wire robustness is exercised by fuzzing the §5 Narcissus decoders, gitoxide's pack/pkt-line/idx stream, the GGUF container header, and the network stack's DNS, TLS, and TCP/IP wire (cross-checked against the SPARK/HOL4 differential oracles), the empirical complement to the copy-once proof, aimed at exactly the attacker-facing surfaces that proof governs.
4. **The oracle is free and doubled.**
   The same workload runs on both golden models, CertiCoq→Wasm host-side ⋈ purecap-on-Sail, and any divergence between them is itself a defect; the safe-Rust targets additionally take source-level `cargo-fuzz` and property testing *before* re-target, upstream of the substrate entirely.

**Discipline:** this is a bring-up gate and a defense-in-depth net, never an axiom.
Simulation testing is *unsound*, it exhibits bugs, it does not prove their absence, so it occupies exactly the slot the specification reserves for mature-but-unsound tooling (Binsec/Rel for constant-time, riscv-formal BMC for refinement, aiT for WCET): path-bounded evidence that gates a pull request and accelerates the un-proven behavioral space, but that never enters the trust base and never stands in for a §13 obligation.
Its one structural advantage over that tooling is that the substrate it runs on is not an approximation of the target, the **RTL ⊑ Sail** refinement proves the silicon refines the very model the tests execute on, closing the "does the simulator match production?" gap that black-box simulation testing must always leave open.
