# What the switch emits, by digest

The emitted C is not tracked: bedrock2's printer prepends its own load-and-store preamble to every module, which is bedrock2's text under bedrock2's terms, and the C is regenerated rather than kept. What is tracked is enough to know whether a regeneration reproduced it: the SHA-256 of the file, its size in bytes, and its line count, each taken over the bytes between the two quotes of the prover's `Redirect` output, which is exactly the string `c_module` returns and one trailing newline fewer than the `sed` cut M1.6's note measured with. `regenerate.py --check` recomputes the three and exits `1` where any of them differs from its row here or where a file has no row.

| File | SHA-256 | Bytes | Lines |
| --- | --- | --- | --- |
| `descriptor_check.c` | `3d85721281062243511867fe073235be624717ca6e6db3517f4fb9419a849136` | 7874 | 202 |
| `ip_checksum.c` | `11fdf341d60b29be82c8132456f3bb55db87a1fde40c0c9cb1e719dfa3415e6c` | 2340 | 62 |

Both rows are taken at `287625b`, the commit these sources stand at. The first is the descriptor check derived from [DescriptorCheck.v](DescriptorCheck.v) over the [generated interface artifact](../../proofs/RingContract.v) as both stand in the index; the second is Rupicola's shipped `ip_checksum`, emitted by [IpChecksumBaseline.v](IpChecksumBaseline.v) as the yardstick. A row moves when its source moves, when the owner the source reads moves, or when a package in the switch moves, and the `--check` that reports it says which file drifted and by how much.
