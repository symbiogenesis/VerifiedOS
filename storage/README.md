# Storage executable boundary

[node_image.c](src/node_image.c) supplies M5.3d's first concrete node-image codec.
It serializes a bounded unsigned-64-bit key/value instance of
[ExecutableIndex.v](../proofs/ExecutableIndex.v)'s `ENode`: a leaf contains ordered
key/value entries, while a branch contains separators and child arena addresses.
The codec preserves their order; it does not decide key ordering, separator
ranges, balance, cycles or tree-wide admission. Those checks belong to the index
and its eventual checked decoder integration.

[The public header](include/vos_node_image.h) owns the bounds and API. Composition
supplies fanout, arena capacity and an exact block length large enough for a full
leaf. Empty leaves and single-child branches preserve the reference's local
shape, which has no minimum occupancy. Child addresses and node identity must fit
the declared arena. Encoding and decoding refuse before changing output. Callers
supply disjoint input and output objects.

The canonical format begins with `VOSNODE1`, followed by little-endian kind and
count (`uint32`), node identity and generation (`uint64`). A leaf stores each
key followed by its value; a branch stores its separators followed by its child
addresses. These payload words are little-endian `uint64`. Unused block bytes are
zero and a decoder refuses nonzero padding, an unknown format, wrong length,
wrong expected identity or generation, invalid shape or out-of-arena references.
Unused decoded array cells are zero. In-memory unused cells do not enter the
encoding.

The identity checks provide no authentication. A storage caller must authenticate
the entire block against its independent parent/root evidence before using it;
changed payload bytes can be well-formed and pass this codec. The numeric instance
is bring-up source, not the final object-key representation. No target storage
service, AES-GCM binding, independent checkpoint verifier, durable nonce
reservation, journal publication, persistent reopen or index-refinement verdict
is supplied here. M5.3d retains those joins and the complete two-instance campaign
under [the recovery contract](../docs/implementation/storage-recovery-policy.md).

`python tools/run.py test --only storage_node_image` discovers the focused
behavioral module. Its native C cases run on Linux, including Host CI's Ubuntu
runner; Windows still checks the pure byte oracle. The
[native seam](host/node_image.c) lets that module compare encoded bytes with an
independent Python byte oracle, decode independently generated blocks, and check
malformed inputs without changing caller outputs. Compiled behavioral mutations
must fail their specified controls; a compile failure supplies no mutation kill.
