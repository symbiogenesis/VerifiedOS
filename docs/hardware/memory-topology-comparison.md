# Memory topology comparison contract and initial screen

This is Q6's authorable comparison in the [implementation checklist](../implementation/implementation-checklist.md), governed by the [requirements register](../requirements-register.md). It compares the demand in [Q4a's inference record](../performance/inference-demand.md) and the placement boundary in [Q5a](../implementation/placement-search.md), with physical quantities owned by [R4's measurands](second-class-macro-architecture.md#5-the-measurands). No candidate has a qualified supply record here, so no topology or density is admitted.

## 1. Workload and early rejection

The common measured workload is Q4a's publisher-pinned dense Qwen3-4B-GGUF configuration, at the quantization and cache format named by each row of its [budget](../performance/inference-demand/budget.json). Preserve the digest, context, tensor accounting and output-quality comparator. Its projection to the release floor is explicitly a projection, not a measured three-billion-parameter model. The other simultaneous release members, and their per-class placement, remain owed to M7.1 and Q5b. Q5a's placement witness exercises a checker and cannot supply their footprint.

Screen a candidate before simulator setup. For the identical admitted workload and quality contract, require each class's resident demand to fit its usable payload after its own exclusivity reservation; require its fixed grants to meet inference traffic and the complete simultaneous roster; and require the area, power and yield/cost comparisons R-18-004b and R-18-004c name. Preserve the independent capacity and bandwidth failures. An absent supply coefficient makes that comparison undecided, not feasible. A smaller workload may be assessed only with its lost release functions and changed quality/context declared.

Q4a already supplies one rejection: at a composition declaring only the minimum M-class grant, its measured dense weight stream alone exceeds that grant. Moving the KV cache cannot remove the weight-stream failure. The rejection is against that minimum-grant candidate, not every two-class candidate, because the register permits a larger qualified grant. Reuse the budget's arithmetic and source records rather than copying its numeric table here. No simulator is needed to rediscover this failure.

## 2. Candidate dispositions

| Candidate | Workload it can be assessed against | Initial screen | Remaining evidence |
| --- | --- | --- | --- |
| Smaller qualified all-SRAM configuration | A separately declared subset whose full resident set fits its measured local payload and fixed grants | It does not satisfy the current release contract's second-class-resident inference member merely by fitting a smaller model. No qualified all-SRAM specimen or complete subset roster is supplied here, so even that subset has no admitted configuration. | Actual macro capacity, overhead, latency, power, die-area fit, supplied process and lifetime evidence; scope and placement of the reduced workload |
| R-15-247 two-class configuration | The current composed release floor, plus Q4a's measured larger-model comparator only if separately admitted | The minimum-grant dense candidate fails the weight-stream screen above. Larger grants remain undecided; R4's architecture and model placeholders do not establish physical capacity. | R5's complete repaired-macro package, first-class evidence, the bank grant, simultaneous roster placement and M9a's composition-capacity join |
| SRAM with an explicit public-weight store | A bounded inference data-stream workflow under the interface below; it does not meet the current wholly-resident second-class clause by relabelling external storage as RAM | No qualified delivery, verification or scratch budget exists, so sustained generation and full-roster fit are undecided. Dropping residence changes the release contract and may exchange capacity for token latency. | Qualified device/link and verification bounds, local working set, supply path, physical exposure, denial-of-service contract and explicit architecture/release amendments |

For every candidate, usable density, tag/ECC/periphery/routing/spare overhead, access and refresh energy, repair coverage, latency and corner/lifetime quantities are **owed**, with R5 owning second-class measurements and R5a first-class sensitive-state lifetime. The actual supplier and product owner must supply first-class macro and wafer/process/cost evidence; no value is inferred from a different process. R-17-063b names a stack that no foundry offers. That absence blocks a credible supply-path verdict for that stack rather than being charged as zero cost.

A conventional SRAM/DRAM comparison must name its placement and controller policy and charge row-buffer, refresh, disturbance and external-interface behavior. Ramulator2 or OpenRAM would require a qualified configuration, process and workload trace before any result could enter this comparison; their defaults do not instantiate this machine. No new implementation or tool deployment is authorized by this comparison contract.

## 3. Public-weight-store interface

The proposed physical requester is an on-die, capability-confined host controller connected to a point-to-point block-data peripheral. The peripheral has no bus-master interface into host memory, cannot initiate loads/stores, and exposes no capability, address-space, executable or coherent-memory authority. The host issues bounded object requests in its own admitted schedule. Device-facing electrical, reset, clock, fault and delivery behavior require a separately qualified interface; none is supplied by this document. R-15-162's one-die main-memory boundary remains in force while this is only a comparator.

The generation's composition declares a trusted model-content identity, a canonical authenticated chunk manifest, a finite chunk index domain, maximum encoded and decoded chunk lengths, tensor placement, scratch and verification capacity, queue depth, per-request deadline and maximum outstanding request count. A chunk binds model identity, generation, tensor identity, offset and length through the authenticated manifest. The verifier rejects malformed, oversized, overlapping, substituted, reordered-as-another-index or incorrectly authenticated data before making bytes visible to inference. The authenticated encoding and verification implementation require their own qualified parser and cryptographic contracts; this proposal does not invent a cipher or mode.

| Operation | Authority and result | Bound and refusal |
| --- | --- | --- |
| Open model | Read-only handle to the composition-named model identity, obtained through the ordinary capability grant | Refuse an identity or format absent from the manifest; no arbitrary device namespace enumeration |
| Request chunk | Host queues a declared index against that handle and a reserved local slot | Refuse out-of-domain indices, duplicate live requests or a full queue without allocation or eviction |
| Complete and verify | Device bytes enter a host-owned staging buffer; the verified extent is published only after full authentication | Refuse oversized, short, corrupt, wrong-generation or timed-out input; erase/release the failed staging slot before reuse |
| Consume verified chunk | Read-only, non-executable local data extent for the named tensor region | Bound decoded length and lifetime; no imported tag, pointer, permission or executable authority |
| Close or fail session | Stop issuing, quiesce the controller and retire handles and live requests | Use a composition-declared terminal deadline; invalidate stale completions and fail the affected inference request if delivery fails |

Authority-bearing state, verification keys/manifests and all staging, decoding and application buffers stay local. Double buffering is allowed only when its full simultaneous footprint is reserved; it does not create free overlap. The implementation must charge copies, authentication, dequantization, KV traffic and output buffers to their actual class and schedule. A rejected chunk produces no partial tensor and no silently substituted model; policy may retry only within a separately declared bounded request contract, never indefinitely.

## 4. Accounting and privacy

For each workload record, compute wire bytes from payload plus framing, authentication and padding. The sustained link requirement is the admitted token rate times wire bytes per token, plus any separately scheduled loading traffic. Verification demand is that same chunk population under the admitted algorithm and key/manifest access pattern. Both service rates must independently fit their grants. State setup and loading time, first-result latency and steady-state generation separately; pipelining overlaps stages only with a justified dependency schedule and the reserved buffers it needs.

Charge the maximum simultaneous encoded chunks, decoded chunks, manifest/proof paths, verifier workspace, queue metadata, inference scratch and resident KV/output state. Report link energy, storage energy, local verification energy and retained-state cost against the declared modes, with each physical coefficient and its source still owed. An infinite or unknown device response bound cannot establish hard delivery, regardless of mean bandwidth.

Public model weights do not make the request trace public. Prompt-dependent sparse expert selection, cache misses or selected chunk addresses may reveal user data. A comparison must either demonstrate a composition-fixed access trace independent of secret inputs, carry a verified leakage contract with the exposed trace explicitly admitted, or reject the configuration. Encryption of chunk bytes does not hide indices or timing by itself. External storage can deny service; containment limits authority, not availability.

## 5. Address-growth act raised for review

R-15-007d already distinguishes a coordinated pre-final-freeze format amendment from a post-freeze transition that must account for stored authority. Q6 supplies neither a new width nor a migration policy. Larger object-indexed storage need not enlarge directly addressable RAM, and a storage handle must never be reinterpreted as a capability address.

The proposed decision text for the R-15-007d review is: **"Assess the public-weight-store arm using bounded object and chunk identifiers outside the directly addressable RAM namespace. That assessment grants no change to the capability width, no authority to reinterpret stored capabilities, and no exemption from R-15-162, R-15-247 or the release-residence requirement. A candidate requiring wider load/store addresses returns to the pre-final-freeze amendment with its required width and the joint model, layout, compiler, RTL and proof changes named before implementation."**

This is a proposal, not an inserted register entry or an approved public-weight architecture. The needed width is owed to an accepted candidate workload and physical supply, not chosen to complete a document. The same review must identify any amendments needed to the memory-interface and release-residence clauses. The directly addressed form and the object form remain distinct options.

## 6. Acceptance and unresolved join

The authorable comparison passes review only if all candidates use a named workload and quality contract; infeasibility is screened before simulation; every absent physical coefficient has an owner; the external arm has bounded authority, buffering, failure, privacy and availability terms; and the address proposal is visibly unadopted. It fails if a workload reduction is credited as full release compliance, a host rate becomes a target rate, or witness placement becomes product capacity.

Q6 itself stays open until useful workload, resources, implementation maturity, physical threat claims and a credible supply path support a selected product. R5 and R5a own macro and lifetime evidence, M9a the full-capacity physical join, Q4b target kernels, M6.8 the admitted inference grant, and M7.1/Q5b the complete roster. A protocol or comparator cannot substitute for those inputs.
