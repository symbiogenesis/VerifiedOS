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

The candidate therefore refuses at its tool precondition. No independent fixture,
capture, replay, observer implementation or Parser attempt has run. Q39 needs a
separately selected, identity-bound tool build with supported user-stack unwinding
before this qualification can start. This finding commissions no installation,
replacement binary, custom unwinder or locked-toolchain change. Q39's complete
qualification and Q43's genuine complete default reuse remain open.
