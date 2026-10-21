# Finite rank-48 identity replay

This is the accepted scope for an independent exact check of the ordinary
`4x4x4_48_204` construction cited by the [survey](open-math-conjectures.md).
The host `matrix-identity` command consumes the six explicitly supplied PLinOpt
`.sms` and `.slp` files for L, R and P. It never executes those programs as
Python or compiles upstream software. Inputs stay outside this repository.

Acceptance requires strict parsing of sparse rational matrices and a bounded
linear straight-line language; duplicate entries, undefined variables,
overwritten variables, unknown syntax, extra outputs, wrong dimensions and
nonlinear operations are refused. Exact rational symbolic interpretation must
match each program to its matrix. Every coefficient of every output bilinear
form must equal ordinary row-major 4 by 4 matrix multiplication. The report
counts additions/subtractions, non-unit scalings and bilinear products
separately; copies are free in this algebraic count. A corrupted coefficient
and a corrupted program must each fail independent checks.

The retained report binds all six input hashes, the immutable upstream revision
and the local checker source hashes. Replay from a supplied directory works
offline. Fetching the pinned inputs, when explicitly requested, uses a unique
system temporary directory and hash-checks every file against the recorded
input manifest. Tests use small authored identities and negative cases; no
benchmark, external proof replay or target implementation is implied.

This checks a finite rational identity and its straight-line operation count.
It supplies no Rocq theorem, compiler correspondence, floating-point equality,
numerical stability, target timing, bounded scratch implementation or approval
to replace the frozen FP32 pilot. Alternative-basis recursion costs are outside
this ordinary-basis replay. Q30g still owns any later arithmetic slice.
