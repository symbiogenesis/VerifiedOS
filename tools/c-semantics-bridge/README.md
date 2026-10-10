# Private Clight bridge statement

[Bridge.v](Bridge.v) states Q35j's proposed forward simulation from the stock
Clight 3.17 subset bundled by VST 2.17 to the accepted contained compiler's
compartment Clight. The [assurance record](../../docs/assurance/c-semantics-bridge.md)
owns its scope, front-end premise, incorporation terms, evidence and proof plan.
`bridge_statement` is a proposition with a body, not a theorem or an axiom.
No simulation proof or source-level foundation is admitted by this instrument.

The author supplies the two existing private source directories and an existing
private switch. The switch's package set and the shared proof switch are unchanged.
`check.py` copies the selected sources into a native lane, resolves only each
Clight module's dependency closure, compiles the unchanged libraries under
different logical namespaces, then compiles the authored statement and the
concrete witness/refusal lemmas with strict diagnostics. Upstream legacy warning
suppression is recorded and is not an acceptance setting for authored proofs.
The script emits the complete source identities, prover version and compile logs.
It executes no benchmark or complete project gate.

Run from the assigned checkout in the guest, with absolute guest-native paths:

```console
python3 tools/c-semantics-bridge/check.py \
  --stock /root/build/lane-NAME/c-semantics/stock \
  --contained /root/build/lane-NAME/c-semantics/contained \
  --flocq /root/.opam/PRIVATE-SWITCH/.opam-switch/sources/coq-flocq.4.2.2/src \
  --output /root/build/lane-NAME/c-semantics/check \
  --switch PRIVATE-SWITCH
```

The recorded run uses `--switch verifiedos-q35e-vst3-20260928 --coq-bin /usr/bin`
to invoke the existing Coq 8.20.1 binaries inside a private switch execution
environment. The explicit override is necessary because unchanged contained
`Memory.v` refuses Rocq 9.3.0 and 9.2.0. This is a legacy statement instrument,
not a result under the shared locked prover. `--statement-only` can resume the
authored compilation only after the prover version and every imported source
and object hash agree with the preceding `upstream-report.json` receipt.

The contained source is a private archive of revision
`1cd36c710967e89db21da08f237ffca78843b883`, obtained from the contained repository
under M1.1a. Stock sources are the CompCert 3.17 subset in VST 2.17's release
archive. Neither source tree, their compiled libraries nor the private switch
is distributed here. A new environment or changed source requires a new reading.
The shared proof gate cannot consume this instrument as a proof receipt.
