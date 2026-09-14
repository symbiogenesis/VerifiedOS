# Standard certificates for static memory planning

This optional host path uses the existing LRAT ecosystem. CaDiCaL searches a
bounded Boolean encoding and produces a binary LRAT certificate; the upstream
`lrat_isa` checker decides whether that certificate refutes the encoded formula.
An ordinary placement independently passes the
[portable checker](../../tools/vos/memory_planner.py) before optional work starts.
An invalid certificate or exhausted budget preserves that checked feasible
placement and leaves optimality unknown.

This is evidence-producing research under
[R-05-011b and R-15-094](../requirements-register.md), outside the admitted
VerifiedOS production toolchain. **Its acceptance criterion is that no native
checker verdict or receipt is the ground of a refinement claim or an admitted
optimality or infeasibility verdict.** R-05-016, R-05-020, R-05-065, R-05-066 and
R-05-104 through R-05-106 remain unchanged. The experiment does not reopen
[Q27a](implementation-checklist.md)'s certified-search disposition, admit its
refused checker arm, supply the kernel-rechecked term R-05-015 requires, or close
Q5b's actual-workload comparison. The
[implementation](../../tools/vos/memory_planner_certificates.py) contains no Python
LRAT checker.

Every query identity and receipt carries fixed fields identifying the portable
experiment evidence tier, `grounds_refinement: false`, `admitted_verdict: false`
and `instance_lrat_replayed_by_rocq: false`. Receipt replay refuses absent or
altered fields. Within this scope, `checked optimal` and `checked infeasible`
describe results for the supplied finite model under the stated implementation
and native execution assumptions; they are never admitted VerifiedOS verdicts.

## Selected upstreams and trust endpoint

[certificates.json](../../tools/memory-planner/certificates.json) pins both source
revisions and records the MIT licenses read before incorporation. Upstream source,
native builds, CNF files, certificates, logs and receipts live beneath the active
lane's `/root/build` directory. No upstream source is vendored into this repository.

The [selected checker](https://github.com/lammich/lrat_isa/tree/99b832b501f473f7890f20b99755b5ace86eae48)
comes from an Isabelle/HOL development whose documented endpoint includes DIMACS
parsing and the exported LLVM implementation. Its
[MIT license](https://github.com/lammich/lrat_isa/blob/99b832b501f473f7890f20b99755b5ace86eae48/LICENSE)
and the exact LLVM/support-file hashes are in the manifest. This integration
compiles that unchanged LLVM with an
[authored I/O wrapper](../../tools/memory-planner/certificates/checker_main.cpp).
The wrapper reads bytes and invokes the upstream checker. It supplies no logical
checking rules. It replaces the upstream Boost-based command wrapper so the
optional path needs no system Boost installation.

The source theorem is not replayed in Isabelle here. The authored wrapper, C/C++
runtime, native compiler, linker and ARM target override are outside that theorem.
The recorded binary hash identifies the executable actually used; it does not
turn native compilation into a machine-code proof. The wrapper accepts only the
checker's Boolean success result, while Python additionally requires exit success
and exactly `s VERIFIED UNSAT` as the complete output.

[CaDiCaL](https://github.com/arminbiere/cadical/tree/c60730422e758ef1cebe7aeddf2dda31c996bf04)
is an untrusted producer under its own
[MIT license](https://github.com/arminbiere/cadical/blob/c60730422e758ef1cebe7aeddf2dda31c996bf04/LICENSE).
Its UNSAT status alone proves nothing. A SAT model is decoded and checked against
the original portable instance; a valid smaller placement refutes the proposed
optimality claim. The selected `lrat_isa` path consumes binary LRAT/LRUP, so the
producer's binary mode remains enabled. ASCII LRAT is not silently converted.

## Encoding and the two necessary directions

`encode` preserves fixed byte sizes, nonnegative aligned offsets, half-open live
interval unions, explicit conflicts, allowed pools, fixed locations, reservations
and direct alias views from the portable model. Unsupported core shapes are
refused by its existing parser. Input dictionary order does not change the pool
limit binding; buffer order continues to identify ordinary output rows.

Each buffer receives a finite domain of legal pool/offset choices. A domain
includes every aligned position satisfying its unary constraints; reservations
remove positions, and fixed offsets restrict a domain to a singleton. Each choice
gets one Boolean variable. A positive clause requires at least one choice and
negative pair clauses require at most one. Further negative clauses exclude
overlapping coexisting allocations and inconsistent direct alias relations.

The objective is the sum of pool extents in bytes, including reserved regions and
alignment holes. A zero-size buffer charges no extent but retains its full legal
address domain through the physical pool capacity, even when an objective bound
is smaller. This is the core metric, not a claim about another adapter's ordinary
height convention, committed pages or process residency.

For an objective query, a final choice group contains pool-height vectors whose
sum meets the bound. Each pool's possible heights are its reserved end or a
positive buffer end. These values contain the exact height of every legal layout.
Negative clauses require each selected positive extent to fit the chosen height
vector. A candidate of cost `H` asks whether any legal layout has total cost at
most `H - 1`. Default pool limits are the full input capacities; callers can state
stricter limits explicitly, which narrows the optimality claim.

The two directions have different jobs:

- A satisfying Boolean assignment selects one position per buffer, respects all
  forbidden pairs, and fits the chosen height vector. Decoding still invokes the
  independent placement checker and recomputes the actual objective.
- Every legal layout meeting the bound can select its actual positions and actual
  pool-height vector. Therefore an UNSAT refutation excludes every such layout;
  no domain may be truncated merely to make the Boolean instance small.

[MemoryPlannerCertificates.v](../../proofs/MemoryPlannerCertificates.v) proves
`finite_encoding_equivalent` for the finite one-hot constraint model in both
directions. `unsat_excludes_every_legal_selection` uses the completeness direction.
The physical optimum corollary explicitly requires coverage of every better legal
layout. The file does not prove Python domain extraction, DIMACS numbering and
serialization, or the connection between physical executions and supplied
lifetimes. Truth-table and placement tests check those finite implementation
boundaries; they do not replace the missing refinement theorem.
No LRAT certificate from an individual planning run becomes a Rocq proof term.
The generic finite-model theorem and the native checker's acceptance remain
separate artifacts, with no mechanically checked bridge between them.

## Commands and bounded failure

```console
python tools/run.py memory-certificates setup --json
python tools/run.py memory-certificates demo --json
python tools/run.py memory-certificates encode --instance instance.json --candidate candidate.json --dimacs
python tools/run.py memory-certificates certify --instance instance.json --candidate candidate.json --json
python tools/run.py memory-certificates verify --instance instance.json --evidence receipt.json --json
python tools/run.py memory-certificates proof --json
```

`encode` can run on the host. Native commands use the repository's guest hop and
write only the lane's native output directory. `certify` without a candidate asks
whether the supplied pool capacities are feasible. `--lrat` supplies a certificate
from another producer while retaining the same regenerated encoding and checker.
`--pool-limits` supplies a JSON object containing every pool's explicit limit.

Finite domain cardinality, variable count, clause count and encoding work each
have checked limits. The pool-height Cartesian product is bounded before it is
materialized. Exceeding a limit returns no partial CNF and supplies no
infeasibility claim. Native work has an explicit conflict budget, process memory
limit, certificate/log file-size limits, CPU limit and wall-clock deadline.
Wall time can end a run with unknown status; it cannot select a new optimality
claim. Source domains and ordinary placements remain immutable snapshots.

Receipts bind the canonical instance, literal objective and pool limits, encoding,
DIMACS bytes, LRAT bytes, checker inputs, authored wrapper, implementation sources
and compiled executables. Every use rechecks the pinned checker sources and build
receipt. Replay rejects changed scope, checker acceptance metadata, endpoint or
native build provenance, then regenerates the objective and complete formula
instead of trusting a receipt's CNF path. It reruns the native LRAT checker; it
does not replay that certificate in Rocq. Rejected proof, changed input,
unsupported size, failed producer and timeout all retain a previously checked
feasible candidate.

The CLI rejects duplicate object keys, nonfinite numbers and numeric overflow in
instance, candidate, pool-limit and receipt JSON. Its JSON output and saved
certificate receipt record hashes of the exact external bytes parsed. These
source-byte identities are provenance alongside the normalized instance binding:
whitespace can change the former without changing the latter. Replay records its
current input files and rechecks the encoded claim; it does not authenticate the
historical author or reread every original source pathname. An explicit `null`
candidate or pool-limit file is refused rather than changing the query's meaning.

The native demo verifies an optimum, rejects a corrupt certificate, obtains a
checked smaller layout for a false optimum, and replays its saved valid proof.
It reports synthetic finite-model evidence rather than a framework workload or
target timing measurement. The focused Rocq command compiles and kernel-rechecks
only the generic finite-model file; its result explicitly records that no
instance LRAT certificate was replayed. The integrator still owns the complete
proof audit.

## Literature disposition

The review's LRAT entry supplies the selected standard format; the upstream
Isabelle checker supplies the concrete LLVM acceptance endpoint. The finite
encoding-equivalence work adopts the review's model-reformulation lesson without
claiming to import LeanCSP or an unrelated theorem into Rocq.

DRCP/FznDrcpCheck and VeriPB/CakePB remain alternative certificate backends. Their
constraint languages, proofs and compiled runtimes are separate integration
boundaries; installing them alongside a working LRAT route would not discharge a
new static-placement obligation. PBLean, SMTCoq, cvc5/Alethe and streaming Lean
LRAT import similarly require a different importer or proof-assistant endpoint.
They are not presented as implemented dependencies.

SCIP exact search, pseudo-Boolean dynamic-programming proof logging and certified
coloring may become useful producers for larger or structurally restricted
instances. This encoding accepts standard refutations rather than assuming any
such producer's search is correct. Projected enumeration, proof trimming and
streaming proof import address different output-size and proof-transport needs;
the present bounded byte-file interface refuses oversized work explicitly.
Adding those mechanisms would require their own format/pin/runtime review.
