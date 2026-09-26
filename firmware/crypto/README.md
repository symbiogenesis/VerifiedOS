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
existing fixture boot harness remains useful for its race controls; the real
binding has a separate campaign in `python tools/run.py boot-crypto run --gallina`.

The campaign compiles host C with warnings as errors, freestanding options and
AddressSanitizer/UndefinedBehaviorSanitizer. It compares every applicable
byte-oriented pure, internal and external-mu verification input in pinned NIST
ACVP files, records excluded prehash/partial-byte inputs, and compares positive
and corrupted signatures with installed OpenSSL 3.5.5. `--gallina` additionally
extracts the exact ML-DSA reference and compares each selected interface and its
refusals. `--first` runs one positive per scheme as an explicitly incomplete
development checkpoint. Neither option can claim target acceptance.

The same campaign generates an authored header signature using OpenSSL and
tests the actual RoT release with a valid image, a corrupted signature, a wrong
root, an over-length payload field and a corrupted payload. A refused image
must leave zero payload storage, unchanged handoff storage and no release call.
The over-length field must refuse before signature verification. These checks
do not execute the RoT hart or the main-die handoff.

Downloads stay in the native lane with pinned hashes and complete source
notices. The NIST ACVP source is revision
`975de31eb83d87039ec88934fdc47d8c312b892d`; its README notice grants use and
copying with attribution and the notice retained. No NIST or OpenSSL
implementation is incorporated. [THIRD-PARTY.md](../../THIRD-PARTY.md) records
the source/license boundary. The receipt binds source bytes before and after
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
