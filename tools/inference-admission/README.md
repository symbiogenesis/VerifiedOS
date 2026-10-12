# Finite host inference admission

`python tools/run.py inference-admission INPUT.json` joins M6.7's executable
residency/work reference and M6.8's symbolic bank-spending reference through one
opening adapter. The shared inputs and acceptance boundary are owned by
[the service authoring contract](../../docs/implementation/contracts/service-authoring.md#executable-host-residency-and-grant-interface)
and [InferenceAdmission.v](../../proofs/InferenceAdmission.v).

The JSON contains an already decoded shape and explicit composition inputs.
There is no verified wire parser, executable target server or physical admission.
Booleans cannot stand for integers; missing, extra and duplicate object fields,
negative numbers, coerced values and JSON beyond the decoder's nesting limit
are refused. A finite residency map treats
absent indices as nonresident. Routing preserves the source's repeated-index
behavior, while work assumes one declared uniform expert cost.

Use these illustrative symbolic inputs, without interpreting their quantities
as qualified bandwidth or WCET:

```json
{
  "shape": {
    "resident_bytes": 40, "context_length": 128, "format": 1,
    "expert_count": 4, "top_k": 2, "kv_bytes_per_token": 8
  },
  "ceiling": {
    "max_resident_bytes": 40, "max_context_length": 128,
    "admitted_formats": [1], "max_expert_count": 4, "fixed_top_k": 2,
    "max_kv_bytes_per_token": 8, "ceiling_grant": 200
  },
  "costs": {
    "dense_work_per_token": 10, "expert_work_per_token": 3, "fetch_penalty": 100
  },
  "residency": [true, true, true, true],
  "kv_placement": "bank",
  "server": {"slot": 7, "workers": [3, 5], "pool_bytes": 4096, "session_capacity": 2},
  "sessions_open": 0, "requested_rate": 4, "route": [0, 2]
}
```

`bank` charges resident weights plus the declared KV bytes per token;
`outside-bank` charges weights only. Neither arm multiplies KV traffic by context
length. The quotient is exact integer arithmetic; zero or absent byte demand has
no defined rate, and an above-grant request is refused without degradation.

The stdout JSON binds the input and source bytes by SHA-256, reports the
`session_decision` separately from `route_decision`, and records both occupancy
and unchanged server resources. A refused opening leaves the route check
`not_run`. A successfully opened session can still have a refused route, as in
the source's separate operations. Exit 0 requires both session and route success,
exit 1 reports a semantic refusal, and exit 2 reports invalid inputs or unreadable
sources. The command writes no persistent session state.

`python tools/run.py test --only inference` runs the focused generated residency,
spending and integrated-opening controls. Independent expected work and spending
checks refute live Python defects; they supply no universal theorem, compiled
mutation verdict or target correspondence. The shared contract retains the
unqualified concrete residency, uniform kernels/WCET, DSE, physical KV/grant and
target joins. Full host/guest gates and benchmarks stay on GitHub Actions.
