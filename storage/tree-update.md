# Bounded node-image candidate update

M5.3d's [public update interface](include/vos_tree_update.h) implements bounded
numeric insertion, replacement, single-pass sorted-batch updates, lazy CoW
deletion, canonical bottom-up compaction, and $O(1)$ birth-generation snapshot
liveness checks over its [node codec](README.md) and
[tree admission](tree-image.md). The single-key algorithm follows
[ExecutableIndex.v](../proofs/ExecutableIndex.v)'s append-only `insert`,
`publish_leaf`, `publish_branch` and gated-root structure. This source checkpoint
implements a candidate producer; authentication and durable publication remain
the [storage recovery contract](../docs/implementation/storage-recovery-policy.md)'s
operational joins.

The caller supplies full fixed-capacity byte and expected-generation arrays,
their exact lengths, and a nonempty allocated prefix `used`. Every input node
reachable from the retained root must lie in that prefix. Complete prior-tree
admission runs before any append, including nodes outside the update route.
The retained snapshot and expected generations must already be authenticated by
the caller and remain stable during the operation. Input/output objects and the
backing arrays are disjoint. No field in the numeric node format authenticates
its own bytes.

Insertion routes separator equality right, replaces an existing leaf key's
value, and inserts a missing key in numeric order. Each visited path node is
copied into the unused suffix. Overflow divides a leaf at half its entry count,
promoting the right leaf's first key. Branch overflow divides the child sequence
at half its count and promotes the separator immediately before the right half.
A root split creates a new branch and increases the exact leaf height once.
Unchanged subtrees retain their existing node identities and generations; all
appended nodes receive the caller's candidate generation. Generation ordering,
nonce allocation and authenticated root binding are not inferred from a number.

`vos_tree_insert_batch` applies a strictly key-sorted batch of `1..VOS_TREE_MAX_BATCH`
entries in one top-down copy-on-write pass (R-10-004). It partitions the batch
across branch separator intervals so untouched subtrees are neither read nor
copied and each modified node on the union of paths is allocated in `generation`
at most once per transaction. Unsorted, duplicate-key, empty or oversized batches
refuse before any block is appended.

`vos_tree_delete` removes a key using Rodeh-style lazy copy-on-write deletion
without sibling underflow borrows or merges (R-10-010). It rewrites only the
root-to-leaf path, prunes child subtrees whose count drops to zero (updating the
parent branch's separator list while preserving every surviving child's valid
key bracket), and collapses single-child branch roots until the root is either a
leaf at height zero or a multi-child branch.

`vos_tree_compact` performs an in-order traversal of the reachable tree and
packs its live sorted entries bottom-up into a canonical, history-independent B+
tree in `generation` (R-10-021), filling every leaf and branch to `fan` entries
except along the right spine. Any two trees with the same logical key/value map
and geometry compact to identical node layouts regardless of prior insertion or
deletion order. `vos_tree_can_reclaim_node` decides in $O(1)$ from an overwritten
or deleted node's birth generation (`node_generation > latest_snapshot_generation`)
whether the block can be reclaimed immediately or must join a retained snapshot's
deadlist (R-10-010).

The function returns success only after full candidate admission at the returned
height and a lookup confirming the requested key/value. The same finite visit
limit applies independently to the prior and candidate checks; a larger candidate
may therefore refuse when its input fitted. Root growth must fit the declared
depth limit and the reader's implementation ceiling. Allocation cannot exceed
the arena capacity. Empty leaves and single-child branches preserve the
reference's absence of a minimum-occupancy contract.

The output root, height and new allocated-prefix length change only on success.
The prior allocated byte and generation prefixes never change, preserving all
retained roots using them. A refusal may leave appended bytes and generations in
the unused suffix; these remain unreachable through the retained prefix and are
overwritten by a later attempt. The caller adopts the returned prefix only as a
candidate. This interface neither advances its input `used` field nor publishes,
acknowledges, authenticates, encrypts or persists any root.

The focused native campaign compares two parameterized populations at fanouts
2, 3, 4 and 16 with independently computed dictionaries and an independent
byte-tree parser. It checks ordered and reverse insertions, replacement,
full-width keys/values, mixed-generation sharing and unchanged retained roots.
Fanouts 2, 3 and 4 exercise internal and repeated root splits; fanout 16 exercises
leaf/root splitting. Refusals cover bounded allocation, root-growth depth,
candidate visits, malformed input and references into the unallocated suffix.
Compiled value, copy-on-write and split defects must execute and fail their
designated witnesses; compilation failures supply no mutation kill.

These finite comparisons establish no Gallina-to-C refinement, minimum occupancy,
deletion/merge behavior, cryptographic soundness, crash consistency, persistent
reopen, compartment isolation or two-instance target acceptance. M5.3d retains
each of those applicable joins.
