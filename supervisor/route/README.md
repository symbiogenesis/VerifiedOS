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

**Exchange repeat: refused at switch typing.** M6.1b-iii's
[source-bound result](exchange-result.json) repeats the exchange with the
[declared alignment erasure](#exchange-normalization-trial). The accepted
frontend reports no alignment error for the normalized node, but refuses it
before assembly: its typed scalar route does not implement Clight `switch`, and
Vélus prints the node's conditionals as six `switch` statements (F-472). The
probe still agrees with the C oracle on all 576 rows natively. No target image
or target comparison verdict exists for the node, and the M8a route stays C.

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

## Exchange normalization trial

[normalize.py](normalize.py) is the exchange normalizer. Vélus types every
64-bit integer with an explicit 8-byte alignment attribute, which the Clight
printer writes as ` _Alignas(8)` after `long long` or `unsigned long long`. The
normalizer removes that group, byte for byte, only where C11 forbids an
alignment specifier and Vélus's generation places one: parameter declarators in
prototypes, definitions and extern prototypes, `register` temporaries, function
return types and cast type names. The RV64 natural alignment of both types is
already 8. Structure members stay byte-identical. Every other alignment
specifier is refused, as is another value or type, a group outside the
printer's byte form, and input outside the form `-nomain` printing takes: a
file-scope object, a `main` function or `volatile`, which only main-node
compilation prints. Under `-nomain`, `-lib` changes no printed byte, so
acceptance is decided from those markers (F-476). Alignment-free input comes
back byte-identical, and a record lists every group removed or kept by line and
column. Vélus, its printer and the accepted compiler are unchanged.

[control.lus](control.lus) places a 64-bit alignment group at every erased
position and keeps five as structure members, one in its `fby` state and four in
its output. [control.py](control.py) generates its rows, 256 edge rows taking 0,
1, 2^32 and 2^64-1 in each 64-bit input followed by seeded rows up to the
requested count, computes their expected answers from its own reading of the
program, and emits the driver compiled natively and on target.
[token_compare.py](token_compare.py) checks a normalization through clang's
lexer without reading the normalizer: the normalized stream must be the printed
stream less whole `_Alignas ( 8 )` groups, and each group is placed by its own
bracket context. The [route tests](../../tools/tests/test_supervisor_route.py)
exercise all three on an authored fixture in the printer's layout.

The result records each check's predicate, interval and evidence. Checks 1 to
3 pass: every recorded tool and licence hash matches, the node re-emits the
recorded Clight and header, and the unnormalized driver is still refused for
its alignment; the token comparison places the node's four removals in the step
function's parameter declarators and the control program's nineteen at
enumerated positions, with its five members kept; the normalizer refuses the
five seeded variants and returns alignment-free input unchanged. In check 4 the
reference comparison passes with 656 cases and 3,088 equalities and the
regenerated fixtures reproduce the recorded digest, and the probe's target leg
is the first failed clause. Check 5 is not reached; a post-verdict rehash found
every frozen identity unchanged.

The switch-free control program compiles through the accepted typed route with
every erased position and its member alignment, so on that program the erasure
suffices for the frontend (F-474). Its 640-row driver agrees natively, but its
straight-line `main` compiles to 242,568 bytes of text, beyond the 32,768-byte
window below `compiler-diff`'s data section, and is refused at layout. The
unchanged probe has the same one-`main` form, so a repeat needs drivers that fit
that window (F-473). Vélus reports that it could not check semantic existence
for the control program; the node compiles without that warning (F-475).

A pass would have decided only that the normalization carries the tested node
through the accepted compiler to target agreement. The failure decides that it
does not, at switch typing. Neither outcome composes a Vélus or purecap compiler
theorem (F-467), supplies a complete supervisor, lifecycle, transport or roster
result, or re-selects the M8a route.

To reproduce, check out the result's source revision, confirm the listed input
and tool hashes, and re-read both licence files. Run the recorded Vélus
commands, then `normalize.py INPUT --out OUTPUT --record RECORD` on each printed
file and `token_compare.py` with `--step` for the node or `--control`. Emit the
drivers with `probe.py` over the normalized node and with
`control.py --seed 20260928 --count 640` over the normalized control program,
compile each natively, and pass each to `python3 tools/run.py compiler-diff
program` with M6.1b-i's compiler arguments, simulator and profile. Every product
stays in the native lane.

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
