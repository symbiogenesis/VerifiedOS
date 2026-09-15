# ML-DSA-87 functional reference campaign

[MlDsa.v](../MlDsa.v) implements the selected pure ML-DSA-87 operations under the [post-quantum reference contract](../../docs/assurance/pq-reference-contract.md), using the local PqArith and Keccak references. This is authored Gallina source. No NIST, libcrux, HACL* or Dilithium implementation body is copied. The algorithms are key generation, bounded hedged signing and verification, with the FIPS 204 decomposition, challenge and hint encodings. The selected API has no HashML-DSA prehash dispatcher. The campaign rejects a prehash request and excludes those explicitly enumerated official groups.

The normative edition is [FIPS 204, 2024-08-13](https://doi.org/10.6028/NIST.FIPS.204). The [potential-updates workbook](https://csrc.nist.gov/files/pubs/fips/204/final/docs/fips-204-potential-updates.xlsx), last updated 2026-07-31, was independently read on 2026-09-15. Its SHA-256 is `5bc93ce63bc647e6d1d456cb2d3a171426c15aca4a7a0e0edd40d08b7a34c793`. This is a potential update, not another publication edition. The implementation adopts its larger 821-attempt signing limit because the workbook accounts for an additional rejection condition; the 2024 table prints 814. It also follows the algorithm's `mu || w1` hash order and single polynomial evaluation in the NTT, agreeing with the workbook's explanatory corrections. The implementation uses integer modular arithmetic, so the Montgomery-reduction prose correction does not apply to its arithmetic route.

The public interfaces are `dsa_keygen seed`, `dsa_sign sk context message_bits rnd` and `dsa_verify pk context message_bits signature`. Exact byte lengths are seed 32, public key 2592, secret key 4896, signature 4627 and hedging input 32; every byte is an integer in 0..255. Contexts have at most 255 bytes. The pure wrapper hashes the prescribed zero byte and context length/context prefix before the bit message. `dsa_sign_internal` and `dsa_verify_internal` receive the already formatted bit message. `dsa_sign_mu` and `dsa_verify_mu` receive a 64-byte message representative and are explicit testing/composition interfaces; they do not authenticate its provenance. A bit message need not end at a byte boundary.

`DsaInvalid` distinguishes malformed public input from `DsaExhausted`, which means a finite sampler or signing budget supplied no result. Matrix, secret and challenge samplers consume at most 894, 481 and 221 SHAKE bytes per polynomial or challenge. Rejected candidates are skipped; exhaustion fabricates no coefficient and emits no partial polynomial or signature. The named zero-fuel test helper can demonstrate exhaustion. Production callers must provide approved hedging randomness: the all-zero deterministic input used by official tests carries no authorization for deterministic production signing.

The module's general theorems state refusal for bad seed/key lengths or contexts, the verifier's strict decoded-response bound, and the zero-budget outcome. PqArith separately owns the general transform and byte-codec inverse theorems at their shape, modulus and bound premises. The native campaign is execution evidence through standard Rocq extraction, OCaml and Zarith. It executes the actual local Keccak bit-list source, with no hashlib/OpenSSL substitution. Extracted natural numbers use host integers; this finite campaign's dimensions, nonces and messages fit their range. The generated OCaml, extracted standard-library bodies, compiled executable and downloaded vector files remain ignored native outputs. These results are not an extraction-correctness theorem, a complete scheme-correctness proof, a security reduction, constant-time or masking evidence, target refinement, Wasm integration, or production key-storage qualification. The independent implementation campaign uses OpenSSL rather than libcrux/HACL*.

## Official inputs and reproduction

The source is [NIST ACVP-Server revision 975de31eb83d87039ec88934fdc47d8c312b892d](https://github.com/usnistgov/ACVP-Server/tree/975de31eb83d87039ec88934fdc47d8c312b892d). The selected revision's complete README license notice was read and is retained in [the NIST notice below](#nist-vector-notice); the campaign acknowledges NIST. Its README SHA-256 is `d5a569884ee83bd1c4737042d0a2cc7d68c6950690f75a73ef14f505a9aa3555`. Downloaded vector values are unmodified. The campaign code is authored separately under Apache-2.0.

[mldsa_vectors.py](mldsa_vectors.py) pins the SHA-256 of each official `gen-val/json-files/ML-DSA-{keyGen,sigGen,sigVer}-FIPS204/internalProjection.json` and refuses cached or downloaded bytes that differ. The full run selects all 25 ML-DSA-87 key-generation records, all 90 pure/internal/external-mu signing records and all 45 verification records for those supported interfaces. The receipt names every selected `tgId`/`tcId`, input source hash, expected validity and comparison result. Key generation compares both complete key byte strings; signing compares the complete signature and additionally verifies it; verification compares the official boolean. The three prehash groups are recorded as exclusions. No authored boundary test is labeled as a standard vector.

Run inside the assigned WSL lane, replacing the lane name with its verified assignment:

```text
python3 proofs/campaigns/mldsa_vectors.py --work /root/build/lane-<assignment>/proofs --jobs 2
python3 proofs/campaigns/mldsa_mutations.py --baseline /root/build/lane-<assignment>/proofs --work /root/build/lane-<assignment>/mutants
```

The first command compiles source, extracts and links the executable, runs the corpus and authored refusal cases, and writes `receipt.json` plus native compilation/extraction logs. The mutation command requires the passing receipt for identical source, compiles each selected semantic mutant, and compares its execution with the official key/signature or positive-verification oracle. A compilation failure is stillborn, not a kill. A surviving compiled mutant remains a reported sensitivity gap. It does not claim exhaustive mutation coverage. The broader proof gate remains responsible for complete constant inventory, assumptions and kernel recheck in the integrated tree.
## Independent executable oracle

[mldsa_openssl.py](mldsa_openssl.py) compares the extracted reference with the installed OpenSSL 3.5.5 default provider, Ubuntu package `3.5.5-1ubuntu3.5` on ARM64 in the recorded run. The [OpenSSL release license](https://github.com/openssl/openssl/blob/67b5686b4419b4cb8caa502711c41815f5279751/LICENSE.txt) was read at the `openssl-3.5.5` tag's resolved commit `67b5686b4419b4cb8caa502711c41815f5279751`: Apache-2.0, SHA-256 `7d5450cb2d142651b8afa315b5f238efc805dad827d91ba367d8516bc9d49e7a`. The installed package copyright was also read; its application and Debian packaging entries are Apache-2.0. The unused `external/perl/Text-Template-1.56/*` entry carries Artistic or GPL-1+ terms. The receipt hashes the actual executable, libcrypto, libssl and installed copyright; the Ubuntu build is not represented as an unmodified upstream binary. No OpenSSL implementation, binary or generated test key is incorporated into the tracked tree.

The harness authors only public test inputs, DER key framing and calls to [OpenSSL's documented ML-DSA API](https://docs.openssl.org/3.5/man7/EVP_PKEY-ML-DSA/). Three fixed public seeds and hedging inputs exercise exact key and signature byte comparisons, both cross-verification directions, and agreement on refusal of changed message/context/challenge/public key, a response exactly at the forbidden bound, an overflowing hint endpoint and a short signature. Both implementations compute the cryptography themselves. The byte-oriented OpenSSL interface does not independently cover partial-byte bit messages; that source interface has a separately labeled authored roundtrip/refusal test in the Gallina execution campaign. OpenSSL setup or API errors are reported as failures, not counted as signature refusals.

```text
python3 proofs/campaigns/mldsa_openssl.py --baseline /root/build/lane-<assignment>/proofs --work /root/build/lane-<assignment>/openssl
```
## NIST vector notice

Verbatim notice from the pinned ACVP source; its terms govern the supplied NIST data.

> Official ML-DSA test data source: NIST ACVP-Server
> Revision: 975de31eb83d87039ec88934fdc47d8c312b892d
> Acknowledgment: the vector data were developed by NIST.
> The campaign selects records without modifying their test values.
> No NIST implementation source is incorporated.
>
> ## License
>
> NIST-developed software is provided by NIST as a public service. You may use, copy, and distribute copies of the software in any medium, provided that you keep intact this entire notice. You may improve, modify, and create derivative works of the software or any portion of the software, and you may copy and distribute such modifications or works. Modified works should carry a notice stating that you changed the software and should note the date and nature of any such change. Please explicitly acknowledge the National Institute of Standards and Technology as the source of the software.
>
> NIST-developed software is expressly provided "AS IS." NIST MAKES NO WARRANTY OF ANY KIND, EXPRESS, IMPLIED, IN FACT, OR ARISING BY OPERATION OF LAW, INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTY OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT, AND DATA ACCURACY. NIST NEITHER REPRESENTS NOR WARRANTS THAT THE OPERATION OF THE SOFTWARE WILL BE UNINTERRUPTED OR ERROR-FREE, OR THAT ANY DEFECTS WILL BE CORRECTED. NIST DOES NOT WARRANT OR MAKE ANY REPRESENTATIONS REGARDING THE USE OF THE SOFTWARE OR THE RESULTS THEREOF, INCLUDING BUT NOT LIMITED TO THE CORRECTNESS, ACCURACY, RELIABILITY, OR USEFULNESS OF THE SOFTWARE.
>
> You are solely responsible for determining the appropriateness of using and distributing the software and you assume all risks associated with its use, including but not limited to the risks and costs of program errors, compliance with applicable laws, damage to or loss of data, programs or equipment, and the unavailability or interruption of operation. This software is not intended to be used in any situation where a failure could cause risk of injury or damage to property. The software developed by NIST employees is not subject to copyright protection within the United States.
