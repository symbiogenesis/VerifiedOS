# ML-KEM functional reference campaigns

These campaigns exercise [MlKem.v](../MlKem.v), [PqArith.v](../PqArith.v) and [Keccak.v](../Keccak.v). The [PQ acceptance contract](../../docs/assurance/pq-reference-contract.md) separates functional behavior from computational security, target refinement, constant time and masking. Standard vectors, an independently executed implementation, native theorem auditing and generated mutations are distinct evidence.

Run the commands in the assigned WSL native lane. Sources stay in the verified Windows worktree; generated OCaml, compiled proofs, downloaded vectors, test keys and receipts stay under its `/root/build/lane-...` directory. No upstream algorithm code is copied or installed by these campaigns. Set the paths to the lane assigned by the integrator:

```bash
repo=/mnt/c/Users/symbi/source/repos/VerifiedOS/.worktrees/NAME
lane_root=/root/build/lane-NAME
build="$lane_root/scratch/pq-reference"
opam_bin=/root/.opam/verifiedos-rocq-9.2.0-ocaml-5.4.1/bin
export PATH="$opam_bin:$PATH"
mkdir -p "$build/proofs"
cp "$repo/proofs/PqArith.v" "$repo/proofs/Keccak.v" "$repo/proofs/MlKem.v" "$build/proofs/"
cd "$build"
rocq c -q -Q proofs '' proofs/PqArith.v
rocq c -q -Q proofs '' proofs/Keccak.v
rocq c -q -Q proofs '' proofs/MlKem.v
```

Compilation must succeed before proceeding. The campaign checks that source bytes match the staged modules, and records both source and `.vo` hashes. Native inventory, assumption closure, required record witnesses and `rocqchk` remain the separate proof gate's responsibility; a passing executable comparison does not establish any of them.

Run every official ML-KEM-1024 group, additional positive decapsulations, hash boundary checks and generated malformed-seed checks:

```bash
python3 -B "$repo/proofs/campaigns/mlkem_vectors.py" \
  --repo "$repo" --build "$build" --opam-bin "$opam_bin"
```

The script extracts actual Gallina, including local Keccak, through the standard OCaml integer adapters and links Zarith. It downloads the official NIST ACVP-Server revision `975de31eb83d87039ec88934fdc47d8c312b892d`, preserving the whole upstream README license notice and input hashes under `vectors/`. The expected answers are external official data. The optional `--limit` is for diagnosis; the acceptance run omits it and produces 154 checks. `mlkem-vector-receipt.json` records exact case IDs, comparison hashes, commands and exit status. OCaml extraction, native integers, Zarith and host execution are unproved execution boundaries, not target implementation artifacts.

Run the separate OpenSSL implementation on newly generated public test inputs:

```bash
python3 -B "$repo/proofs/campaigns/mlkem_openssl.py" \
  --repo "$repo" --reference "$build" \
  --build "$lane_root/scratch/mlkem-openssl" --cases 25
```

This requires the preceding successful vector receipt and unchanged source/executable hashes. The qualified local oracle is OpenSSL 3.5.5, upstream revision `67b5686b4419b4cb8caa502711c41815f5279751`, Apache-2.0, invoked as an external executable with its default provider. A different version requires renewed qualification. The script records the installed package notice, binary/library identities, individual commands and 225 comparisons: exact keygen and deterministic test encapsulation outputs, decapsulation in both implementation directions, altered-ciphertext implicit rejection, and paired short/long ciphertext refusal. OpenSSL's seed and `ikme` controls are used only for reproducible public tests. Test fixtures and `mlkem-openssl-receipt.json` remain in the native build directory.

Run the focused generated mutation set after the same-source baseline campaigns pass:

```bash
python3 -B "$repo/proofs/campaigns/crypto_mutations.py" \
  --repo "$repo" --baseline "$build" \
  --build "$lane_root/scratch/crypto-mutations" --opam-bin "$opam_bin"
```

The script reads the owned ProbingModel source alongside PqArith and MlKem. It generates selected changes through the repository mutation engine and generic equality/group-operation rewrites. A definition-prefix compile separates stillborn changes. PqArith and ProbingModel then use native theorem/example compilation as their oracle; ML-KEM uses definitions-only extraction and official runtime comparisons. `proof-killed` and `vector-killed` are separate verdicts. Compilation failures and timeouts do not count as kills; any survivor requires investigation. The receipt names each selected definition, operator, source hash, tested case and verdict.

The `.v.in` and `.ml.in` files are extraction/driver templates. They are copied into native output directories before compilation and are not additional standalone proof modules. The scripts perform no full-repository gate, shared-ledger repair, package installation or production key operation.
