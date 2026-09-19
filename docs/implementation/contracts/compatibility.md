# Compatibility contract for an editor-driven native test cycle

Status: **workflow and authority contract authored; target execution open**.
Q9 selects the reference Zed editor's edit, build and native-test cycle,
already named in [the porting guide](../userspace-porting.md#zed-the-reference-editor).
The blocked step is running the newly built native test program immediately
inside the generation that built it. R-02-008 excludes that step. The supported
replacement is edit, build, prove, admit, consent to signing, boot the successor
generation, then run its already admitted test compartment.

This is a named consumer of the resident toolchain required by R-13-027 and
R-18-004e, adjacent to the first release's shell and content capabilities. It
does not make Zed a required application in R-18-004a's capability floor and
does not reopen the decision to host the compiler. The same boundary applies
to another editor implementing this interface.

## Smallest interface

These operations are typed requests to existing service roles. They are not
POSIX calls or authority to create arbitrary processes. Their implementation
and parser proofs remain admission prerequisites.

| Operation | Explicit inputs and authority | Result and refusal |
| --- | --- | --- |
| Read source slice | One consent-granted source object, immutable version, offset and length within the grant | Bounded bytes; wrong object/version or out-of-range extent is refused before reading |
| Stage edited source | One granted output-object reservation and bounded byte chunks, with sequence and declared total length | A content-addressed data object after complete digest verification; incomplete, repeated, over-budget or mismatched input is discarded |
| Submit build | Granted source-closure objects, a fixed toolchain/configuration identity, a predeclared build profile and an admitted composition-service endpoint | One bounded job handle; missing closure, foreign profile, unavailable pool or missing composition-mode authority is refused |
| Advance build | Job handle, activation epoch and the composed step budget | Bounded progress or typed completion/refusal; no activation expands its budget and no producer output becomes executable |
| Read diagnostics | The job's result endpoint and bounded sequence range | At most the reserved diagnostic bytes and records; excess becomes an explicit truncated result, never an unbounded queue |
| Cancel build | The job's cancellation capability and current epoch | Quiesce, revoke, sweep and release within the declared release bound; a stale handle affects no replacement job |
| Submit successor for admission | Completed source/proof/output closure and the requested next-generation roster | The ordinary CHERI-TAL and source-correspondence checks run; missing proof, exhausted checking arena or an inadmissible roster leaves the running generation unchanged |
| Request generation consent | The admitted candidate's exact root and roster, forwarded to the trusted path | The holder may authorize the existing signing/install path; the editor receives neither the signing key nor mint, sealing, wiring or boot-selection authority |
| Read successor test result | A separately granted result object from the next generation's admitted test compartment | Bounded diagnostics bound to candidate root, test identity and boot epoch; an old result cannot certify the candidate |

There is no operation to execute a staged object, rewrite the running roster,
install a runtime plugin, load an external helper by path, or bypass checking
because the producer is local. A test program that generates another native
program has the same next-generation boundary. Browser content remains on
R-14-008's contained interpreter path and supplies no alternative native route.

## Capability and trust contracts

The editor holds its private source/result endpoints and grants the holder
explicitly gives it. A builder holds only the selected immutable source
closure, its output reservations and diagnostics endpoint. Neither holds
execute authority over its output, sealing authority or capability-wiring
authority (R-13-027a). Admission and signing remain distinct existing roles;
an admitted object alone does not authorize installation or consent.

The entire dependency/configuration/assumption identity keys reusable proof
results. A changed source, imported lemma, semantics, configuration or admitted
assumption set invalidates the corresponding cached result. Cache lookup is
not an admission bypass. A recovered job or foreign result must match the
complete identity, not just a filename, package label or claimed version.

The editor, source and producer are untrusted. Containment and ordinary
admission supply the security boundary. Imported source parsers and diagnostic
consumers are contained with their own budgets. A successful compilation is
not a binary correspondence theorem, and a successful test is not admission
evidence. M1.10 and M6.10 own the resident implementation and two-generation
demonstration; this contract does not substitute a host subprocess for either.

## Bounded data contract

Before composition, the chosen build profile supplies a finite positive
capacity for every row below. Each declaration includes R-08-046's owning
compartment, derivation source, bind/release capabilities, low and exhausted
thresholds, release-time bound, lifecycle, recovery reserve, confidentiality
label, telemetry policy and restart/generation semantics. A missing field
refuses the profile. Capacities are admission inputs, not host measurements.

| Pool or input-dependent structure | Size fixed before activation | Exhaustion action |
| --- | --- | --- |
| Source selection and dependency index | Maximum objects, edges, name bytes and source bytes; closure depth or an iterative traversal stack bound | Refuse the closure before the build starts |
| Edited source staging | Maximum object bytes, chunk bytes, concurrent partial objects and chunk descriptors | Abort the partial object; publish no digest-named object from incomplete bytes |
| Build jobs and handles | Maximum jobs, epoch width, private per-job state and result handles | Refuse a new job; epoch exhaustion requires retirement, never wrap into a live handle |
| Compiler/prover pass arenas | Per-pass working-set and activation-step bounds fixed in the build profile | End the attempt unadmitted; preserve the running generation and discard unsound partial evidence |
| Diagnostics and UI summaries | Maximum records, bytes per record and retained aggregate bytes | Emit a reserved truncation marker; release old records only by the declared policy |
| Dependency and proof cache | Maximum entries, key bytes and payload bytes with complete identity | Use the declared bounded replacement policy or recompute; neither action grants a proof result |
| Candidate closure and proof package | Maximum objects, certificate bytes, roster entries and checking steps | Refuse admission with no partial wiring or installation |
| Consent and result transfer | Maximum outstanding requests, result bytes and endpoint slots | Refuse new requests; no implicit standing grant or cross-client delivery |

The common member lifecycle is Free, Bound, Quiescing, Revoked, Sweeping,
Reusable. Release needs the declared quiescence and sweep, and interruption
does not make a revoked member reusable early. A restart loses execution
state; durable source and completed content-addressed objects follow the store
contract. A new generation receives fresh handles through its own wiring.
The ordinary-mode floor cannot borrow composition-mode slots or bank grants.

## External-authenticator decision

**Proposed use:** carry an existing roaming-key credential into the developer's
repository or package-service login through a confined client. Its useful
property is interoperability with a credential already enrolled elsewhere.

**Ground:** R-12-020 explicitly declines external roaming hardware security
keys. Bounded messages, a verified parser and absence of arbitrary DMA could
bound platform isolation, but they would not establish the external key's
credential behavior, firmware correctness, origin handling or non-export of
its secrets. Those would remain an external trust dependency even if the
client's platform containment theorem held.

**Disposition: decline the external-authenticator branch.** No CTAP client,
new USB class or exception is admitted here. The existing on-die credential
path remains the supported path; a service accepting only an existing roaming
credential is unavailable through this workflow until the account has an
accepted alternative. This forfeits cross-device credential portability and
may prevent access to such a repository. It does not strengthen the threat
model. Reopening the arm would require an explicit R-12-020/foreign-computer
decision plus protocol, resource and trust contracts before implementation.
This records the same decision shape as Q15's
[contactless disposition](../../background/architectural-alternatives.md#the-contactless-proximity-surface-declined-across-all-four-uses).

## Turnaround comparison owed

Measure both paths over the same source closure, candidate roster, toolchain,
configuration, proof obligations and cache identity. The local path runs the
device's composition mode, performs ordinary checking and consent, installs
through the A/B transactor and boots the successor. The remote path includes
transfer to the authorized remote composer, return of its artifact, the same
device-side checking and consent, and the same installation and boot. A
network failure on the remote path is a recorded failure; the local offline
case must not fetch a missing dependency silently.

Start at acceptance of the named edited source/roster and end at the successor
test's first authenticated result at the declared shell rung. Record source
processing, proof production, transfer, checking, consent wait, installation,
boot and test phases separately. Report both user elapsed time and machine
time excluding the measured consent wait. Cold and reused-cache trials are
separate, with complete identities and invalidation cases recorded.

[Q26's host observations](../../performance/toolchain-residency.md) supply a
working-set and stage comparator. They supply no device wall-clock, and its
local offline act does not meet the network predicate attached to the proposed
DP-3 turnaround limit. The chosen product limit therefore remains an explicit
Q1/Q10 decision. No scaling of host seconds or figure is supplied here.

## Acceptance predicate

The contract half is acceptable when the named editor workflow, each operation's
authority and refusal, every input-dependent pool, generation boundary and
external-authenticator disposition are explicit. A bounded prototype must
exercise missing grants, oversized closure/chunks, stale epochs, diagnostics
exhaustion and cancellation before any broader interface is admitted.

Q9's executable half remains open until one admitted client performs the full
successor-generation cycle under these bounds, both turnaround paths have
valid measurements and any required policy changes are approved. There is no
target editor, composer or complete two-generation image to run that test
against in this lane. The excluded same-generation native-execution branch
stops at R-02-008; no compatibility layer is built to evade that boundary.
