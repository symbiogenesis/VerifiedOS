# Mathematical research evidence maintenance

This is the implementation contract for the non-normative research evidence
manifest and generated view linked by the [survey](open-math-conjectures.md).
It changes no requirement, accepted premise, implementation selection or proof
status. The manifest owns each selected claim's status; the survey supplies
explanation and the linked implementation contracts own adoption.

Each decision-relevant entry records a permanent identifier, precise claim,
source URL and immutable version or revision, date inspected, evidence stage,
assumptions and exclusions, consumer artifact and plan owner, disposition
(`evaluate now`, `await workload`, or `monitor security`), and next action.
Source inspection, supplied replay records, independent replay and production
acceptance are distinct stages. An axiom allowlist is not a measured dependency
audit. A review date is not an assertion that no newer source exists.

The host `math-evidence` command validates the manifest and emits a deterministic
Markdown view. Acceptance requires refusal of missing or unknown fields,
duplicate identifiers or JSON keys, empty required collections, invalid dates,
unknown evidence stages or dispositions, unresolved local consumer links and
unversioned source identities. Missing generated output or changed output is a
check failure; emission repairs only the derived view. Tests exercise malformed
inputs and stale output. The ordinary generated-artifact gate checks the view
without network access. Checking metadata supplies no theorem or source-truth
verdict.

The same command reports finite shapes from the existing host/reference composer:
component and edge counts, immutable key/value encoding widths and bytes, absent
key behavior, and a deterministic sorted-array baseline. It binds the fixture
and implementation bytes and distinguishes reference lookup workloads from
observed production access frequencies. The report is generated and checked,
contains no timing benchmark, and supplies no resident producer, target WCET or
actual-roster measurement. A future dictionary selection must identify its own
workload and finite resource threshold before benchmarking on CI. Dynamic
service indexes retain their separate update, exhaustion and recovery contract.
