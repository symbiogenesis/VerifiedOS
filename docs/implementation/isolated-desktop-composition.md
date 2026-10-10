# Isolated desktop composition

This is Q34i's bounded composition reference and delivery record. The
[checklist's acceptance predicate](implementation-checklist.md) remains open:
the actual first-release roster and its complete resident-byte accounting are
not supplied. [R-14-011c and R-17-007b](../requirements-register.md) own placement
and the observation boundary; R-18-004b owns the comparisons. No requirement,
general-domain pool declaration or statement in
[ElasticDomain.v](../../proofs/ElasticDomain.v) changes here.

## Composition rule and refusals

[desktop_composition.py](../../tools/vos/desktop_composition.py) binds each
installed desktop application's compartments to a supplied, composition-fixed
envelope. Either the manifest's isolation bit or the holder's isolation input
places the application in its isolated domain. The other input cannot clear
that declaration. An ordinary application binds to its profile's general
domain. One isolated application can contain several compartments; they share
one application's manifest, label, fixed reservation, class-specific pools and
session manager.

`compose` receives labels, extents, reservations and session-manager identities
from the static composition and fills the member lists. It allocates no capacity
and synthesizes no runtime authority. `admit` checks already-filled declarations.
Every installed compartment must occur exactly once, and every profile has one
general domain. Fixed-tier shapes have explicit fixed placements outside desktop
domains; browser origins cannot enter desktop domains. Native artifact admission,
successor-generation installation and interpreted-bundle validation remain their
existing owners' obligations.

Admission refuses a declared-isolated application in the general domain, a
second application's manifest in an isolated domain, and an isolated member's
edge back to a general member. Each isolated session manager has exactly one
`session_requests` endpoint from its profile's general session manager. That
endpoint has no return path and no capability slot. Other direct edges between
desktop domains are refused, including edges between isolated domains. Runtime
declassification through the powerbox stays outside this reference's direct-edge
model. Different domains have different labels, managers and disjoint pool
extents. Shared-core reservations use one declared frame period and cannot
overlap, even when declarations reuse the same Python reservation object.

## Reading the existing elastic contract

The [elastic-domain contract](contracts/elastic-domain.md) states an arbitrary
domain, not one domain per profile. `Domain` carries one label, a member list,
cores, dormant contexts and class-indexed extents. `Decl` carries one domain's
dispatch constants. `Global` separates that domain's state, the composed frame
and other-label observations. `ReadsOnlyItsLabel` and `MovesNothingOutside`
quantify arbitrary declarations and transitions. The allocation histories and
`Distribution` likewise parameterize one arena and one member predicate. None
quantifies profiles or assumes a singleton profile domain. No Q34a singleton
finding is needed. Its recorded share and accounting findings retain their
existing owners and are not resolved by domain placement.

[IsolatedDesktop.v](../../proofs/IsolatedDesktop.v) instantiates the existing
envelope with a general and an isolated label, both placed on core zero in a
single fixed frame. The isolated declaration enumerates one application's
manifest and is admitted by `decl_admits`. `DesktopState` keeps both domains'
complete dispatch states and separate pool observations. Each projection uses
the existing `Global` and dispatch confinement theorem; its transition
instantiates `within_the_envelope` while preserving the other's complete
dispatch state and pool. A changing general-domain step witnesses that the
relation is inhabited.

The file proves that either domain's dispatch and pool read only its own state.
For both domain directions, changing only the other pool refutes a dispatch
mutant that defers to that pool and a pool-read mutant that adds its occupancy.
The request endpoint's isolated distribution also instantiates the existing
pool-capability confinement theorem. These are contract-level witnesses and
checked refutations, not native kernel or pool-service refinements.

## Pool pricing and the missing roster

`price_pools` requires the caller's complete first- and second-class resident
demand outside all desktop pools, both class supplies as payload bytes, and
each class's exact exclusivity fraction. Outside-pool demand includes code,
contexts, session managers, service storage, metadata and quarantine not already
inside the supplied extents. The caller also supplies the preceding general
domain's pool declarations. Both general extents must remain exactly unchanged.
Every isolated pool is added beside them; no isolated bytes can be taken from
the general pool.

The report sums each class's outside-pool demand and every domain extent,
compares the sum with `(1 - exclusivity) * usable_payload`, and reports exact
rational headroom. It also reports the isolated pools' additive first- and
second-class cost. The first-class supply floor is read from R-15-173a's
pessimistic ungraded band; the general pool floor comes from R-18-004a, and the
second-class supply floor and exclusivity ceiling come from R-18-004b. The
reader takes these figures afresh from their normative owner entries and binds
the report to their digest. Missing, repeated or unsupported owner shapes are
refused. There is no default roster demand or supply figure.

The [focused tests](../../tools/tests/test_desktop_composition.py) supply a
synthetic fixture with eight ordinary applications and two isolated manifests,
then check supplemental pool charges, exact capacity equalities and excess-byte,
supply-floor, exclusivity and changed-general-pool controls. The fixture's
bytes are test operands. They are not the release roster's footprint or a
measured macro's usable supply.

The [boot-roster contract](contracts/boot-roster.md) records that no recipe
composes accepted products for the whole roster.
[MemoryPlan.v](../../proofs/MemoryPlan.v) supplies demonstration geometry, not
the accepted first-release residency list. No complete first-release static
plan, isolated-application footprint, measured class supply or operating-point
grant can therefore be substituted into this record. Actual roster capacity
pricing remains Q34i's unresolved acceptance clause. Bandwidth, area, yield,
unit cost and supply qualification retain R-18-004b's instruments and are not
accepted by these two capacity comparisons. Q34e still owes the general
domain's focus dispatch and input-to-response measurements with isolated
domains beside it; Q10 owns the product judgment of their cost.

## Delivery evidence

Focused host tests cover placement, wiring, fixed-tier shapes, reservation and
pool separation, owner-policy refusal and exact pricing. Pinned Ruff and ty
checks pass on the authored Python files for Linux and Windows analysis.
A focused Rocq 9.3.0 compile of `IsolatedDesktop.v` and its `Require` closure
passed in 72.475 seconds; the candidate compiled under the proof gate's strict
settings. Native enumeration found 34 new symbols, all closed under the global
context. A focused `rocqchk -silent -o -Q proofs "" IsolatedDesktop` rechecked
that module and its compiled dependency environment; the existing gate's summary
parser found no axioms or unsafe assumptions. That audit and kernel check took
37.181 seconds. The first candidate closed, with no change to the locked prover,
an existing proof statement or an accepted assumption. These scoped checks do
not establish the full corpus's proof acceptance. The complete strict compile,
assumption audit, native inventory and kernel gate remain pending cold Guest CI
at the integrator's settled revision. Host CI and that Guest CI handoff remain
the integrator's gates.

The verbatim native records are retained as
[`/root/build/lane-solve-20261010-a/desktop-candidate/candidate-result.json`](retained-evidence/root/build/lane-solve-20261010-a/desktop-candidate/candidate-result.json),
SHA256 `1bc9e4a5799d8e7c01dff71f69799f276c798ac04cbdb9162c759c85a31be1e0`,
[`/root/build/lane-solve-20261010-a/desktop-candidate/focused-audit.json`](retained-evidence/root/build/lane-solve-20261010-a/desktop-candidate/focused-audit.json),
SHA256 `d6e0a34076e356b6cb4004d8c929107d0f83859eca414ad0b899d9a0098529de`,
and
[`/root/build/lane-solve-20261010-a/desktop-candidate/kernel-context.txt`](retained-evidence/root/build/lane-solve-20261010-a/desktop-candidate/kernel-context.txt),
SHA256 `6ab673b318a00623c62cd191789fc8932cdf30981865a3044a9538e75c9cd204`.
These copies preserve the scoped observation after lane retirement and are not
current proof receipts.

## Dispatch decision

On 2026-10-10 the acceptance reading identified the missing actual first-release
roster. With the user delegating the continuation choice, this batch retained
Q34i's reusable composition checks, proof witnesses and exact accounting as a
bounded checkpoint. The accepted-roster comparison remains open; the checkpoint
neither invents budgets nor closes full Q34i. Keeping this prerequisite gives
the eventual roster and Q34e join a concrete admission and pricing interface.
