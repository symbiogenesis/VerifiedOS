# Muse Spark Open, ternary packing and efficient reasoning

Status: non-normative research assessment, 2026-10-22. **Retain Muse Spark
Open as a candidate for a substantially larger resource envelope, alongside
Bonsai 2 and the measured Q12 baseline.** No Muse checkpoint, target kernel,
ternary conversion or post-training campaign is selected or commissioned here.
Q4b owns selection, M6.6 owns the executable server and session descriptor,
M6.8 owns its grant, and the [product gate](../implementation/contracts/product-gate.md)
owns quality acceptance.

## Released model and comparison scope

Meta's [October 15 release](https://research.meta.ai/blog/muse-spark-open)
announces an open-weight multimodal mixture-of-experts model. The
[official architecture overview](https://dev.meta.ai/docs/muse-spark-open)
identifies 816B total parameters, 42B active per token and a 1,048,576-token
maximum context. Text, image, audio and video are inputs; output is text.
The [model card](https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B)
specifies 256 experts with eight selected per token. These are publisher
architecture declarations, not a tensor census of downloaded weights.

The public repository metadata identifies BF16 revision
`0fb02478b02565b2ce7fc57e6051c91172774ac9` for
[the model repository](https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B/tree/0fb02478b02565b2ce7fc57e6051c91172774ac9).
This review reads public documentation and the rendered card on the assessment
date. Gated file access does not establish verified configuration or weight
bytes at that revision. Downloaded weights, locally verified digests and an
independent tensor census are missing evidence.

Meta's card reports mixed comparisons with Qwen3.8-2.4T-A95B at `xhigh`:
Terminal-Bench 2.1 with Terminus 2 is 76.4 versus 82.0, while DeepSWE 1.1
with the preferred harness is 60 versus 57. These publisher results concern
the listed models, effort and harnesses. They establish neither uniform
superiority over Qwen nor matched quality against Bonsai 2, Swift Bonsai 2
or Swift-Qwen 27B. Compare those candidates on the frozen workload and their
actual post-compression quality before ranking them.

## Residency and the native baselines

The official overview gives approximately 1.65 TB of BF16 weights and
537 GB of NVFP4 weights, the latter retaining some layers in BF16. The card's
approximately 2 TB BF16 and at least 700 GB NVFP4 serving recommendations
include room beyond weights. Keep those published capacity categories distinct;
no figure is a target measurement, a complete session bound or a VerifiedOS fit.
BF16 is the widest released reference and NVFP4 a separate native baseline.

Sparse activation reduces expert arithmetic and selected expert reads; every
expert still consumes resident storage. [R-15-171](../spec.md#r-15-171)
requires all experts resident with top-k fixed and refuses routed storage
fetches. An ensemble must also meet
[R-15-171a](../spec.md#r-15-171a): composition-fixed shard residency, exchanges
and grants on each member. Meta's multi-machine desktop demonstration supplies
no qualified VerifiedOS member, admitted sharding schedule or target token rate.
It cannot remove the single-machine first-release obligation.

Do not substitute 42B active parameters for 816B in a capacity calculation or
read all 816B as the automatic weight traffic of every token. A Muse census
must identify routed and shared tensors, routers, embeddings and output head,
precision exceptions, perception encoders and the exact attention pattern.
The [native settings](https://dev.meta.ai/docs/muse-spark-open/settings)
distinguish sliding-window layers from full-context layers; their KV terms
need separate bounds. Charge per-session KV, activations, transforms, scratch,
decode buffers, routing work and concurrent consumers under the whole-program
plan. Advertised context capacity supplies no admitted context or latency bound.
The [existing demand record](inference-demand.md#8-the-target-traffic-budget)
continues to own Q4a's resource arithmetic and supply-floor interpretation.

## Ternary Muse and BITCOS are separate hypotheses

A good ternary Muse requires model-specific quantization and quality recovery.
The [BITCOS paper](https://arxiv.org/html/2609.16338v1) losslessly encodes
already-ternary symbols; it cannot preserve intelligence discarded by converting
BF16 or NVFP4 to ternary. Retaining selected tensors at higher precision may be
necessary, and its cost belongs in the census. Bonsai's reported retention does
not predict Muse's retention, router stability or multimodal quality.

As a dimensional illustration only, assigning all advertised parameters a
hypothetical whole-model effective rate of 1.76 bits per weight gives
`816e9 * 1.76 / 8`, approximately 180 decimal GB of weights. This assumes that
rate is attainable across the whole model, including precision exceptions;
it excludes session state and runtime storage. It is neither a calibrated
Muse size estimate nor evidence of quality, bandwidth, latency or laptop fit.
A substantially smaller resident model needs additional model reduction or
distillation and independent quality evidence.

Use the [existing BITCOS storage inequality](bitcos-assessment.md#compare-against-this-repositorys-actual-baseline)
with Muse's final per-tensor zero census, actual scale groups and each competing
packing's geometry. Include directories, panel offsets, padding, tails and
guard storage. Neither a Bonsai histogram nor the ternary alphabet chooses
the winner. Freeze the trained and quantized checkpoint before choosing its
lossless layout; Intel CPU/GPU results supply no Muse or VerifiedOS speedup.
The existing RVV comparison remains a candidate lowering, not an implemented
Muse kernel. Charge actual issued traffic and decode/compute scheduling.

## Portable Bonsai ideas

The [Bonsai assessment](bonsai2-assessment.md#source-and-candidate-selection)
and its pinned GGUF card identify mechanisms worth independent investigation:

| Mechanism | Muse investigation and missing evidence |
| --- | --- |
| Signed blockwise Hadamard rotations with matching activation transforms | Study sensitive Muse matrices and compatible dimensions; preserve basis, normalization and indexing, and charge activation work and scratch. |
| FP16 group scales over 128 weights | Compare group geometry and quality on Muse; scales, tails and metadata consume bytes. |
| Higher precision for sensitive tensors | Census routers, expert boundaries, attention, normalization, embeddings and perception paths; use a sensitivity study rather than Bonsai's exception list. |
| Kernels contracting packed weights directly | Avoid full-model expansion where feasible; prove arithmetic and bounds, then measure complete target traffic, scratch and issue cost. |

These mechanisms form a research menu rather than a complete disclosed training
recipe. Qwen's hybrid linear/full-attention backbone is an inherited architecture,
not a quantization operation to transplant into Muse. Muse's own attention
schedule remains part of the cost model. The finite rotation proof handoff
in the Bonsai assessment addresses exact transform arithmetic; orthogonality
alone proves neither extreme-quantization quality nor executable equivalence.

## Swift-style Muse and the decisive comparison

Reasoning-efficient post-training is plausible independently of model family.
First compare Muse's native `low`, `medium`, `high` and `xhigh` settings at
matched quality, using its own tokenizer, template and stopping semantics.
The default is `xhigh`; a shorter native trace is already an available baseline.
No verified Swift Muse checkpoint or controlled combined result is established
by these reviewed sources.

The [Swift Bonsai 2 release](https://ukisai.com/swift-bonsai-2) provides a
combined research checkpoint, with limitations detailed in the
[updated Bonsai review](bonsai2-assessment.md#what-swift-contributes). Historical
runtime-correction results and current merged-file results are different arms.
They supply neither a transferable Muse adapter nor a guaranteed multiplicative
saving. Muse-specific marker selection, objectives, outcome checks and held-out
data are needed for an independent experiment; Qwen token IDs and adapters
cannot simply be transplanted.

If training is justified, separately compare native effort controls, efficient
reasoning on the native model, ternary conversion with quality recovery, and
the combined derivative. Compare each frozen ternary candidate with and without
BITCOS using identical arithmetic. A dense update merged into ternary weights
usually breaks the ternary alphabet; requantization is another lossy step.
An unmerged adapter consumes resident bytes, reads and arithmetic. Changes to
routing or reasoning length can change the expert-access and state schedule.
Do not multiply published token reductions by packing speedups.

Freeze task strata, prompts, effort, context/output limits, sampling, quality
margins and ranking before evaluation. Report time and energy to a correct
useful answer, failures and retries, first-token and answer-start latency,
token counts, resident bytes and issued traffic. Include tools and modalities
only where admitted. Preserve Q1's separate same-model widest-weight KL/top-1
predicate; a cross-model benchmark cannot satisfy it. The admission bound
still covers declared maximum context/output, even if average traces shorten.

The [Muse license record](../../THIRD-PARTY.md#muse-spark-open-model-research)
keeps this research distinct from incorporation under the custom Muse Model
License and usage policy. Before commissioning training or target integration,
land the bounded contract, provenance, compute budget, quality margins and
stop conditions in the existing plan. Keep Q12's measured record and release
floor until the [joint model-format and quality act](prompt-processing-term.md#weight-format-act-and-acceptance)
supports a replacement. The current disposition adds a larger candidate and
portable experiments while leaving selection and target qualification open.
