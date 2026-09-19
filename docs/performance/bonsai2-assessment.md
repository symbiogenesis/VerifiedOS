# Bonsai 2 and reasoning-efficient post-training

Status: research selection review, 2026-09-19. **Prioritize Ternary Bonsai 2
27B for evaluation on a configuration with a larger resource budget. Retain
Q12's measured 4B baseline for the minimum mobile comparison.** Consider
reasoning-efficient post-training on Bonsai only after establishing its own
quality baseline. No combined checkpoint, training result, target kernel or
release-model replacement is established here.

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
The reviewed [Bonsai 2 collection](https://huggingface.co/collections/prism-ml/bonsai-2)
contains 27B releases, not a Bonsai 2 4B replacement for Q12.

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

The published language-weight footprint alone exceeds the minimum usable
second-class payload in the [existing demand budget](inference-demand.md).
That screens out the shipped packings at that minimum, before session state
or concurrent consumers. The supply numbers are floors, not architectural
caps: a larger qualified configuration remains a candidate. No unchanged
mobile-fit conclusion follows from a successful laptop or GPU run.

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

## What Swift contributes

The reviewed
[Swift card at `048328f4059015b63f860a453bf94834af0db683`](https://huggingface.co/ukisai/Swift-Qwen3.8-27b/blob/048328f4059015b63f860a453bf94834af0db683/README.md)
describes penalizing selected reasoning-marker tokens during fine-tuning and
a transfer component from ThinkingCap. This is behavioral post-training, not
an added looped-transformer architecture. Its
[NOTICE](https://huggingface.co/ukisai/Swift-Qwen3.8-27b/blob/048328f4059015b63f860a453bf94834af0db683/NOTICE)
identifies a trained LoRA merged into the base weights and an unchanged model
configuration and tokenizer.

The card reports GPQA mean thinking-token reduction of 41.0 percent, with
58.3 percent referring to the median. Quality is not uniformly preserved:
its BF16 AIME scores are 98.67 percent for the base and 94.00 for Swift.
INT4 results are separate comparisons, not evidence for ternary Bonsai 2.
The supplied [discussion](https://www.reddit.com/r/LocalLLaMA/comments/1wjocnh/question_ukisai_swift_ternary_bonsai_2_27b/)
asks about making a Swift version of Bonsai; it supplies no combined checkpoint
or controlled result. The reviewed release materials do not provide a complete
training recipe, marker set, objective and dataset sufficient to reproduce
Swift exactly.

The [license review](../../THIRD-PARTY.md#bonsai-2-and-swift-model-research)
accepts Bonsai's Apache-2.0 terms for a prospective experiment, but does not
select Swift weights or deltas for incorporation: their contribution carries
separate commercial restrictions. Applying the general technique independently
needs its own reviewed training-data and code provenance. Distillation from
Swift or reuse of ThinkingCap is not silently included in that independent arm.

## Proposed combination and decisive experiment

Start with unchanged Bonsai 2 at its supported `xhigh` and `medium` settings
and a bounded non-thinking comparator where the task permits it. The GGUF
card says `low` is unsupported and behaves close to `xhigh`; a label alone
does not create a cheaper baseline. Establish whether the existing controls
already meet the useful-answer objective before commissioning training.

If training is justified, train against Bonsai's actual quantized forward
path with the required rotations and state precision. Use independently
licensed examples with checked outcomes; separate training, tuning and held-out
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
| Post-trained Bonsai, native packing | Does training improve useful-answer cost at acceptable quality? |
| The same post-trained Bonsai, BITCOS | Do the gains survive together after the new weight census? |

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
stop conditions; then price that work in the plan. Missing inputs leave the
combined model an experiment proposal, not a runtime dependency.

Promote a candidate only if its matched-task quality and complete resource
cost beat the strongest feasible baseline under the frozen objective. Preserve
the measured [Q12 record](ternary-static-demand.md) and the existing release
floor until the [joint model-format and quality act](prompt-processing-term.md#weight-format-act-and-acceptance)
is supported. This review makes the newer model visible to that decision
without rewriting measurements of an older checkpoint.
