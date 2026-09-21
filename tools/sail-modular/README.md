# Optional generated Sail static libraries

`python tools/run.py sail-modular qualify` derives four method translation units
and a single shared owner from the full pinned Sail 0.20.2 C++ model, then builds
them as static libraries with an isolated CMake overlay. On Linux use `python3`.
Run `model build` first to obtain the current lane's successful baseline receipt.
`--partitions` accepts 2 through 16; `--json` prints the complete report conforming
to [the schema](report.schema.json).

The optional native prerequisite is LLVM/libclang 21.1.8, read through its stable
C API with authored Python standard-library `ctypes` bindings. No Python binding,
compiler upgrade or automatic package installation is involved. Its license is
[Apache-2.0 with LLVM exceptions](https://github.com/llvm/llvm-project/blob/llvmorg-21.1.8/LICENSE.TXT).
Provision the library explicitly alongside the existing Clang toolchain. The
qualification host uses Ubuntu's `libclang1-21` package version
`1:21.1.8-6ubuntu1`; on that distribution the explicit provisioning command is
`sudo apt-get install libclang1-21=1:21.1.8-6ubuntu1`. Other supported native
images must supply the same LLVM 21.1.8 library explicitly; the command refuses
other versions and never runs a package manager. CMake
3.24 or later with the Linux RESCAN link-group feature is required. Stage resource
measurements use the operating system's `wait4`, with no timing-tool dependency.
Its peak RSS is the maximum child/descendant value, not the sum of concurrent
compiler processes; it does not establish aggregate build-memory savings.
The qualification report records the exact library, tool and header hashes.

Libclang supplies complete declaration and body byte ranges. The partitioner
retains every method exactly once, byte-for-byte. It declares namespace globals
as `extern` in the shared header and retains their sole definitions in the owner.
Internal helper functions lose only their `static` linkage token and receive
compiler-range-derived prototypes; their bodies and sole definitions stay in the
owner. No model state is duplicated. Initializers and declarator shapes beyond
the compiler-described type/name form, unexpected namespace declarations,
conditional preprocessing, invalid ranges and incomplete membership refuse.

Each run has a fresh native directory under the assigned lane's `sail-modular/`.
Generated code is intentionally untracked. Native logs go under `/root/logs` in a
directory carrying the lane and run identity. `partition.json` identifies every
method and output; `qualification.json` records the baseline receipt, full CTest
comparison, frozen differential-corpus trace comparison, stage timings and peak
resident memory. Both measured builds use clean objects with the compiler cache
disabled and the same bounded job count. The baseline is rebuilt after capturing
header hashes. Source/tool identities are checked again before publication.
Header or generated-input changes refuse reuse even if timestamps are preserved.
The post-build Ninja dependency closure must match the captured inputs; an
uncaptured header refuses qualification and requires a refreshed baseline. The
partitioned build's corresponding dependency files must also have baseline bytes.
CTest captures up to 100 MiB per test and refuses any truncated output. Outputs
must agree after replacing only their build-directory paths, and
every corpus member must match both the frozen trace and the other emulator's
full output. A nonzero stage exit leaves its log and timing record, and the run writes
`last-failure.json`; only a completed passing comparison publishes `latest.json`.

Qualification does not establish a theorem, an independently verified module ABI,
dynamic extension loading, or a speedup. It measures finite-corpus agreement with
the ordinary full-model build. The ordinary build recipe remains available.
