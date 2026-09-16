# Declared periodic schedule extraction

`python tools/run.py phase-schedule SCHEDULE RESOURCES --json` resolves named
requests and resource occupancies into the existing finite phase-service
contract, then checks that contract. This implements the schedule extraction
part of the [prerequisite contract](prerequisite-contract.md). The inputs below
are declarations. They do not implement the target admission emitter or establish
that an instruction stream, arbiter, qualified macro or all initial states obeys
them. Every receipt keeps `target_comparison` equal to `open`.

## Input format

Both files are UTF-8 JSON, without comments or trailing commas. Every listed
field is required and every unlisted field is rejected, at every object level.
Duplicate JSON keys, duplicate names within a namespace, floating-point and
non-finite numbers, and booleans in integer fields are errors. Names match
`[A-Za-z][A-Za-z0-9_.-]*`, are case-sensitive, and need only be unique within their
own namespace. A hart and a bank may share a spelling. Each duration and limit is
an integer in the same declared cycle domain; there is no clock conversion.

The resource object has these exact fields:

| Field | Value |
| --- | --- |
| `schema` | Exactly `"phase-resources-v1"` |
| `harts` | Nonempty array of objects containing exactly `name` and positive integer `issue_limit`. The limit counts requests from that hart within any one cycle's alternative. |
| `operations` | Nonempty array of distinct operation-class names. |
| `banks` | Nonempty array of the bank objects described below. Array order assigns bank numbers. |

Each bank has exactly these fields:

| Field | Value |
| --- | --- |
| `name` | Stable bank name. |
| `path_cycles` | Nonnegative integer fabric transit time, with zero meaning acceptance in the issue cycle. |
| `occupancy_cycles` | Nonempty object mapping declared operation names to positive integer occupancy. A bank need not support every declared operation; a request to an unsupported operation is an error. |
| `refresh_cycles` | Positive integer refresh occupancy, or `null` when this bank has no refresh declaration. A scheduled refresh of a bank with `null` is an error. |

Operation occupancy and refresh occupancy include the acceptance or reservation
cycle. Banks accept at most one request in a cycle. Refresh starts before request
acceptance, reserves its bank for its stated occupancy, and consumes no injection
grant. These are the existing [phase-service semantics](../store-buffer-comparison.md),
including carried fabric and bank state across frame wrap.

The schedule object has exactly these fields:

| Field | Value |
| --- | --- |
| `schema` | Exactly `"phase-schedule-v1"` |
| `name` | Stable schedule name. |
| `mode` | Exactly `"periodic"`; only one mode is supported. |
| `resources_sha256` | Full lowercase SHA-256 of the supplied resource file's exact bytes. Even a whitespace-only resource edit requires a new digest. |
| `phases` | Nonempty array of phase objects, each one cycle, repeated in array order forever. The initial state is phase zero with empty banks and no requests in flight. |

Each phase has exactly `grant`, `alternatives` and `refresh`. `grant` is the
nonnegative maximum total requests injected in that phase. `alternatives` is a
nonempty array of request arrays. Each request has exactly `hart`, `bank` and
`operation`, referencing resource names. An empty request array explicitly allows
no requests. `refresh` is an array of distinct bank names, possibly empty, whose
refresh starts in that phase. A hart's integer identity follows its resource array
order, independently of bank numbering.

Every alternative is retained in its declared order and every request retains
its within-batch issue order. The checker chooses one whole alternative each
cycle and explores all reachable histories. It does not combine independent
per-request choices or infer additional empty alternatives. Duplicate alternatives
are retained. An alternative exceeding its hart's declared issue limit is a
malformed admitted-issue assertion and is rejected. Missing banks, harts,
operations or occupancies are errors. A service conflict, including a joint
bank collision or traffic exceeding the phase grant, remains an explicit
alternative for the service checker to refute. The receipt's
`injection_excesses` lists every over-grant phase/alternative using zero-based
indices; these records do not replace the service counterexample trace.

Fields such as `qualified`, `modes`, `transitions` or an undeclared initial state
are unsupported and refused. No input boolean can promote the declaration into
qualification. Per-hart limits constrain only the declared requests; they do not
prove an instruction stream or issue-width model emits no other traffic.

## Synthetic examples and output

The [resource fixture](schedule-examples/resources.json) supplies synthetic
occupancies, zero fabric latency, one hart and one bank. The examples bind that
file and exercise the comparison's required counterexamples:

| Schedule | Expected result |
| --- | --- |
| [Grant gap](schedule-examples/grant-gap.json) | Refutes a read permitted during the zero-grant phase of `[2, 0]`. |
| [Same-bank joint](schedule-examples/same-bank-joint.json) | Refutes two jointly admitted reads to one bank, each individually legal. |
| [Frame wrap](schedule-examples/frame-wrap.json) | Refutes a first-phase read after a final-phase write leaves its bank occupied. |
| [Closed companion](schedule-examples/closed-companion.json) | Closes after restricting the first phase to an explicit empty batch. |

Run any row by substituting its filename:

```powershell
python tools/run.py phase-schedule docs/implementation/phase-service/schedule-examples/grant-gap.json docs/implementation/phase-service/schedule-examples/resources.json --json
python tools/run.py phase-schedule docs/implementation/phase-service/schedule-examples/closed-companion.json docs/implementation/phase-service/schedule-examples/resources.json --json --output-contract out/declared-phase-contract.json
python tools/run.py phase-service --contract out/declared-phase-contract.json --json
```

The output contract's parent directory must exist and the destination must be a
new file. The extractor refuses to overwrite an existing file or either input.
It may emit a well-formed refuted contract, so a later reader can reproduce the
same failure. Output is UTF-8 JSON with sorted keys, compact separators and one
final LF. `contract_sha256` binds exactly these bytes whether or not a file is
requested. `schedule_sha256` and `resources_sha256` bind the bytes read once for
parsing; `sources_sha256` binds the extractor, CLI, service implementation and this
format document. Hashes record byte identity, not provenance or truth.

The report includes the contract, bank/hart/operation name tables, aggregate
injection excesses, and the service result with its counterexample trace or
acceptance drain. Exit 0 means the declared service contract closes, 1 means a
service refutation, and 2 means malformed or unreadable input, a stale resource
hash, or an unavailable output path. A failed output does not become a successful
receipt. The acceptance drain retains its original fabric-only meaning; completion
and physical quiescence have separate obligations in the prerequisite contract.

Q22e still needs the target instruction-stream and arbiter mapping, mode and
initial-state coverage, qualified timing and memory, and workload WCET, area and
power evidence. A closed synthetic companion supplies none of those operands.
