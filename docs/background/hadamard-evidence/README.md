# Exact checks of twelve finite Hadamard matrices

This directory retains the reproducible evidence behind the finite-order claim in
the [open mathematics survey](../open-math-conjectures.md#hadamard-matrix-conjecture).
It checks twelve compressed CSV matrices from the public `hoa64` mirror at commit
[`d825201089123126ce792d4921cba4ae1b8977a3`](https://github.com/bbeartheancient/hoa64/tree/d825201089123126ce792d4921cba4ae1b8977a3/matrices).
The source bytes are downloaded only for a local run; this repository does not
redistribute the matrices.

| File | Role |
| --- | --- |
| [manifest.json](manifest.json) | The complete twelve-file scope, pinned URLs, and expected SHA-256 digests of both compressed and decoded bytes |
| [verify.py](verify.py) | Exact verifier and report generator |
| [verification.json](verification.json) | Deterministic result generated from the manifest and matrix bytes |

From the repository root, with Python 3.10 or later:

```console
python docs/background/hadamard-evidence/verify.py --input-dir out/hadamard-inputs --download
python docs/background/hadamard-evidence/verify.py --input-dir out/hadamard-inputs
```

The first command fetches each pinned URL, checks its compressed digest before
saving it, checks the decoded digest, and verifies the matrix. The second command
rechecks the retained files without network access. Both compare their computed
results with `verification.json` and fail on any mismatch. `--write-report` is
available when intentionally regenerating the tracked report after a reviewed
change to the manifest or verifier.

The verifier requires square dimensions, literal `1` or `-1` entries, and Hamming
distance `n/2` for every distinct row pair. Those exact-integer checks establish
`H H^T = n I` for each supplied matrix. An order-4 positive control and a
one-bit-corrupt negative control exercise the checker. The evidence says nothing
about all multiples of four or the availability of a fast transform. Order 1852
appeared in the earlier download list but was not among the twelve verified and
cited matrices; it is outside this record's scope.
