# What the switch emits, by digest

The emitted C is not tracked: bedrock2's printer prepends its own load-and-store preamble to every module, which is bedrock2's text under bedrock2's terms, and the C is regenerated rather than kept. What is tracked is enough to know whether a regeneration reproduced it: the SHA-256 of the file, its size in bytes, and its line count, each taken over the bytes between the two quotes of the prover's `Redirect` output, which is exactly the string `c_module` returns and one trailing newline fewer than the `sed` cut M1.6's note measured with. `regenerate.py --check` recomputes the three and exits `1` where any of them differs from its row here or where a file has no row.

| File | SHA-256 | Bytes | Lines |
| --- | --- | --- | --- |
| `descriptor_check.c` | `3d85721281062243511867fe073235be624717ca6e6db3517f4fb9419a849136` | 7874 | 202 |
| `ip_checksum.c` | `11fdf341d60b29be82c8132456f3bb55db87a1fde40c0c9cb1e719dfa3415e6c` | 2340 | 62 |
| `frame_kernel_retained.c` | `4fd65a967050f1ce5b0f9992a899305f2882e1268cc3a5ee11177389eabf3fc4` | 2033 | 53 |
| `frame_kernel_inplace.c` | `a250be67842ac8e904beae6c7d53308b97ab1653fa50838060cbfdb447e0ea7e` | 2014 | 53 |

The first two rows are taken at `287625b`, the commit those two sources stand at. The first is the descriptor check derived from [DescriptorCheck.v](DescriptorCheck.v) over the [generated interface artifact](../../proofs/RingContract.v) as both stand in the index; the second is Rupicola's shipped `ip_checksum`, emitted by [IpChecksumBaseline.v](IpChecksumBaseline.v) as the yardstick. A row moves when its source moves, when the owner the source reads moves, or when a package in the switch moves, and the `--check` that reports it says which file drifted and by how much.

The last two rows are the frame-kernel census pair, [FrameKernelRetained.v](FrameKernelRetained.v) and [FrameKernelInPlace.v](FrameKernelInPlace.v), each emitted by `regenerate.py --source <file> --function <name>` into a stage of its own. Neither imports an owner, so only a source edit or a package move drifts them; the `--owner` the driver compiles first is beside the point for these two and is left at its default. The two differ by 19 bytes and not one line: their C is the same program with the output writes and the second pass sent to a second pointer, which is exactly the difference the census below reads. **Their `--check` has been run in a second stage and not from a second checkout**, so what it establishes for these two rows is that the digest is a property of the input rather than of the stage, and the stronger reading the paragraph above records for the first two rows is not yet taken for them.

## The plain-RV64 census

What the contained `ccomp` emits from each of those files, at `-S` and at `-S -dcapasm`, printed by the same run that takes the digest above. **This is a proxy, not a target measurement.** The target is plain RV64 with the capability arms stubbed, which R-18-002 forbids, and the stub count in the last column is the size of that gap rather than a property of the program. Instructions and distinct mnemonics use the driver's `^\s+[a-z][a-z0-9.]*` predicate over the `.s`; loads and stores are the named RV64 access mnemonics, `lb lbu lh lhu lw lwu ld flw fld` and `sb sh sw sd fsw fsd`; branches are the mnemonics beginning with `b`, so `call`, `j`, `jal`, `jalr`, `ret` and `tail` are outside that count. The `TODO` column is the `-dcapasm` term's stubbed arms, with the number of distinct arms in parentheses.

| Assembly | Lines | Instructions | Mnemonics | Loads | Stores | Branches | `-dcapasm` TODO |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `descriptor_check.s` | 309 | 254 | 21 | 30 | 10 | 34 | 115 (16) |
| `ip_checksum.s` | 148 | 120 | 26 | 20 | 17 | 7 | 53 (20) |
| `frame_kernel_retained.s` | 158 | 124 | 23 | 23 | 20 | 7 | 46 (18) |
| `frame_kernel_inplace.s` | 157 | 123 | 23 | 23 | 19 | 7 | 46 (18) |

The census is per program and not per length: both kernels take their length as a runtime argument and emit two `while` loops, so no figure in their rows moves with the frame size. That is the first thing this census does not share with [the transformation experiment](../../docs/implementation/static-memory-transformations.md), whose schedule is unrolled at a public length and whose instruction count therefore grows with it.
