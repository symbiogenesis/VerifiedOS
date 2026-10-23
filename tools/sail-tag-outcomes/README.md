# Canonical V1 tag candidate

This isolated Q35p library amendment implements the landed
[canonical tag contract](../../docs/implementation/contracts/canonical-tag-outcomes.md)
over the authenticated Q35n coq-sail 0.20.3 candidate. It does not change the
production support recipe, prover switch, Sail source or emitter.

- `candidate.json` binds the immutable semantic patch, existing source recipe,
  unchanged minimal Sail reproducer and qualified private syntax-plugin identity.
- `TagInterpreter.v` defines executable finite-map tag legality, a fixed handler
  for other outcomes, primitive continuation bridges and forwarding lemmas.
- `TagControls.v` checks the actual emitted metadata and physical-memory callers,
  positive instances and distinguishing refusals.
- `replay.py` reproduces the selected support builds, actual minimal emission,
  repeated output comparison and strict native controls. It copies dependencies
  privately and inventories both installed prefixes before and after. No installed
  `.v` dependency is rebuilt. A failure or timeout produces no success verdict.

Run from the assigned checkout in the native guest, using expanded absolute inputs
from the matching Q35n/Q35o qualification. The output must be a new directory under
this checkout's assigned `/root/build/lane-*` root and must overlap no input. For the
recorded native inputs, the invocation is:

```sh
python3 tools/sail-tag-outcomes/replay.py \
  --source-archive /root/build/lane-reuse-wire-20261023-tags/coq-sail-0.20.3.tar.gz \
  --stdpp /root/build/lane-reuse-wire-20261023-tags/stdpp \
  --plugin /root/build/lane-reuse-wire-20261023-tags/plugins/sail_plugin_coq.cmxs \
  --rocq-prefix /root/.opam/verifiedos-rocq-9.3.0-ocaml-5.4.1 \
  --sail-prefix /root/.opam/verifiedos-sail-0.20.3-ocaml-5.4.1 \
  --out /root/build/lane-reuse-wire-20261023-tags/replay
```

The session's fanout retirement may move those native input copies into its retained
lane archive; select their preserved absolute locations when replaying after
retirement. `candidate.json` and the retained receipts bind their identities.
The replay runner's `PASS` means only these isolated compile controls passed.
It does not perform the retained native assumption queries or kernel recheck,
complete package tests, the production census, full canonical acceptance or a gate.

The [current qualification](../../docs/implementation/q35p-memory-bindings.md)
records all unmet joins and the immutable evidence. The original bounded search
stopped after twelve checks; a new proof candidate needs a new reviewed checkpoint.
The wraparound control uses lazy kernel conversion. Eager `vm_compute` can first
materialize the existing loop's enormous unary bound even when its interval is empty;
other computational controls carry explicit tactic timeouts.

Focused host helper controls run with:

```powershell
python -m unittest discover -s tools/sail-tag-outcomes -p test_replay.py
```

These test path isolation and digest refusal without a native toolchain or gate.
The driver was reviewed and host-checked separately from the retained native run;
that run used the retained per-attempt commands. A clean replay of this packaged
runner has not been claimed.