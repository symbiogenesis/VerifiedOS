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
- `TagConservativity.v` proves that the tag interpreter preserves legacy requests,
  responses, event order and refusals for tag-free computations.
- `PhysicalCallerBridge.v` checks every request kind in the minimal emitted caller,
  arbitrary successful data replies, tag ordering and exact refusals.
- `replay.py` reproduces the selected support builds, actual minimal emission,
  repeated output comparison and strict native controls. It compiles the emitted
  architecture against both support variants and checks each V1 instance reading
  against its reviewed digest. It copies dependencies
  privately and inventories both installed prefixes before and after. The replay
  of the November input set also checks the recorded Sail and Z3 binaries,
  plugin population, private stdpp sources and objects, and emitted bytes.

Run from the assigned checkout in the native guest, using expanded absolute inputs
from the matching Q35n/Q35o qualification. The output must be a new directory under
this checkout's assigned `/root/build/lane-*` root and must overlap no input. For the
retained November inputs, the invocation is:

```sh
inputs=/root/build/fanout-retained/4b3b843a3b9fe80d0323/holdfast-20261124-canonical/lane/replay-inputs
lane=holdfast-replay-20261125
export PATH=/root/z3-5.3.3/bin:$PATH
python3 tools/sail-tag-outcomes/replay.py \
  --source-archive "$inputs/coq-sail.tar.gz" \
  --stdpp "$inputs/private/lib/coq/user-contrib/stdpp" \
  --plugin "$inputs/plugins/sail_plugin_coq.cmxs" \
  --rocq-prefix /root/.opam/verifiedos-rocq-9.3.0-ocaml-5.4.1 \
  --sail-prefix /root/.opam/verifiedos-sail-0.20.3-ocaml-5.4.1 \
  --out "/root/build/lane-$lane/replay"
```

Set `lane` to the worktree's verified lane name before running.
The session's fanout retirement may move those native input copies into its retained
lane archive; select their preserved absolute locations when replaying after
retirement. `candidate.json` and the retained receipts bind their identities.
The replay runner's `PASS` covers the isolated compiles and the two V1 instance readings.
The fresh normalized declarations are retained in `v1-baseline.json` and
`v1-candidate.json` for comparison with the frozen bundle.
It does not perform the retained native assumption queries or kernel recheck,
complete package tests, the production census, full canonical acceptance or a gate.
Each emission runs in a fresh directory and passes `bindings.sail` as the relative
input name because Sail includes that name in the emitted refusal terms.

The [current qualification](../../docs/assurance/sail-memory-bindings.md)
records all unmet joins and the immutable evidence. The original bounded search
stopped after twelve checks; a new proof candidate needs a new reviewed checkpoint.
The wraparound control uses lazy kernel conversion. Eager `vm_compute` can first
materialize the existing loop's enormous unary bound even when its interval is empty;
other computational controls carry explicit tactic timeouts.

Focused host helper controls run with:

```powershell
python -m unittest discover -s tools/sail-tag-outcomes -p test_replay.py
```

These test path isolation, input identities and frozen V1 declaration refusal.
