# Contained checker observation qualification

## Decision and scope

The selected candidate for Q39's independent observation qualification is bounded
Linux `perf` sampling with DWARF user-stack unwinding, with the explicit tool
prerequisite below. It changes no locked checker or compiler
bytes and performs no proof repair. No real Parser diagnostic is authorized by
this contract. The
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
