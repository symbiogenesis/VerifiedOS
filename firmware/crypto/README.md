# Boot signature verification

[slh256s.c](slh256s.c) implements SLH-DSA-SHAKE-256s verification from
[NIST FIPS 205](https://doi.org/10.6028/NIST.FIPS.205), including WOTS+, FORS,
XMSS and the hypertree. [mldsa87.c](mldsa87.c) implements ML-DSA-87 verification
from [FIPS 204](https://doi.org/10.6028/NIST.FIPS.204) and the repository's
[functional reference](../../proofs/MlDsa.v). Both are original Apache-2.0 C
using [keccak.c](keccak.c), fixed local arrays, bounded loops and no allocation.
The ML-DSA matrix and challenge samplers refuse when the reference's finite
budgets are exhausted. No sampler manufactures missing coefficients.

[vos_signature.h](../include/vos_signature.h) separates the internal message,
pure contextual message and ML-DSA external-mu interfaces. Pure verification
binds the context prefix; internal verification adds no prefix. Neither accepts
prehash dispatch. The byte-message resource limit is 65536 bytes and context
length is at most 255 bytes. These bounds belong to the C interface, not FIPS.
Exact key/signature lengths are checked before reading them. Caller storage
must remain readable and immutable for the entire call.

`vos_boot_slh256s_verify` binds the existing `vos_rot_policy.verify` callback to
FIPS 205 Algorithm 20 over exactly the fixed signed boot prefix. Static
assertions bind its signature and root sizes to the boot layout owner. The
boot harness selects it with `python tools/run.py boot-handoff run
--signature-scheme slh256s`, including the input-race control and main-die
emulation from the released bytes. The default fixture mode stays explicit.
The independent comparison campaign is `python tools/run.py boot-crypto run --gallina`.

Keccak keeps its unchanged round constants in a bounded local array and expands
the fixed theta, rho/pi and chi topology with scalar lane locals and literal
rotation offsets in a nonrecursive round helper. This removes repeated indexed
array addressing from the scalar RoT binary without changing
the algorithm, 24-round count or input bounds. Local storage fits the accepted
purecap compiler's scalar-global profile.
The [target translation unit](../harness/slh_target.c) and `boot-handoff
signature-target` retain a bounded RoT-profile trial with real header inputs.
Compilation or an instruction-limited run without an HTIF verdict supplies no
signature target acceptance.

The campaign compiles host C with warnings as errors, freestanding options and
AddressSanitizer/UndefinedBehaviorSanitizer. It compares every applicable
byte-oriented pure, internal and external-mu verification input in pinned NIST
ACVP files, records excluded prehash/partial-byte inputs, and compares positive
and corrupted signatures with installed OpenSSL 3.5.5. `--gallina` additionally
extracts the exact ML-DSA reference and compares each selected interface and its
refusals. It also compares streaming SHAKE256 against `Keccak.v` and Python's
independent digest over empty inputs and absorb/padding/squeeze rate boundaries.
`--first` runs one positive per scheme as an explicitly incomplete
development checkpoint. Neither option can claim target acceptance.

`boot-crypto target` compiles [signature_target.c](signature_target.c) through
the accepted contained compiler and executes all five real signature interfaces
on the scalar RoT profile. It takes `--ccomp` with repeated `--ccomp-arg` options,
or `--staged` for the [staged streams](#staged-target-streams), and `--simulator`
and `--build-receipt`. The compiler's native `build-result.json` and
`build-inputs.json` must bind its executable and unchanged source archive.
The target population is one pinned ACVP positive per interface and each
applicable authored corruption, root, message, context and length refusal.
The full host population remains separately recorded. `--first` selects only
the positive target cases and cannot establish that refusal coverage. Repeated
`--mode` options select interfaces; a receipt covering fewer than five records
its selection and is complete only as a shard of a joined campaign.
Exact ABI lengths accompany bounded read-only input capabilities. Timeout,
instruction exhaustion and traps supply no signature decision. The report
binds source, compiler, model, input, assembly, ELF and log identities and records
unexecuted cases. Firmware release and the complete boot chain retain their
separate joins.

The crypto composition reserves an exactly aligned 32 KiB stack and refuses
a compiler stream whose conservative sum of function frames exceeds it.
`--jobs` permits one to six isolated target cases. All selected interfaces
compile or load before execution, and each interface's accepted positive gates
its refusal controls. Final records use population order regardless of completion
order. Duplicate, contradictory and malformed HTIF lines refuse the run.

The same campaign generates an authored header signature using OpenSSL and
tests the actual RoT release with a valid image, a corrupted signature, a wrong
root, an over-length payload field and a corrupted payload. A refused image
must leave zero payload storage, unchanged handoff storage and no release call.
The over-length field must refuse before signature verification. These checks
do not execute the RoT hart or the main-die handoff.

Downloads stay in the native lane with pinned hashes and complete source
notices. The NIST ACVP source is revision
`975de31eb83d87039ec88934fdc47d8c312b892d`, which
[the pin owner](../../tools/vos/acvp.py) holds with each fetched file's SHA-256;
its README notice grants use and copying with attribution and the notice
retained. No NIST or OpenSSL implementation is incorporated.
[THIRD-PARTY.md](../../THIRD-PARTY.md) records the source/license boundary. The receipt binds source bytes before and after
the run, the C compiler and executable, OpenSSL and its libraries, vector
revision/digests and optional Gallina extraction. A workspace lock protects
shared campaign files. Starting or failing a rerun replaces a previous passing
report with an incomplete or failed status.

`python tools/run.py test --only boot_crypto` runs offline adapter and receipt
controls. Its native cases compile C, accept both public fixtures and refuse
their corrupted neighbors as well as invalid lengths and all-zero signatures.
The [fixtures](fixtures.json) are authored inputs signed by OpenSSL, not NIST
vectors or copied implementation. Each uses the message
`VerifiedOS offline signature acceptance fixture`, a zero byte, then all byte
values in order; the context is `VerifiedOS`, zero, then byte 255. The recipe is
`openssl genpkey -algorithm SLH-DSA-SHAKE-256s` (respectively `ML-DSA-87`),
`openssl pkey -pubout -outform DER`, and `openssl pkeyutl -sign` with
`-pkeyopt hexcontext-string:56657269666965644f5300ff`. Random generated signing
keys are disposable test inputs and are absent from the fixture file. The
file records the generator executable/library identities and notice hashes;
the full campaign rechecks its positive and corrupted signatures against
OpenSSL and, for ML-DSA, Gallina when selected.

The qualified vector/oracle campaign is separate from Host CI and
Guest CI. Host execution and comparison are functional evidence. Target
lowering, firmware execution on the RoT composition, binary refinement,
constant-time and masking claims remain open under M7.1f and its joins.

## Staged target streams

`python tools/run.py boot-crypto stage --ccomp PATH --ccomp-arg=ARG` compiles
all five interfaces through the contained compiler, applies the dialect and stack
checks and writes [target/](target/): one stream per interface, each a three-line
generated header followed by the compiler's exact bytes, and
[manifest.json](target/manifest.json). The manifest binds each stream's SHA256,
path-free compile arguments and frame sum, the compiler build's revision and
executable and receipt digests, the configuration file's digest and every checkout
file that the preprocessor's line markers name. It also lists by name every file in
the checkout directories an include can search, each read file's own directory and
each `-I` directory, so an added header that would shadow a read one also counts as
a change. A source that changes between two interfaces' compilations refuses the
staging. `--check` recompiles and compares without writing. Staging runs only where the contained compiler is provisioned;
its native `stage.json` keeps the literal arguments and preprocessed-unit digests,
which name that checkout's paths.

`boot-crypto verify` holds the tracked files to their manifest and to this
checkout's sources on either lane. `boot-crypto target --staged` executes them
instead of compiling. It refuses compiler arguments, a changed bound source, an
added or removed file in a searched directory, an altered stream or header, a
missing or unowned file and a frame sum that disagrees with the manifest, and it
repeats the dialect and stack checks. Its receipt records `"compilation": "staged"`
and the manifest's digest. The compiler's provenance is the staging record, not a
check made where the streams execute. Editing a bound source, or adding, removing
or renaming a file in a searched directory, makes the streams stale until they are
staged again; editing an unread file there, such as this README, does not.

## Hosted target campaign

[boot-crypto-target.yml](../../.github/workflows/boot-crypto-target.yml) executes
the complete campaign from the staged streams on GitHub-hosted Linux. Pushes to
`main` that change [target/](target/) or the workflow start it; manual dispatch
accepts a revision already on `main` and a per-case timeout of at most 9,600 s,
9,000 s by default, so that a positive and its refusals fit the execution step.
One campaign runs at a time, and a newer run cancels an older one, queued or
running, which then joins no receipt. Each interface runs on its own runner with
`--mode` and `--jobs 4`, so its positive still gates its refusals. Each runner
verifies the streams, restores Guest CI's
model-lane toolchains and Sail memo read-only, and builds the model for its
simulator and build receipt. `boot-crypto join` then composes the five receipts:
every interface exactly once, identical source, model, manifest, compiler and
vector identities, verdicts that agree with their cases, and unexecuted cases
listed. A failed case fails the joined receipt; an inconsistent set is refused.
The run retains each interface's receipt and logs and the joined `report.json`
for 30 days. A passing joined receipt is target execution evidence for the staged
streams at its revision; the firmware join and the limits above remain.
