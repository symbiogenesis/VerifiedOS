# Second-class baseline and boundary admission contract

This Q22e dependency resolves the baseline path of second-class stores and makes
the existing cyclic-executive admission consume the full boundary it already
owes. It does not select store-buffer deletion, qualify memory or timing, or
supply an emitted target schedule. The [comparison](../store-buffer-comparison.md)
retains its target completion predicate.

## Register decision

Select the unbuffered second-class arm. Keep the FIFO SRAM-only. A second-class
store issues after prior buffered stores have entered the fabric, completes the
atomic data/tag/ECC bank commit before retirement, and cannot be overtaken by a
later memory operation. Cross-path arrival and visibility remain R-15-015a's
obligation; acceptance at a bank is not completion. R-15-218 remains an SRAM
buffer bound. The second-class operation's separate qualified service bound
covers routing, grants, occupancy and every permitted refresh phase.

R-07-040 must cover every reachable timer-to-boundary-handler prefix, including
the remaining irrevocable operation and any consequent synchronous fault path,
or the remainder of an already live kernel path. Pending delivery prevents new
ordinary predecessor instructions; only work needed to reach that precise
completion/fault boundary and finish its required kernel path continues. A
completed store is never replayed. Explicitly restartable scrub/sweep groups and
fatal fault paths retain their existing contracts. Service needed to finish a
prefix must remain available after the timer fires, without borrowing a peer's
grant. A missing finite bound refuses the composition.

The residency bound H bounds each complete prefix. A prefix counts a remaining
operation and its consequent handler sequentially; separate full-operation and
full-handler maxima neither establish coverage nor authorize double counting.
The padded boundary is H plus R-15-220's platform cost plus R-15-220a's context
cost. Every successful path releases at table instant plus that bound, with
padding when it finishes early. Faults that require fail-stop do not release a
successor. R-11-009 charges the boundary once per visit; elapsed instruction
service before the table instant stays in the in-slot cost and its remaining
post-timer service stays in H.
This partitions executed time, not separately maximized reservations: retain
the sound full-instruction WCET bound, with no guessed residual subtraction.
WCET plus the padded boundary may conservatively reserve unused capacity. Do
not add another per-boundary operation or handler charge already covered by H.

Acceptance of the decision requires paired register/spec edits at R-15-015b,
R-15-218, R-07-040 and R-11-009, resolution of affected cross-references and
coverage, co-reads, and independent full reading. No architectural ordering rule,
fence obligation, fatal-fault behavior or qualification flag is weakened.

## Executable admission repair

Add a Gallina boundary-cost definition over the existing PartitionContext
platform cost, a composition-declared context bound and a finite nonempty list
of complete residency cases. Each case has non-overlapping remaining-operation
and remaining-handler costs; its sum bounds that case, and the maximum bounds
the declared set. The record must state that coverage and physical soundness of
these declared cases are refinement obligations, not consequences of arithmetic.
An empty case set must not yield an accepted zero residency. A zero-cost idle
case is representable explicitly.

Change CyclicExecutive's slot admission to consume the boundary cost. Preserve
the three-term platform definition for consumers asking for that quantity.
Where the existing executive asks for a switch rather than a boundary, consume
platform plus context and retain any separately required table-load term.
Audit all consumers of the changed record and definitions, including generated
validation domains, so passing demonstrations use explicit boundary inputs.

Prove the boundary bounds every declared successful prefix followed by its
switch, padding fixes the successful release instant independently of the
chosen prefix, and each component is monotone. Prove that an accepted slot has
room for its workload bound plus this full boundary. Include load-bearing
refutations of omitted context, omitted residual operation, and a bound taking
the maximum instead of the sum for an operation followed by a fault handler.
Exercise idle, live-kernel, unbuffered-completion and operation-then-fault cases;
include a nonempty witness and empty-case admission refusal.

Use the existing proof gate for compilation, claim and assumption audit and
rocqchk. Use generated validation where its existing domains cover the changed
arithmetic; expand the domain if needed. The integrator owns generated headers,
shared documentation, co-reads, arithmetic repair and the final host wave.
Source-level theorems establish this admission arithmetic only. They do not
certify the completeness of the prefix list, a target WCET or an RTL timer.
