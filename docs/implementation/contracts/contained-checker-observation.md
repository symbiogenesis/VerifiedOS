# Contained checker observation qualification

## Decision and scope

The first candidate for Q39's independent observation qualification used bounded
Linux `perf` sampling with DWARF user-stack unwinding. The
[parent-owned debugger candidate](#parent-owned-debugger-candidate) takes up the
unmet observation prerequisite. Both use unchanged locked checker and compiler
bytes. A real Parser diagnostic requires its own landed predicate. The
[locked capture review](../contained-compiler-port-decisions.md#capture-prerequisite-at-the-locked-checker)
owns the retained input basis and the limits of its buffered profile.

The claim being qualified is narrow: at a recorded sample time, recover an
independently known nested native call stack, distinguish that observation from
an event which completed earlier, and refuse an incomplete capture. A recovered
stack supplies neither compared terms nor a reduction, progress, termination or
kernel-acceptance verdict. Any later hypothesis requiring those facts returns to
Q39 for its own evidence and predicate.

Linux's [record documentation](https://github.com/torvalds/linux/blob/v6.18/tools/perf/Documentation/perf-record.txt)
defines user-stack recording with a selected byte bound and requires unwind
support to resolve that stack. Its
[script documentation](https://github.com/torvalds/linux/blob/v6.18/tools/perf/Documentation/perf-script.txt)
defines replay and explicit event-loss reporting. Merely accepting the
`--call-graph` option does not establish that a particular installed build can
unwind an OCaml stack.

## Preconditions and bindings

Before any capture or replay, retain the following exact identities in the
assigned lane. Missing or changed bindings refuse before capture.

- The public revision, independently reviewed observer/control sources, dedicated
  checkout, owner and native output directory under that lane's `lane_root`.
- The resolved `perf` executable, complete build-options output, version,
  ELF architecture and SHA-256, plus its actual unwind dependencies and their
  SHA-256 identities. Require an enabled supported DWARF unwinder and symbol
  resolution; an option spelling, header or debug section alone does not pass.
- The independent control's compiler, exact flags, source, executable and debug
  bytes. Native C and OCaml controls are separate: a C-only success does not
  qualify the locked checker's OCaml compilation convention. The latter control
  must use the selected locked OCaml toolchain and record its native-code/debug
  options. No compiler, prover or switch installation is part of this route.
- The kernel identity, architecture, requested event and clock, process identity,
  actual mappings and executable/debug identities used for symbolization. Use an
  owned child rather than a PID selected by name. A mapping from another process
  or a replacement executable refuses.
- Fresh explicit raw-capture, control-log, recorder-log and replay destinations.
  Refuse aliases to any input or existing useful capture. A replay binds the
  exact recorded bytes; it never refreshes expectations from a changed control.

The output and placement rules are the
[ordinary lane rules](../../../tools/README.md#where-a-file-lives-and-which-lane-touches-it).
Raw captures, logs and unwind work stay on native guest storage. Only explicit
metadata exports enter the checkout. No observer attaches to another worker,
modifies a shared tracing configuration or reuses the retained checker PID.

## Independent controls and acceptance

The controls execute no contained compiler or proof object. A synchronized
control first enters and returns from a named `completed` function, emits and
flushes a completion marker, then enters distinct non-tail nested `outer` and
`inner` functions. It emits and flushes an `inner-active` marker while both calls
remain live, and performs bounded CPU work while polling for the controller's
release, so that the selected CPU-clock event can sample that interval. Record
monotonic marker times in the same clock basis as the samples. Keep the original
marker bytes.
The controller knows the live nesting from the control protocol, independently
of the reconstructed stack and symbol names.

Acceptance requires all of the following on both native controls:

1. A complete run supplies at least one fully resolved sample during the
   independently delimited active interval, containing `inner` and `outer` in
   order. The earlier `completed` marker is classified as historical completion,
   and no sampled frame or absent sample is converted into a function-return
   event. An unresolved frame, insufficient stack extent, missing active-interval
   sample or unsupported OCaml unwind convention refuses that claim.
2. An owned-child interruption during the active interval retains the raw
   capture and marker prefix, actual signal, observed recorder/child exits and
   cleanup result. It labels the run interrupted and never inserts the missing
   `inner`/`outer` completion markers or a successful proof outcome. A stack at a
   prior sample is labeled with that sample's time, never as a stack at exit.
3. Replaying a deliberately truncated copy refuses complete-capture acceptance,
   preserving the original raw bytes and their digest. Malformed records,
   reported lost records, inconsistent mappings, changed control/debug bytes,
   PID substitution and recorder/replay failure also refuse; any readable prefix
   remains explicitly partial evidence.
4. The controller rechecks all input/output identities before returning, reports
   the executed scopes and confirms that every child it created has exited.
   A successful control qualifies only this exact observer/toolchain tuple.

Use the software user CPU-clock event at 49 samples per second, a 16 KiB
user-stack record limit and a private 64-page ring. Each capture has a two-second
wall cap, each replay a ten-second cap, and the entire independent qualification
a sixty-second cap. Limit each process to 512 MiB address space, three CPU seconds
and 16 MiB output files; keep capture output under the same total byte limit.
The controller sends SIGINT only to its owned process group at its capture cap,
allows one second for exit, then uses SIGKILL on surviving owned children and
reaps them. Reaching any cap refuses acceptance and preserves the prefix. A
missing sample or failed unwind ends the candidate rather than extending its
limits, changing compilation options or attempting the real Parser.

These limits apply to small independent controls only. They select no checker
diagnostic duration, memory budget or renewed attempt allowance. Before any real
operation, Q39 must review the control evidence, justify that it transfers to the
selected checker's compilation convention and land that operation's exact
hypothesis, complete input ledger, resource cap and stopping rule under the
[continuation handoff](contained-compiler-reuse.md#continuation-from-an-isolated-public-lane).

## Current tool prerequisite

The 2026-11-09 read-only native preflight verifies that the retained checker's
SHA-256 agrees with the
[original binding manifest](../retained-evidence/q39/bounded-parser-profile-20261013/bindings.json.gz).
Its ELF is native AArch64 PIE and retains debug information. This establishes
input availability only; the executable was never launched.

The installed `perf` identifies itself as
`6.18.54.1.g26d1ceb55087`, SHA-256
`160daabc3ff14c60e4b9de2bc932ae5aebd2e5fd842e8f5683b2f9f493e92297`.
Its own `version --build-options` output marks `dwarf`, `dwarf-unwind`,
`libdw-dwarf-unwind`, `libunwind` and `libelf` off. `gdb`, `lldb` and `eu-stack`
are absent from the root toolchain user's command search. The assigned lane's
`out/evidence/q39-observation-preflight.json` retains raw commands, outputs,
identities and the refusal; the fan-out handoff retains that output on retirement.

The installed candidate therefore refuses at its tool precondition. The private
distribution candidate below has passed acquisition and ELF/dependency preflight
without replacing the installed binary. Its single bounded independent attempt
refuses opening the prescribed event before control activation, as the outcome
below records. No stack-observation qualification or Parser attempt is accepted.
Q39's complete qualification and Q43's genuine complete default reuse remain open.

## Private distribution-tool prerequisite

Select Ubuntu's `linux-perf` **7.0.0-43.43**, from
`http://archive.ubuntu.com/ubuntu`, `resolute-updates/main`, architecture `arm64`.
The restored guest is Ubuntu 26.04 AArch64. This candidate uses distribution-built
DWARF support rather than rebuilding the installed WSL tool, and does not assume
that a newer userspace tool is compatible with the running WSL kernel. Its actual
event support, unwind conventions and record/replay tuple must pass the existing
independent qualification; option or dependency presence alone supplies no pass.

The frozen acquisition population is:

| Package | Version | Architecture | Archive SHA-256 |
| --- | --- | --- | --- |
| `linux-perf` | `7.0.0-43.43` | `arm64` | `305d46274edd7f1598c8b728f90954c576067c2f5c897b3cb3bca031c41b7aff` |
| `libdw1t64` | `0.194-4` | `arm64` | `8f81bc569e72acd97197890fa34e6a91fe601a6d1632d99bc4569791a25c4724` |
| `libdebuginfod1t64` | `0.194-4` | `arm64` | `536f23845ba4a4b671c3e61a14e6aacfc511b0e4fac4ecd81c7e0215259a06bb` |
| `libdebuginfod-common` | `0.194-4` | `all` | `151b5cfce8702069ef2caaa09bba3af4e28415fcb87bc948465747a370402b0b` |
| `libnuma1` | `2.0.19-1build1` | `arm64` | `166bdafa785118f4a1466540fe4abcbba055210c5c31057cdb53c6b76bffda3e` |
| `libtraceevent1` | `1:1.8.7-1` | `arm64` | `32f50510f8c524795a7e555a1fcce7bb81d0f2f13e0aa5ee7234e7e294af0fdb` |

These pins are a selected candidate population, not installed dependencies or a
qualification verdict. `linux-perf` is from source package `linux`; the three
`libdw`/`libdebuginfod` packages are from `elfutils`; the remaining source packages
are `numactl` and `libtraceevent`. The library/configuration packages are from
`resolute/main`. Retain the complete package stanzas, including declared dependency
relations, relative archive paths, lengths and digests, in the lane's native
selection evidence. Record which declared dependencies are already installed,
their exact versions and the actual dynamic-library closure. A missing or
incompatible dependency refuses this candidate; it does not authorize a floating
package selection, shared installation or compiler/prover change.

The 2026-11-09 metadata reading verifies both local `InRelease` signatures against
the existing Ubuntu archive keyring, with signing fingerprint
`F6ECB3762474EDA9D21B7022871920D1991BC93C`, and compares each exact uncompressed
`main/binary-arm64/Packages` file's length and SHA-256 with its signed entry:

| Suite | `InRelease` SHA-256 | `Packages` SHA-256 |
| --- | --- | --- |
| `resolute` | `45f95ce276cdba3e41870516a130e03c58b8b7a79e9546b0efe9e526d255740c` | `f1139a214af70f615388f8d4b377f591767bb52e45adb133679479c27a4dde8c` |
| `resolute-updates` | `f100a1a2f57a39b2f67a7f34219a462c474d4c275b456a94c2d5f1bccf077f25` | `fa9f96b0fad1d520fee0d545183e30d8ae051381101bc08e44b0bd1188525db3` |

Retain the keyring identity, raw signature-verification output, signed metadata
and matching package stanzas. If acquisition uses a compressed index, retain its
own exact bytes and verify its distinct signed digest before decompression, then
verify the uncompressed digest above. No compressed index was read in this
selection. A signature on one release cannot authenticate an unrelated cached
package listing. These retained indices identify the candidate; they make no
claim about repository freshness after the reading.

Acquisition and use have the following ordered acceptance predicate:

1. Land this prerequisite before acquisition beyond license-only inspection.
   Download only the frozen archives into a fresh directory under the assigned
   native lane; require their complete signed-index lengths and SHA-256 values.
   Bound each archive at 16 MiB, the population at 32 MiB and each network request
   at fifteen seconds. A timeout, unavailable archive or identity mismatch refuses
   without substituting another version or executing any fetched bytes.
2. Inspect each archive's own copyright/license population as data and retain
   its exact member paths, bytes and digests. Record the selected releases'
   actual terms and local diagnostic use in [THIRD-PARTY.md](../../../THIRD-PARTY.md)
   before executable adoption. No package source, executable, library or debugger
   data is distributed in the tracked repository. The package name or Linux
   lineage supplies no license inference. An unread or incompatible term stops
   adoption; license-only inspection grants no permission to run the candidate.
3. Extract only into a fresh private native lane root, after checking archive
   entries for containment and refusing escaping links or special files. Never
   run package maintainer scripts, register packages, alter `PATH`, replace the
   installed `perf`, write a system configuration or install shell hooks. Retain
   the package-declared configuration as data; do not activate
   `libdebuginfod-common`'s shell integration. Use explicit executable/library
   paths and child-only environment settings, with `DEBUGINFOD_URLS` empty and
   no symbol downloads. The current inherited system/profile environment remains
   unchanged.
4. Bind the selected ELF, its loader and the full resolved dynamic-library
   population, with real paths, architecture, versions and SHA-256 identities.
   Retain complete build-options/version output and require an enabled supported
   DWARF unwinder, ELF support and symbol resolution. Record its distinct tuple
   rather than inheriting evidence from the installed WSL `perf`. Revalidate the
   tuple before and after each use; substitution or a missing library refuses.
5. Only then implement and run the existing independent C and locked-OCaml
   controls, preserving their sixty-second combined cap and every completion,
   interruption, truncation, mapping and byte-identity refusal above. No real
   checker or proof object enters that population. A failed event, unwind or
   convention check rejects the candidate without changing the locked toolchain,
   extending a cap or attempting Parser.

Selection closes only the missing tool-choice decision. Acquisition, license
reading, private ELF/dependency validation and independent observer qualification
each retain their own verdict. A future real diagnostic still needs its separate
landed hypothesis, complete inputs, resource cap and stopping rule; this route
authorizes none of Q39's complete compiler qualification or Q43's complete reuse.

## Candidate qualification outcome

The frozen archives were obtained from the official
`https://ports.ubuntu.com/ubuntu-ports/` mirror after the primary archive request
timed out. Their complete lengths and SHA-256 values match the selected signed
indices. Their own copyright files were read before executable adoption, with
the intended local diagnostic use recorded in [THIRD-PARTY.md](../../../THIRD-PARTY.md).
Private extraction ran no maintainer scripts and changed no installed package,
tool, shell configuration or kernel setting.

The extracted AArch64 ELF identifies itself as `perf 7.0.14`, SHA-256
`b9dd15e9fff1f0efbacbcb541ac3f2d8a597f902e4c2e610e8e288f2e7a7be4e`.
Its complete build-options output enables `dwarf`, `dwarf-unwind`,
`libdw-dwarf-unwind` and `libelf`. The native preflight binds its loader and
resolved dynamic-library population by actual path and SHA-256, with child-only
library paths and debuginfod disabled. This passes the acquisition and
ELF/dependency preconditions, not the event or stack-observation predicate.

The independently reviewed controller and C/OCaml source identities are retained
with the attempt. The C control and clock stub compile under strict native C17;
the OCaml control compiles natively with debug information under the selected
historical `q39-port` OCaml 4.14.2. Its compiler has CFI support and no frame
pointers. The experiment records that convention explicitly; transfer to the
selected checker's exact optimization/debug settings, or to the current tracked
compiler lock, remains unqualified.

The one bounded attempt refuses before the C control's activation. On kernel
`6.18.54.1-microsoft-standard-WSL2`, the selected recorder exits 255 opening the
prescribed `cpu-clock:u`, which its diagnostic renders as `cpu-clock:uH`:
`PMU Hardware doesn't support sampling/overflow-interrupts`, followed by
`Failure to open any events for recording.` The only control marker is `ready`.
Cleanup sends SIGINT to that owned child, observes its actual exit at -2, reaps
both child and recorder, and observes both owned process groups empty. All bound
inputs remain unchanged; the raw record is empty.

No OCaml control execution, active-interval sample, replay, active-interval
interruption or truncation control ran. Malformed-record, lost-record,
mapping-consistency, changed-control/debug-byte, PID-substitution and
recorder/replay-failure fixtures also remain unrun. Cleanup after the opening
failure supplies no active-interruption qualification. The candidate is rejected
at this event/tool/kernel tuple; kernel-wide sampling support remains undecided.
No second capture, event substitution, setting change or real checker operation
is authorized by this outcome.

The checkout export `out/evidence/q39-observer-tool-attempt.json`, SHA-256
`f8291433168fb883aa379664b7e106be6a97d18743a2c5044fbb763e395b2086`,
binds selected packages, signed indices, own-license file identities, the native
preflight and exact reviewed experimental sources. It contains metadata only;
external license texts, tool/library bytes, complete sources and raw outputs stay
in the native lane for the local fan-out's retention. The native qualification
report has SHA-256
`1b24692a47b417c4bd571d0db1884f0635114240b17f50643b7408fed553d852`;
the empty record has SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
These records supply no compiler/kernel qualification, accepted observation
adapter or Q39/Q43 completion. A different compatible observation tuple requires
its own selected prerequisite and independently reviewed bounded predicate.

## Parent-owned debugger candidate

Use GDB/MI on AArch64 to start and interrupt its own inferior. This route
depends on native parent tracing and debug unwinding. The restored guest reports
`6.18.58.1-microsoft-standard-WSL2` and has no installed GDB. Read-only ELF
inspection finds unwind information, debug information and a symbol table in
the retained checker. The retained `q39-port` switch provides the historical
native OCaml compiler. Section presence alone establishes no unwind verdict.

The target distinction is conversion under declaration-type inference, body
inference or final comparison, or during module checking or subtyping. The
historical sample already finds closure conversion under structure-field
checking. All four whole audits proceed past the same lemma name in generic
module contexts and end at its concrete Parser occurrence. The locked checker
uses distinct phase call sites. A later diagnostic must bind the live caller's
source site and the declaration or module identity independently of the
conversion function name. The checker sends its declaration-entry notice through
a synchronous console feeder with a formatter flush. Before using that notice,
bind the installed implementation and require a complete drained record from
the stopped inferior and a matching live frame past the emission site. An
unresolved frame or site, ambiguous phase or unbound name yields an unresolved
observation. Repeated snapshots give no compared terms, cause or progress bound.
[Declaration checking](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/mod_checking.ml#L51-L103)
[Module checking](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/mod_checking.ml#L262-L328)
[Checker feedback setup](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/coqchk_main.ml#L435-L440)
[Feedback implementation](https://ocaml.org/u/4ab63f3d84e8baf8c600d4361ecf7619/rocq-runtime/9.3.0/src/rocq-runtime.lib/feedback.ml.html)
[Retained audit logs](../retained-evidence/q39/pending-audits-20261012/README.md)

The retained checker's static call-site map distinguishes type inference, body
inference and final comparison. The body inference path inlines a wrapper from
`typeops.ml`, so the displayed file for a caller PC can differ from
`mod_checking.ml`. Use the exact installed source and emitted call instruction
with the PIE load bias and return-address convention. The source tag alone
cannot resolve that caller site. The installed feedback source confirms
synchronous feeder dispatch and an explicit console formatter flush. The
executable and both installed source hashes match the
[retained bindings](../retained-evidence/q39/bounded-parser-profile-20261013/bindings.json.gz).
This verifies the static discriminator. Live frame recovery remains a separate
check.

### Private debugger acquisition

Select the following `resolute/main` archives. The cached `InRelease`, SHA-256
`45f95ce276cdba3e41870516a130e03c58b8b7a79e9546b0efe9e526d255740c`,
verifies with the Ubuntu archive signing fingerprint
`F6ECB3762474EDA9D21B7022871920D1991BC93C`. The signed entry binds a
7,533,190-byte `main/binary-arm64/Packages` index with SHA-256
`f1139a214af70f615388f8d4b377f591767bb52e45adb133679479c27a4dde8c`.
The local uncompressed index matches. Simulated dependency resolution with
recommendations disabled selected this population without upgrades or removals.

| Package | Version | Architecture | Archive SHA-256 |
| --- | --- | --- | --- |
| `gdb` | `17.1-2ubuntu1` | `arm64` | `d9191045754c9908eb18e7ef972b27cacae3ddc3f39e635c5514a18a64a2da42` |
| `libbabeltrace1` | `1.5.11-5build1` | `arm64` | `ee23d538a5afa4fc5b05d0f8f06ef3da7df53a407c3a017f8f00b20f9733c81b` |
| `libdebuginfod-common` | `0.194-4` | `all` | `151b5cfce8702069ef2caaa09bba3af4e28415fcb87bc948465747a370402b0b` |
| `libdebuginfod1t64` | `0.194-4` | `arm64` | `536f23845ba4a4b671c3e61a14e6aacfc511b0e4fac4ecd81c7e0215259a06bb` |
| `libdw1t64` | `0.194-4` | `arm64` | `8f81bc569e72acd97197890fa34e6a91fe601a6d1632d99bc4569791a25c4724` |
| `libsource-highlight-common` | `3.1.9-4.3build2` | `all` | `9208a5cb2e873ae7bcc458f13d51aaec29a04c563df926cad9145af8a4234bf4` |
| `libsource-highlight4t64` | `3.1.9-4.3build2` | `arm64` | `017ea387e6210acb241a2dce2fed2da3d7ba7780ea48a440989ee610ecaf1d38` |

Reverify the signature and exact index before acquiring only these archives at
the signed relative paths from the archive or official ports mirror. Use the
[prior acquisition procedure](#private-distribution-tool-prerequisite) for
download bounds, exact lengths, own-license reading, contained extraction and
ELF/dependency binding. Record each archive's actual terms and intended use in
[THIRD-PARTY.md](../../../THIRD-PARTY.md) before adopting executable bytes. Bind
GDB's version, build configuration, interpreter, actual library closure and
data path. Use explicit paths and child-only settings. Disable startup scripts,
automatic script loading, symbol downloads, inferior shell startup and
debugger-induced randomization changes. Keep archives, binaries and extracted
files in the assigned native lane. [GDB auto-loading](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Auto_002dloading.html)

### Independent debugger controls

The cheapest refusal after acquisition is a single launch and interrupt of a
tiny owned C child. Require a genuine asynchronous all-stop event for that
inferior. An opening failure ends the tuple. Then qualify C and native OCaml
separately. In each language the positive cases mark completion of an earlier
operation and exercise two distinguishable phases that call the same non-tail
nested work. Each active interval is delimited by control markers independent
of GDB, with completion emitted only after returning. Use the historical locked
OCaml compiler with exact native and debug flags.

Start each phase in a fresh inferior. Bind its PID, the stopped thread, source,
ELF, mappings and debug bytes. Verify asynchronous execution support. Keep the
raw MI stream and inferior console separately, including a control that prints
MI-like text to its own console. Read frames after the matching asynchronous
stop, following the independently flushed active marker. Require the inner then
outer frames and the correct phase's caller site even when the nested frames
are identical across phases. Require actual resumption, completion markers and
normal exit on the completion case. On a separate interruption case, retain
the stop, actual exit signal and surviving marker prefix. Check that all owned
children have exited. Never synthesize completion. [GDB/MI execution](https://sourceware.org/gdb/current/onlinedocs/gdb.html/GDB_002fMI-Program-Execution.html)
[GDB/MI stack inspection](https://sourceware.org/gdb/current/onlinedocs/gdb.html/GDB_002fMI-Stack-Manipulation.html)

Replay the raw evidence and reject a deliberately truncated copy, wrong phase,
unresolved frame, missing or duplicate stop, PID or mapping substitution, byte
drift and unexpected debugger or inferior exits. Preserve a failed capture and
its actual verdict. Recheck bound identities before returning. Allow one
three-second wall window per capture, ten seconds per replay, sixty seconds for
the entire qualification, 512 MiB address space per process and 16 MiB total
output. On timeout terminate and reap only the recorded owned processes, with
one second for graceful cleanup before forced termination. Reaching a limit
refuses the candidate.

These control limits authorize no real Parser run. Land that operation's own
hypothesis, sealed inputs, source-site and name correlation, resource caps and
stopping rule after the independent controls pass. Q39's whole-environment
qualification and Q43's complete-tier default reuse retain their predicates.

### Restored guest opening checkpoint

The Ubuntu ports mirror supplied the complete selected archive population. The
acquisition report, SHA-256
`1df72009a25beb413e92a96c1317a86009e7a0a27209de3ed5c1b7884478805e`, binds the
signed index, exact package bytes and own-license notices. The
[license record](../../../THIRD-PARTY.md#contained-compiler-observer) landed
before private extraction and executable use. The ELF preflight report,
SHA-256 `f143096257663f61e49ee2c28b57393d9db45b593631c57508052693172c0449`,
binds GDB 17.1, the explicit AArch64 loader, debugger data and actual shared
objects. The first entry review refused a relative dangling documentation
link within the private root before extraction. The containment review then
accepted the link with its original relative target and kept the complete
extraction private. GDB's bound version and configuration invocations passed.

The strict C17 opening control compiled and its isolated parser fixtures refused
stale, duplicate and missing stop records. The single live opening used the
bound debugger on the restored WSL kernel. GDB accepted the asynchronous MI
settings and reported creation of the owned inferior. It then reported an
internal fatal error and `error creating backtrace: mmap: 12` and exited at
`-11`. The controller observed no active marker, interrupt acknowledgment,
stop or frames. It confirmed the PID-bound inferior was reaped and rechecked
unchanged input identities. The inferior's exit status was unavailable.

The opening report, SHA-256
`c47dc33ce841cc05e9234819c23f3c089fc6600f223e3cabccb91007fa0967b7`, and raw MI,
stderr and console streams remain in the restored distribution, indexed by the
`q39-observer-20261124` fan-out's native retention receipt. This refuses the
tested startup tuple. The failure leaves the cause, parent tracing support and
OCaml unwind behavior unresolved. A revised preflight must address the startup
failure under its own bounded predicate. The two-phase controls and real Parser
operation have no verdict.
