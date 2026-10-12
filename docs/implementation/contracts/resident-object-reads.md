# Bounded resident object reads

R-10-006a and R-10-006b in the [requirements register](../../requirements-register.md)
own the obligations. This contract owns their implementation and qualification
recipe. Q44 owns the new reference, retained-read source and evidence; M5.3d
provides the executable storage/authentication and target join, and M5.4 consumes
the same interface. The contract is landed design input, with implementation and
qualification open.

## Assessment and scope

Repeated readers need safe lifetimes; they need not each write a common lifetime
counter. Linux's [folio-read proposal](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/%2B/refs/heads/noref-filemap-read-with-llm)
addresses that bookkeeping and its CPU cache-coherence cost. VerifiedOS excludes
that coherence machinery, but atomic counters still consume scheduled memory-bank
and owner service work. An immutable resident window permits retention to be
established at an explicit boundary and reused for several reads.

Adopt that narrow obligation. A blanket reference-count ban would conflict with
mutable CoW extent sharing and contained `Arc` use. A promise of linear scaling
would exceed the finite memory, crypto, ring and storage-service budgets. Retaining
a window also spends memory and adds a retirement proof, so admission charges that
cost beside the avoided common writes. No Linux code or reclamation algorithm is
incorporated, and RCU is not a required implementation.

The qualifying operation reads an exact byte interval of one already resident,
immutable version under a live admitted reservation. A reservation is bounded
retention, not a new authority source. The service checks the current caller's
rights at each operation; namespace deletion, grant revocation or profile teardown
cannot be bypassed by holding a reservation. Resident bytes and retained metadata
stay inside the existing domain/island and delegation rules.

## Interface and resource record

The selected representation declares these typed inputs and transitions:

- Admission binds a storage owner, domain, exact object version, resident byte
  window and applicable authenticated root. It establishes a charged live range
  before acknowledging success. System-image roots identify the admitted generation;
  a generation change cannot silently rebind an existing reservation.
- Read supplies that reservation and an in-window offset/length. It checks current
  authority, identity and byte authentication before returning payload. R-10-001's
  every-read verification and R-10-012's authenticate-then-return rule remain intact;
  a prior admission or authenticated descriptor alone cannot replace them.
- Renewal and retirement are explicit operations. The owner closes admission and
  prevents new reads before completing outstanding operations and the existing
  revocation/reuse barrier. A holder cannot force indefinite waiting for its
  acknowledgement. Reset/crash does not restore volatile reservations as authority.

Composition records finite bounds for resident backing and metadata, holders,
outstanding reads/transfers, request length, retention/renewal policy, retained
predecessors, quarantine and retirement steps. Those bounds include bytes held
while a CoW replacement, deletion or generation change is pending. Counter
exhaustion cannot wrap into a live identifier or count. Exhaustion returns the
declared refusal or enters a separately bounded lawful fallback; it does not
silently fall back to unbounded pinning or reclaim live backing.

Statically retained generation bytes and revocable owner-held windows are possible
representations, subject to these same identity, authority and lifetime obligations.
The contract selects no cache geometry or replacement algorithm. Retained capacity,
admission/renewal/retirement work and each fallback are inputs to the existing
memory plan and temporal admission, rather than amortized costs omitted from WCET.

## Traffic classification

For successful reads under fixed live reservations, the complete caller-to-owner
path issues no read-triggered write to lifetime, pin/reference-count,
replacement-recency or hit-count metadata common to reader sessions. A common
counter updated by one storage owner on behalf of every reader is still common
metadata. Performing a release/reacquire around each read is a hidden per-read
reservation event and does not satisfy the path.

Enumerate the concrete stored state and classify every observed write. Bounded
request/session-private state and SPSC publication retain their own counts; any
other read work, including authentication and diagnostics, is separately enumerated
and charged. This classification cannot hide a common lifetime or replacement
write behind a ring handler, callback, statistics label or batch wrapper. Mutable
CoW extent accounting, cache misses/fills and explicit admission/renewal/retirement
are outside the zero-per-read class and have their own declared resource bounds.

Record read count N, explicit reservation events, bytes returned and writes by
class. With admission/renewal/retirement events fixed, varying N through the declared
finite witness range adds zero writes in the prohibited common class. Total work
need not be zero or independent of N: copies, authentication, private bookkeeping
and publication still cost work, and a single storage owner may serialize requests.
Counts are behavioral evidence, not timing measurements or throughput benchmarks.

## Qualification and controls

Use an inhabited implementation with at least two independent reader sessions
reading the same resident version repeatedly under a fixed reservation schedule.
Return independently checked expected bytes, including boundary-length reads;
missing payload, an always-refusing reader, singleton-only execution and omitted
or incomplete observation cannot qualify. Complete execution and independently
checked payload must establish that the reads actually ran and every concrete
writer was covered; a complete execution may legitimately issue zero stores. Bind evidence to the exact source, configuration,
reservation bounds, write classification and executable/target artifact.

Exercise lifecycle cuts during admitted reads and outstanding transfers: eviction,
delete, CoW replacement, generation-root change, close, grant revocation, holder
failure and reset/crash. Old authorized operations see the exact retained version,
or the existing bounded refusal; an old handle never redirects to replacement
bytes. Mutation and zeroization wait until no authorized reader or accepted transfer can
access the range; reuse follows completed containment, sweep and zeroization under
R-08-004, R-08-006 and R-08-007a. No crash snapshot recreates the old authority.
Wrong domain, version, root, out-of-window request or failed authentication returns
no payload. Exhaust each declared resource and exercise the chosen refusal/fallback
and counter limits; verify the retirement bound without a cooperative holder.

Keep a passing control beside each deliberately defective construction. Compile
controls that add a common per-read increment/decrement, replacement touch or
hidden reacquisition; each must fail the traffic predicate while serving the same
correct bytes. Premature reuse, old-handle rebinding, omitted domain/root/authentication
checks, counter wrap and unbounded holder-wait controls must fail their intended
lifetime/resource predicate. Distinguish a control that does not compile from an
executed rejection; investigate any survivor.

The reference theorem states preservation of version/authority and reuse safety,
the bounded resource and retirement obligations, and the classified traffic
property. Review its inhabited premises and rejected examples, then compile and
check assumptions through the locked proof workflow. The concrete storage owner
and target trace must refine that reference; a fixture count does not provide this
connection. M5.3d's target join runs the system-image and user-data instances
through the same implementation. Complete proof/model/RTL suites and all benchmarks
remain GitHub Actions-only under the repository's validation handoff.

## Acceptance boundary

A successful qualification establishes the stated no-common-write path and its
safe bounded lifetime. It does not establish cache-hit rate, arbitrary linear
throughput, immunity to all shared metadata costs, NAND endurance, physical memory
retention or completion of the remaining storage proof chain. The existing storage
recovery policy, confidentiality, temporal admission, revocation and hardware
isolation obligations remain prerequisites at their own boundaries.
