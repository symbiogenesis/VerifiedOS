# Durable document counts

Document maintenance uses canonical enumerations and generated summaries. Narrative
cross-references describe their subject without repeating its changing size.
Contract limits, enumerated obligations, authored estimates and historical measured
evidence keep their exact values and scope.

Checklist item cells carry hours, ranges, authority classes and measurement status.
They do not carry a share of the changing grand total. Aggregate progress, class
sums and calibration results remain generated. Calibration results live in a
generated table; narrative interpretation must not assume that every sample
overran its estimate. Attended and agent-parallel measurements stay separate.

Current counts are checked where they are deliberately presented. Removing an
incidental prose count must not remove validation of its owner: enumerations remain
nonempty where required, membership remains checked in both directions, and valid
empty status buckets remain allowed. Historical completion evidence is not repaired
from a live inventory. Duplicate-count detection uses the subject and declared
document scope, independently of the current numeric value of another inventory.

Acceptance requires focused regression evidence for estimate-cell parsing and
repair, calibration-table repair, missing enumeration owners, valid zero status
buckets, stable duplicate-count detection when unrelated inventories grow, and
preservation of historical evidence. The checker registry and mutation cases must
describe the resulting rules. Host CI must pass on Windows and Ubuntu for the
published revision; both Guest CI lanes are dispatched under the repository's
validation handoff.
