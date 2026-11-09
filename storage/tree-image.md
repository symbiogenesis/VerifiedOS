# Bounded node-image tree read contract

M5.3d's [public tree-image interface](include/vos_tree_image.h) joins its numeric
[node codec](README.md) to a bounded, read-only index. Its admission follows
[ExecutableIndex.v](../proofs/ExecutableIndex.v)'s `well_formed`, `at_depth` and
`published` predicates for unsigned 64-bit keys and values. This interface does
not implement insertion, deletion, authentication or persistent publication.

The caller supplies one stable arena snapshot: exactly `arena_nodes` fixed-size
blocks and exactly one independently bound expected generation per block. The
lengths, geometry and root must agree before any block is read. A retained tree
can contain nodes of different generations. The caller authenticates every
reachable block and its expected generation against independent retained-root
evidence before this interface uses it. Identity fields are not that evidence.
Inputs and output must be disjoint and stay unchanged throughout the call.

`vos_tree_lookup` validates every reachable node, including branches outside the
query's route, serving as the full-tree checkpoint audit. `vos_tree_lookup_path`
provides the $O(\log_B N)$ runtime query path (R-10-022a): it validates only the
root-to-leaf path (`height + 1` node decodes), checking expected identity and
generation, strict separator ordering across every visited branch, the inherited
`[lower, upper)` key bracket at each step, strict leaf key ordering, and exact
leaf depth `height == 0` on the routed leaf without walking off-route subtrees.
Local framing and expected identity/generation use the existing
codec. Leaf keys are strictly increasing, each at or above its inherited lower
bound and strictly below its upper bound. Separators are strictly increasing,
strictly above the inherited lower bound and strictly below the upper bound.
Their child intervals include their left separator and exclude their right
separator. Equality routes right. Every leaf is at exactly the declared height;
a leaf root has height zero. Empty leaves and single-child branches remain
admissible, matching the reference's lack of a minimum occupancy rule.

The declared height must fit the composition's depth limit and the implementation
ceiling. The visit budget counts every visited reference, so repeated references
cannot multiply work without bound. Repeated references to an empty subtree are
permitted when each interval admits it, as the reference permits them; this API
adds no ownership or unique-parent condition. Cycles exhaust the finite height
and refuse. Unreachable blocks do not enter the tree predicate. Work or depth
exhaustion is refusal even if a larger budget could admit the tree.

The result distinguishes `FOUND`, `MISSING` and `REFUSED`. A found value is
published only after the entire reachable tree passes admission. A true miss
also requires full admission. Missing keys, malformed nodes, key/range defects,
unequal leaf depths and exhausted bounds can never share a successful result.
Only `FOUND` changes the caller's output. No partially checked value escapes
when another branch refuses.

Acceptance requires independent byte-built trees and key/map answers, including
separator equality, full-width keys/values, two parameterized instances and
retained roots with mixed node generations. Refusal cases cover off-route tree
defects, ordering/ranges, cycles, skew, out-of-arena references, exact depth/work
limits and stale node identities/generations while preserving caller output.
Compiled behavioral defects must execute and fail their designated witnesses;
compilation failure supplies no mutation kill. These finite native comparisons
do not establish a refinement theorem or satisfy the real crypto, device-trace,
durable publication/reopen or two-instance target acceptance in M5.3d.

## Production typed keys and authenticated values

R-10-003's parametric index is the production boundary; this numeric `VOSNODE1`
instance is a bounded bring-up codec. M5.3d must instantiate the same index over
the complete L2 key and authenticated value before claiming the L2/AEAD join.
`KeyspaceDomains.v` orders the six components as domain, namespace, kind, object,
attribute and version. The wire codec encodes every component in that order with
one composition-fixed unsigned big-endian width per component, rejects values
outside its declared range, and proves that byte comparison agrees with the
abstract lexicographic comparator. Truncation, concatenation without fixed
boundaries and hashing the tuple into a 64-bit key are inadmissible.

A snapshot retains an authenticated root and generation in bounded metadata and
selects that root before lookup; creation does not rewrite or copy the keyspace.
The version suffix groups versions of one logical key and is not a contiguous
snapshot prefix. A query spanning retained versions declares its maximum version
population and charges filtering against it; composition refuses an unbounded
range scan. Neither a different key order nor a second index proof follows from
wanting a snapshot-prefix query.

The production leaf value is an inline typed extent descriptor: logical extent
coordinates, byte length, generation and nonce-derivation kind/epoch, a 128-bit
AES-GCM tag and an independent 256-bit domain-keyed dedup digest. A branch entry
holds child coordinates/generation and its 128-bit tag. Coordinates determine
the nonce only under the existing injectivity/reservation contract. The value
is not the bring-up `uint64_t`; putting an unchecked descriptor beside ciphertext
would lose the independent binding R-10-022a requires.

The descriptor profile derives leaf/branch capacities from header bytes, complete
key widths, these value widths and the declared block size. Both encoding and
admission refuse a block that cannot fit the required entries; no 128-byte
bring-up fanout is inherited. Before production codec implementation, the profile
must fix those widths and limits and land the Narcissus grammar/canonicity and
parametric-index correspondence predicates. Acceptance includes full-width keys,
cross-component boundary order, overflow/collision refusals, exact descriptor
round trips, wrong-location tag refusal, snapshot-root isolation and measured
path/retained-version budgets on the actual producer. The existing numeric
codec tests establish none of that widened production join.
