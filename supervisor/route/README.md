# Supervisor producer compatibility trial

**Decision: keep C as the M8a supervisor route.** The [source-bound result](result.json)
records the first failed predicate: the real node compiles through Vélus, but
its unchanged printed Clight is refused by the accepted purecap compiler before
assembly. Vélus places `_Alignas(8)` on the two `unsigned long long` epoch
parameters; the accepted C frontend reports alignment specified for parameters.
The native C compiler refuses the same declarations. No target image or
node-versus-oracle comparison was reached. This decides this bounded exchange
trial, not every possible Vélus route. No compiler port or printer rewrite was
introduced, and final Vélus delivery stays after M8a.

This is M6.1b-i's bounded experiment over the existing immutable M8a manifest,
supervisor effect interface and lifecycle comparison fixtures. Its source node
is a real start/restart planner for that manifest. It emits acceptance, the
ordered unit identifiers, stop membership, declared backoff and the storage
unit's epoch-filtered grant. It compares full-width epochs without incrementing
them. The node is a small producer probe, not the complete supervisor.

[oracle.c](oracle.c) obtains expected answers from the existing C planner and
checks each accepted request against its current-epoch consumer. Refused plans
must preserve the sentinel output fields before the harness normalizes them.
The input product covers initial start, restart and an invalid restart value;
the declared backoff steps and ceiling; full-width attempt counts; retired and
live storage edges; equal epochs and stale low/high epoch bits. The existing
`supervisor check` separately retains its full Gallina comparison and effect
execution controls. Those host checks supply no target effect verdict.

[probe.py](probe.py) turns the C answers into a target driver. It includes the
emitted Clight dump unchanged and accepts the actual printed interface names
explicitly. The same driver is compiled natively and by the accepted purecap
backend. Its negative control changes the first accepted count and must fail.
Compiler output, native binaries, assembly, images and build logs stay in the
assigned native lanes. None of the contained compiler implementation is copied
into these original sources.

## Reproduction inputs

Use Vélus revision `27ba860c2624ba232816591290c6c119b9ead88a` with its CompCert
gitlink `22c33b91d42c7df986c97b13b6cd630866a56494`. Read both selected license
files before use and preserve the [contained producer rule](../../THIRD-PARTY.md#vélus).
The experiment uses a private opam root with OCaml 4.14.2, Coq 8.20.1,
Menhir 20240715, ocamlbuild and ocamlgraph. Configure Vélus for `x86_64-linux`
with `-no-runtime-lib -no-standard-headers`; this producer emits the Clight
input, and its ordinary x86 assembly is not the purecap target.

Build the oracle using a native C compiler with the supervisor include directory,
`oracle.c`, `supervisor/src/supervisor.c` and `supervisor/src/manifest.c`. Save its
standard output as `fixtures.txt`. Run Vélus with `-nomain -lib -header -dclight`
on [start_restart.lus](start_restart.lus), setting `-o` to a path in the native
trial directory. Read the emitted header, then invoke `probe.py` with
`--fixtures`, `--emitted`, `--memory`, `--output`, `--step` and `--out` naming
those exact files and identifiers. Repeat with `--perturb` for the negative
control only after the unchanged positive compiles. For the recorded producer,
the memory type is `start_restart`, and both the output type and step function
are `fun$step$start_restart`. The positive's compiler refusal prevents the
negative control from supplying a target comparison verdict.

The accepted purecap compiler is supplied externally to `python tools/run.py
compiler-diff program`, with `--ccomp-arg=-fverifiedos-typed`, its actual
`-conf` configuration, the source-bound simulator and a native `--keep` directory.
Retain the JSON report and every source/ELF/trace identity. Rehash all frozen
inputs after execution; changed inputs need a fresh experiment.

## Integration boundary

The stock exposed handoff is printed Clight C consumed by the accepted backend's
C parser. Finite agreement across that handoff does not compose the Vélus and
purecap compiler correctness theorems or qualify a direct Clight-AST importer.
The original node and its interfaces contain no allocation, runtime collector
or target library body.

The complete producer still needs all detector/action, dwell, window, boot and
escalation decisions, the reviewed manifest source binding, and the lifecycle
effect phases. The current synchronous host effect callbacks are kernel-internal
interfaces, not additional principal invocations. Their real supervisor-to-kernel
transport and the composed start/fault/restart observations retain the roster
contract's separate acceptance. A passing small node supplies none of those
results and cannot move the supervisor roster row to executable.
