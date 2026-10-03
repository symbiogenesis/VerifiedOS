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

**Switch rewrite: target agreement.** M6.1b-iv's
[source-bound result](switch-result.json) repeats the target legs with a
[declared switch rewrite](#switch-rewrite-trial) applied to the normalizer's output.
The accepted typed route compiles the rewritten node. The unchanged probe, split
into 24 programs that fit `compiler-diff`'s text window, agrees with the C oracle
on all 576 rows natively and on target, and its perturbed program fails on target.
An authored control program carrying every declared switch shape agrees on all 576
of its seeded rows natively and on target. The trial passes. The M8a route stays C.

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
specifier is refused, as is another value or type, a group before a pointer
declarator, a group outside the printer's byte form, and input outside the form
`-nomain` printing takes: a file-scope object, a `main` function or `volatile`,
which only main-node compilation prints. Vélus ignores `-lib` under `-nomain`,
so no printed byte distinguishes `-nomain -lib` output and acceptance is
decided from those markers (F-476). Alignment-free input comes back
byte-identical, and a record lists every group removed or kept by line and
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
3 pass: every recorded tool and license hash matches, the node re-emits the
recorded Clight and header, and the unnormalized driver is still refused for
its alignment; the token comparison places the node's four removals in the step
function's parameter declarators and the control program's nineteen at
enumerated positions, with its five members kept; the normalizer refuses the
five authored variants and returns alignment-free input unchanged. In check 4
the reference comparison passes with 656 cases and 3,088 equalities and the
regenerated fixtures reproduce the recorded digest, and the probe's target leg
is the first failed clause. The perturbed probe's and the control driver's
outcomes were collected after that failure and are recorded apart from it.
Check 5 is not reached; a post-verdict rehash found every frozen identity
unchanged.

The switch-free control program compiles through the accepted typed route with
every erased position and its member alignment, so on that program the erasure
suffices for the frontend (F-474). Its 640-row driver agrees natively, but its
straight-line `main` compiles to 242,568 bytes of text, beyond the 32,768-byte
window below `compiler-diff`'s data section, and is refused at layout. The
unchanged probe has the same one-`main` form, and its size is unmeasured because
the switch refusal stops it first, so a repeat needs drivers that fit that
window (F-473). Vélus reports that it could not check semantic existence for
the control program; the node compiles without that warning (F-475).

The normalizer, token comparison and control generator here differ from the
frozen versions the result binds, the generator only by its lint repair. The
normalizer and comparison refuse a group before a pointer declarator at every
position, where the frozen normalizer erased one at parameter and return
positions, recording the pointee's type, and kept one as a structure member,
and the frozen comparison placed the parameter form as a parameter. Neither
trial program carries that form, and the route tests hold its refusal. The
result's `post_trial` section binds the repaired tools and an equivalence run:
on every trial input they write the frozen tools' products, reports and logs
byte for byte, the normalizer's records compared less the output path each run
names, and the frozen tools
reproduce the trial's recorded products, so `frozen_inputs` still names the
tools the trial ran. The same section lists the result's review amendments,
which add every run's argv from the trial's stage records and the oracle
binary's identity, and state that the clang and native compiler identities bind
their driver executables only and that the license reads rest on attestation.
`python tools/run.py typecheck` holds `tools/` only; the route tools are clean
under the repository's pinned ty and ruff configurations run directly over this
directory.

A pass would have decided only that the normalization carries the tested node
through the accepted compiler to target agreement. The failure decides that it
does not, at switch typing. Neither outcome composes a Vélus or purecap compiler
theorem (F-467), supplies a complete supervisor, lifecycle, transport or roster
result, or re-selects the M8a route.

To reproduce, check out the result's source revision, confirm the listed input
and tool hashes, and re-read both license files. Run the recorded Vélus
commands, then `normalize.py INPUT --out OUTPUT --record RECORD` on each printed
file and `token_compare.py` with `--step` for the node or `--control`. Emit the
drivers with `probe.py` over the normalized node and with
`control.py --seed 20260928 --count 640` over the normalized control program,
whose memory type is `control`, whose output type and step function are both
`fun$step$control`, and whose reset function is `fun$reset$control`. Compile
each driver natively, and pass each to `python3 tools/run.py compiler-diff
program` with M6.1b-i's compiler arguments, simulator and profile. The result
records each run's argv. The orchestration script that ran them is untracked
lane scratch, and its recorded hash postdates the verdict, so a reproduction is
checked against the bound driver, variant and product hashes. Every product
stays in the native lane.

## Switch rewrite trial

[switch_rewrite.py](switch_rewrite.py) is the exchange's second rewrite, applied
to the normalizer's output. Vélus turns an Obc `Switch` into a Clight `switch` at
one site, `translate_stmt` in `src/ObcToClight/Generation.v` (SHA-256
`0edb3ffad07e250fb84319d95666277a9eaa4033dca2c862f06a83bbd8dfce8d` at Vélus
`27ba860c`). That site writes one `case` for each present branch, in increasing
order, each ending in `break`, then a last `default` with no `break`; the Clight
printer `CompCert/cfrontend/PrintClight.ml` (SHA-256
`25a3f8489ae6444356262f3f4fc6f3bb1e3b3303f5fbf22ce0228c1cb25305db`) writes an
empty body as nothing. The rewrite declares five shapes of that layout, by case
count and empty bodies:

| Shape | Cases | Default |
| --- | --- | --- |
| `if-else` | one, non-empty | non-empty |
| `if-only` | one, non-empty | empty |
| `else-only` | one labelled 0, empty | non-empty |
| `chain-else` | two or more, non-empty | non-empty |
| `chain-only` | two or more, non-empty | empty |

Labels are decimal and strictly increase, and a body may hold further declared
switches. Each declared group becomes
`if ((E) == K1) {B1} else if ((E) == K2) {B2} ... else {D}`: every byte outside
the switch and every body's bytes are kept, and only the label and `break` text
between them is replaced. A Clight expression has no side effect and no body runs
between comparisons, so each evaluation of `E` reads one value, and the layout has
no fall-through, so the body whose label equals that value runs, or the default.
Every other `switch` is refused: one with no case, an empty case body outside
`else-only`, labels out of order or not in decimal, a `break` that does not end a
case, a label after the default, or a brace, label, conditional, `if`, loop,
`goto`, `continue` or `return` in a body. Input with no `switch` comes back
byte-identically. Vélus, its printer, the normalizer and the accepted compiler are
unchanged.

[switch_compare.py](switch_compare.py) checks a rewrite through clang's token
stream without reading the rewrite. It parses each normalized `switch` by its own
grammar, classifies its shape, and requires the rewritten stream to hold that
group's declared `if` chain and to equal the normalized stream elsewhere, token for
token and byte for byte outside the groups. Its control predicate also requires
every declared shape, a nested group and labels other than 0, 1, ... in order.
[switch_control.lus](switch_control.lus) is the control program that carries them;
its printed Clight holds eleven switches. [switch_control.py](switch_control.py)
generates its rows, 128 edge rows over every constructor and 32- and 64-bit edge
values followed by seeded rows, and computes their answers from its own reading of
the program. [split_probe.py](split_probe.py) splits the unchanged probe's
straight-line driver into programs of consecutive rows whose row blocks rejoin
into the driver byte for byte; the node has no memory, so no answer moves. The
control generator writes its programs the same way, each resetting the node and
each answered from that reset. The
[route tests](../../tools/tests/test_supervisor_switch.py) hold all four on an
authored fixture in the printer's layout. [switch_trial.py](switch_trial.py)
orchestrates the trial: `freeze` hashes itself, every frozen input and every tool
identity, `provision` prints and hashes both licence files as timestamped stages,
and `run` records each check clause as its own stage and stops after the first
failure.

The [result](switch-result.json) passes every check. The freeze at the authoring
commit `1f90ae78` hashed the script, 38 inputs and 15 tool identities, among them
clang's `libclang-cpp` and the native compiler's `cc1`. The trial finished 52 s
after provisioning, inside its two-hour bound:

1. Every identity M6.1b-iii's check 1 held matches, the opam switch export
   matches M6.1b-i's, the Vélus site and printer have the declared hashes, the node
   re-emits the recorded Clight and header, and the unnormalized driver is still
   refused natively and by the accepted compiler for its alignment.
2. The rewrite lowers the node's six switches, all `if-else`, three of them nested
   to depth three inside the delay group, and the control program's eleven, which
   carry every shape. `switch_compare.py` passes both, and fails a moved label and
   a changed statement. The rewrite refuses eight authored undeclared-shape
   variants of the node and writes nothing, and returns M6.1b-iii's normalized
   control program and both rewritten programs byte-identically.
3. Both rewritten programs compile through the accepted typed route.
4. The reference comparison passes with 656 cases and 3,088 equalities, and the
   regenerated fixtures reproduce the recorded digest. The probe's 24 programs of
   24 rows agree natively and through `compiler-diff program`, the largest at 8,956
   bytes of text against the 32,768-byte window. The perturbed program fails at its
   moved check natively and on target. The control program's 24 programs agree on
   its 576 rows, seed 20261002, natively and on target, the largest at 16,040 bytes.
5. Every frozen input and tool identity rehashes unchanged.

The checkout's `model/config/verifiedos.json` was reformatted after M6.1b-iii and
no longer has the recorded profile hash, so the simulator ran under that file's
bytes at M6.1b-iii's revision, written to the native lane; both read as the same
JSON value. The control program was fitted to the site's printed shapes before
provisioning, by running Vélus, the normalizer, the rewrite and the comparison in
the native authoring lane after a recorded licence read. The accepted compiler and
the simulator first ran after provisioning.

A pass decides only that the normalized and rewritten exchange carries the tested
node through the accepted compiler to target agreement. It composes no Vélus or
purecap compiler theorem (F-467), re-accepts nothing bound to the accepted
compiler and does not re-select the M8a route. A switch shape no declared rewrite
carries meets this rewrite's refusal rather than a compiler change.

To reproduce, check out `1f90ae78`, confirm the result's input and tool hashes,
write `model/config/verifiedos.json` as it stands at `d590c463`, whose hash the
result binds, to a native file, and run
`python3 switch_trial.py COMMAND --lane DIR --worktree CHECKOUT --revision SHA
--profile FILE` with `freeze`, `provision` and `run` in turn, `DIR` in the native
lane. The result binds by hash every stage record and report it cites, and their
retained copies keep them readable after the lane is retired.

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
