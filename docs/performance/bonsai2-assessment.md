# Bonsai 2 and reasoning-efficient post-training

Status: research selection review, 2026-10-22. **Evaluate Bonsai 2's small
models and the experimental Swift Bonsai 2 release alongside the established
27B candidate. Retain Q12's measured 4B baseline for the minimum mobile
comparison.** A combined checkpoint is available; its mixed evidence does not
establish a release-model replacement or target kernel. The
[Muse Spark Open assessment](muse-spark-open-assessment.md) adds a candidate
with a much larger resource budget, without displacing compact deployment.

This review extends the [BITCOS comparison](bitcos-assessment.md). Q4b owns
target selection, M6.6/M6.8 own the server and grant, and the
[product-gate contract](../implementation/contracts/product-gate.md)
owns quality acceptance. A model is best for a declared workload and resource
envelope; a publisher's aggregate benchmark does not decide that comparison.

## Source and candidate selection

Prism's [September 17 announcement](https://prismml.com/news/prismml-launches-bonsai-2-27b)
identifies Bonsai 2 as a ternary derivative of Qwen3.8-27B and reports 98.2
percent aggregate performance retention. Its twenty-benchmark aggregate and
the GGUF card's fourteen thinking-benchmark aggregate describe different
suites. Neither is a project measurement or a guarantee on every task.
Prism's [October 15 expansion](https://prismml.com/news/prismml-expands-bonsai-2-family-with-2b-4b-and-9b-models-for-on-device-ai)
adds Qwen3.5-derived 2B, 4B and 9B models, with advertised footprints of
0.43, 0.95 and 2.00 GB. These are candidates for a fresh comparison with Q12,
whose measured checkpoint remains the recorded baseline. The 27B review
below retains its own Qwen3.8 source and exact identities; small-model
quality, sampling and state costs require their own evidence.

Use the publisher's
[GGUF revision `6ed5e12bf84b7a63069882c91dd9e9218647d17b`](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/tree/6ed5e12bf84b7a63069882c91dd9e9218647d17b)
as the reviewed candidate identity. Its upstream file listing gives
`Ternary-Bonsai-2-27B-PTQ1_0.gguf` as 5,946,648,928 bytes, SHA-256
`53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3`,
and `Ternary-Bonsai-2-27B-PQ2_0.gguf` as 7,206,168,928 bytes, SHA-256
`3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1`.
These are publisher identities, not locally verified weight digests or tensor
censuses. The review fetched metadata and license text, not those weight files.
Keep both packings as baselines; the smaller one need not decode faster.

The [pinned GGUF card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/6ed5e12bf84b7a63069882c91dd9e9218647d17b/README.md)
specifies g128 FP16 scales, hybrid attention, and block-1024 Hadamard rotations
whose matching activation transform is mandatory. Recurrent-path and
normalization tensors retain higher precision. Its custom PQ2_0/PTQ1_0 types
and rotation-aware runtime are distinct from Q12's Q2_0_g64 instrument.
Unknown format or rotation semantics must refuse loading. Renaming the type
or accepting a superficially compatible loader does not establish correctness.

For current operational compatibility, use Prism's
[demo guide](https://github.com/PrismML-Eng/Bonsai-demo/blob/294035ef0d42faec196a49b6a32401d5f1129c58/README.md)
and [format contract](https://github.com/PrismML-Eng/Bonsai-demo/blob/294035ef0d42faec196a49b6a32401d5f1129c58/MODEL-FORMATS.md).
Recent upstream llama.cpp builds include Bonsai 2's required Hadamard,
sign-flip and model-graph integration for official Q2_0. PQ2_0 and PTQ1_0
remain fork formats, and the demo defaults to PQ2_0 with matching fork
binaries. Older builds can recognize Q2_0 while omitting required transforms.
The pinned model card's broad upstream warning therefore does not describe
every current packing/runtime pair. An application's bundled engine must
include the integration; its file extension alone supplies no evidence.

The companion
[MLX configuration](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-mlx-2bit/blob/3f926b415992eaa2ae9dd7b573706494d6bbf787/config.json)
declares the full/linear layer sequence, recurrent precision, convolution
shape, untied embeddings and absent MTP. Inspect the selected GGUF's own
metadata before transferring any of those declarations. The companion's
[PACK-RUNTIME note](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-mlx-2bit/blob/3f926b415992eaa2ae9dd7b573706494d6bbf787/PACK-RUNTIME.md)
calls itself a text-only preview without vision, while its configuration
sets `components.vision` true. Resolve that disagreement from tensor contents
before using the companion for multimodal measurements. It also limits its
reload checks to serialization, not quality or cross-runtime equality.

## Resource and kernel consequences

The reviewed 27B language-weight footprint alone exceeds the minimum usable
second-class payload in the [existing demand budget](inference-demand.md).
That screens out its shipped packings at that minimum, before session state
or concurrent consumers. The supply numbers are floors, not architectural
caps: a larger qualified configuration remains a candidate. No unchanged
mobile-fit conclusion follows from a successful laptop or GPU run. The new
small models need their own tensor census, quality comparison and session
budget before a fit or replacement decision.

Build a new tensor census and access schedule for this model. Do not scale the
4B report by parameter count, treat GGUF file length as bytes read every token,
or reuse its dense-attention KV expression for every hybrid layer. Account for
full-attention KV, recurrent and convolution state, their reads and writes,
Hadamard scratch and arithmetic, untied embedding/head accesses, padding and
the optional vision path separately. Bound all state per session and preserve
its isolation and reset behavior. Advertised context capacity is not an
admitted context or latency bound.

BITCOS can repack the finalized ternary symbols in their stored rotated basis.
Preserve g128 scales, rotation metadata, higher-precision exceptions and tensor
indexing. Compare against the exact PTQ1_0 packing geometry as well as PQ2_0;
the 4B paper's zero fraction supplies no Bonsai 2 estimate. Census zeros per
tensor after post-training and any requantization, then use the existing
BITCOS storage inequality and complete target schedule. Rotation and recurrent
operators remain costs even if unpacking becomes free. The proposed 128-lane
RVV block can align with g128, but that is a layout opportunity, not a measured
speedup. No x86 instruction or Intel timing is inherited.

## Finite rotation proof handoff

The [Hadamard survey](../background/open-math-conjectures.md#hadamard-matrix-conjecture)
is a non-normative input to Q4b's candidate comparison and M6.6's future kernel
and session work. The named block-1024 rotation has an unconditional power-of-two
construction; it does not wait for the universal Hadamard conjecture. A useful
finite proof records the actual sign matrix or recursive construction and checks
`H*H^T = 1024*I`, then connects normalization, scales, tensor indexing, padding,
rounding and overflow to the candidate's exact operator. Orthogonality over exact
numbers alone supplies neither quantization quality nor executable equivalence.
The missing lowering, scratch/lifetime and bounded-execution evidence stays with
the selected kernel's existing proof path; M6.8 charges the full rotation traffic
and schedule. A non-power-of-two construction is deferred unless a selected model
exposes such a dimension, with its own certificate and complete cost comparison.
The survey records independently checked matrices for twelve formerly open orders,
including 668; those finite witnesses make exact sign matrices available for a
matching dimension. They supply no `O(n log n)` evaluation algorithm, scratch
bound or quality result, and do not change the selected block-1024 operator.
No model, transform implementation or new compute slice is admitted by this lead.

## What Swift contributes

The [Swift 1.5 description](https://ukisai.com/swift-1-5-27b) combines selected
reasoning-marker penalties with reinforcement learning and on-policy
distillation. These are post-training techniques, rather than an added
looped-transformer architecture. The current
[27B card at `b4c84d42903a8646b25857eb2827288d92ed85a4`](https://huggingface.co/ukisai/Swift-1.5-Qwen3.8-27b/blob/b4c84d42903a8646b25857eb2827288d92ed85a4/README.md)
reports GPQA thinking-token reductions of 41.9 percent mean and 58.5 percent
median. Its five-repeat BF16 results include task regressions: IFBench falls
from 73.53 to 72.07 percent and AIME 2026 from 98.67 to 96.00 percent, while
LiveCodeBench v6 rises from 76.76 to 81.71 percent. Token savings, score
changes and demonstrations are per-task evidence, not a universal speedup.
The separate INT4 comparisons use different recipes and saved references;
they do not measure a controlled ternary adaptation. The reviewed materials
still do not specify a complete recipe sufficient to reproduce Swift exactly.

## Available Swift Bonsai 2 release

The [experimental release](https://ukisai.com/swift-bonsai-2) supplies complete
merged GGUFs, advertised as 5.947 GB PTQ1_0 and 7.206 GB PQ2_0, without a
separate adapter or runtime correction. PTQ1_0 is the earlier merged release;
PQ2_0 has updated merged weights. The reviewed
[repository revision `a3bdac086bbb6b04d87d0108d18943b5f63868f7`](https://huggingface.co/ukisai/Swift-Bonsai-2-GGUF/tree/a3bdac086bbb6b04d87d0108d18943b5f63868f7)
identifies those distinct candidates. Metadata gives PQ2_0 as 7,206,168,928
bytes and PTQ1_0 as 5,946,648,960 bytes; weights were not downloaded or
locally validated.

The [pinned release card](https://huggingface.co/ukisai/Swift-Bonsai-2-GGUF/blob/a3bdac086bbb6b04d87d0108d18943b5f63868f7/README.md)
separates historical runtime-correction results from current PQ2_0 results:

| Comparison | Task | Base / Swift score | Mean token change | Median token change |
| --- | --- | --- | --- | --- |
| Historical runtime correction | GPQA-Diamond | 84.18 / 84.34 percent | 19.0 percent fewer thinking tokens | 39.8 percent fewer |
| Historical runtime correction | C-Eval | 81.37 / 81.47 percent | 18.4 percent fewer thinking tokens | 7.1 percent fewer |
| Current PQ2_0 files | IFBench, loose scoring | 82.13 / 82.60 percent | 1.7 percent fewer thinking tokens | 0.4 percent more |
| Current PQ2_0 files | AIME 2025 | 92.00 / 93.33 percent | 4.3 percent more completion tokens | 5.1 percent more |

GPQA and C-Eval have not been rerun on the current merged files. GPQA helped
select training settings and is not an untouched holdout. AIME's archived
scorer checks final answers with a reasoning fallback; final-answer-only
scores are 90.67 percent for both models. Small score differences establish
no improvement, and token counts measure neither latency nor energy.

The authors report uneven instruction following, tool use and open-ended
coding or agent behavior in practical testing. Their caution applies to
the tested models and runtimes, rather than all ternary models. It prevents
treating the available benchmark results as production-quality acceptance.
The [license review](../../THIRD-PARTY.md#bonsai-2-and-swift-model-research)
distinguishes this Apache-2.0 release from Swift Qwen's custom commercial
terms. Independent training needs separately reviewed data/code provenance;
distillation from Swift or reuse of ThinkingCap is not implicitly included.

## Portable Bonsai mechanisms

Beyond the ternary alphabet, the pinned Bonsai card discloses signed
block-1024 Hadamard weight rotations with matching activation transforms,
FP16 scales per 128 weights, selected higher-precision tensors, and kernels
that consume packed weights directly. These suggest experiments on Muse's
own tensors and operators. Their exact grouping, precision exceptions and
rotation dimensions require a new sensitivity study and runtime contract.
The reviewed disclosures do not establish a complete reproducible
quantization-aware training recipe or measured quality retention for a
ternarized Muse. Bonsai's inherited Qwen hybrid-attention backbone is a
separate architecture property; packing
and post-training do not transfer it to Muse. See the
[Muse assessment](muse-spark-open-assessment.md) for the resource-tier and
quality constraints.

## Candidate comparison and independent training experiment

For 27B, start with unchanged Bonsai 2 at its supported `xhigh` and `medium`
settings and a bounded non-thinking comparator where the task permits it. The GGUF
card says `low` is unsupported and behaves close to `xhigh`; a label alone
does not create a cheaper baseline. Establish whether the existing controls
already meet the useful-answer objective before commissioning training.

Evaluate the available Swift Bonsai PQ2_0 against unchanged Bonsai in its
native packing before commissioning independent training. Keep the earlier
Swift PTQ1_0 as a separate candidate; its smaller file is not the updated
PQ2_0 checkpoint, and historical runtime evidence is not a substitute for
matched evaluation of either file.

If independent training is justified, train against Bonsai's actual
quantized forward path with the required rotations and state precision. Use
independently licensed examples with checked outcomes; separate training, tuning and held-out
evaluation. A candidate objective can combine task correctness with a bounded
reasoning-length penalty and a separately ablated marker penalty. Select
markers on training data and apply the penalty only in the reasoning segment.
Publish the selected coefficients, token IDs, data identities and seeds with
the checkpoint. This is a proposed local experiment, not Swift's disclosed
recipe, and it claims no benefit until measured.

Do not transplant a Qwen adapter into Bonsai merely because shapes agree.
Bonsai has different trained weights and a rotated representation. A residual
adapter needs an explicit basis mapping and charged resident bytes, traffic
and multiply work. Merging a dense update into a scaled ternary matrix normally
destroys the ternary alphabet; requantizing it is a new lossy operation.
Compare a bounded residual adapter with a ternary-aware merged candidate only
after fixing their arithmetic and quality tests. A floating master or an F16
export does not by itself supply the original trainable state or training recipe.

After selecting and freezing the trained model, regenerate its census and
choose the lossless packing. Evaluate the following ablation on matched inputs:

| Arm | Question |
| --- | --- |
| Unchanged Bonsai, native packing and supported effort settings | How far do existing controls go? |
| Unchanged Bonsai, BITCOS with identical arithmetic | Does packing reduce target cost without changing outputs? |
| Available Swift Bonsai, native packing | Does the released derivative improve useful-answer cost at acceptable quality? |
| The same Swift Bonsai, BITCOS | Do the released derivative and lossless packing improve target cost together? |
| Independently post-trained Bonsai, native packing | Does a separately licensed training experiment improve on the released candidates? |
| The same independent derivative, BITCOS | Do its gains survive after the new weight census? |

Keep the matching Qwen3.8 reference for capability comparisons and the
existing 4B models for the mobile resource comparison. Preserve Q1's separate
same-model widest-weight KL/top-1 checks; a behavioral score or a reference
from a different model cannot satisfy that predicate. Name the derivative's
reference explicitly and record an unavailable reference as missing evidence.

Freeze task strata, sample counts, seeds, prompts, tokenizer/template,
sampling, context, reasoning effort, numerical quality margins and the ranking
rule before scoring. Include instruction following, mathematics, code/tool
success, long-context use and vision only where admitted. Report paired
uncertainty, regressions per stratum, looping and truncation rates. Count
timeouts, malformed tool calls and truncated incorrect answers as failures.
Passing an aggregate while failing a required stratum rejects the candidate.

Measure **time and energy to a correct useful answer**, alongside first-token
latency, answer-start latency, total/thinking/answer token counts, peak resident
bytes and traffic. Report the cost of failed attempts as well as successful
ones. Fewer thinking tokens reduce generated work; they neither shrink weights
nor prove a higher sustained token rate. Do not multiply Swift's token reduction
by BITCOS's published speedup. End-to-end time includes prompt processing,
every generated step at its context length, tools, sampling and any adapter.
Under fixed grants, earlier completion does not donate another partition extra
service. Admission still needs a bound at the declared maximum output/context,
not an average shorter trace.

## Project disposition

Q4b takes this as a candidate-selection input alongside Q4a and Q12, with
hybrid-state and rotation requirements passed to M6.6 and the resulting traffic
to M6.8. Its current estimate does not include a new training campaign. Before
commissioning that campaign, land a bounded contract with dataset rights,
compute budget, producer/toolchain, checkpoint outputs, quality margins and
stop conditions; then price that work in the plan. The available Swift Bonsai
release is a candidate for evaluation; independent training remains a proposed
experiment. Neither is a runtime dependency without acceptance evidence.

Promote a candidate only if its matched-task quality and complete resource
cost beat the strongest feasible baseline under the frozen objective. Preserve
the measured [Q12 record](ternary-static-demand.md) and the existing release
floor until the [joint model-format and quality act](prompt-processing-term.md#weight-format-act-and-acceptance)
is supported. This review makes these candidates visible to that decision
without rewriting measurements of an older checkpoint.
