# e-means for clustering and codebook training

Status: optional research candidate, reviewed 2026-11-09. Retain e-means for a
future named clustering consumer. No current consumer, implementation, target
measurement or release dependency is selected. Q30g owns later compute-slice
selection under the [compute plan](../../PLAN.md#open-compute-qualification);
Q4b consumes this lead only if an inference candidate actually trains a codebook.
Any implementation first needs its own bounded, priced plan item. This assessment
does not enlarge the frozen Q30b/Q30c pilots or their estimates.

## Research identity and result

[Bessa et al., e-means v1](https://arxiv.org/html/2611.09501v1),
arXiv:2611.09501v1, trains k-means clusters using mini-batches and exponentially
averaged statistics, with scheduled updates and dead-cluster revival. Reported
embedding experiments reach Lloyd's 25-epoch test loss in 1.4–2.6 passes, with
roughly 10–45 times H100 GPU wall-clock speedups against Flash-KMeans. The
scaling laws are less suitable for tiny, low-dimensional datasets. These are
the authors' measurements; universal quality and a VerifiedOS performance factor
remain unestablished.

The [project page](https://e-means.github.io/) is the discovery entry; the
versioned paper is this assessment's research input. No implementation source,
dataset or dependency is incorporated or pinned. A selected reuse candidate
needs the exact-revision licence and dependency reading required by
[the incorporation rules](../../AGENTS.md#before-incorporating-an-upstream).

## Where the candidate fits

Potential consumers are semantic-search index construction, photo/document
clustering and vector-quantization codebook training. These are candidate
applications, not additional release features. Training cost, downstream
quality, query latency, encoded bytes and inference throughput are separate
measurements. Faster centroid training alone changes none of the
[inference demand record's](inference-demand.md) resident bytes or token traffic,
and it does not replace the [lossless ternary packing comparison](quantization-assessment.md).
A codebook or approximation that changes model behavior needs its own quality
decision before its deployment cost is compared.

An admitted implementation uses the existing confined compute path and
[numerical, resource and source-correspondence contract](../implementation/compute-compatibility.md#qualification-contract).
Its buffers, reductions and distance calculations need actual V/M lowering
and timing evidence. The research supplies no ISA, kernel, trust-base or
design-space-exploration change.

The prospective [Vela numerical workload](https://github.com/symbiogenesis/VelaLang/blob/main/docs/extensions/numerical-workloads.md)
can exercise dimensions, explicit mutable storage, finite loops and arithmetic
proof obligations. Vela's [first-release primitive semantics](https://github.com/symbiogenesis/VelaLang/blob/main/docs/language/first-release.md#primitive-semantics)
exclude floating-point runtime support. Its numerical semantics and target
correspondence must be qualified before a faithful runtime example; a
fixed-point adaptation needs its own accuracy evidence.

## Consumer selection and acceptance

Keep selection deferred until a real application names the clustering operation
and the cost it needs to reduce. Before implementation, the separate plan item
fixes its scope, estimate, retained baseline and the following decision inputs:

1. **Workload and quality.** Freeze dataset identity and permitted use, training
   and held-out splits, dimensions, cluster count, epoch/batch budget and the
   application quality threshold. Compare against the strongest applicable
   retained clustering baseline at that threshold. Measure the downstream
   retrieval or quantization result separately from clustering loss.
2. **Finite numerical behavior.** Fix representations, rounding and accumulation
   order, seed/shuffle, distance ties, schedule, revival and finalization rules,
   including empty clusters and tails. Define refusal or recovery for invalid
   dimensions, non-finite values, overflow and zero or underflowed counts.
   A positive real-valued initial count alone proves no finite-precision division
   safe. Label exact and approximate assignment as different configurations.
3. **Independent behavior and resource evidence.** Compare assignment, count/sum
   updates, revival and finalization against an independent scalar oracle on
   small boundary cases. Bound initialized storage, index arithmetic, scratch,
   batches, restart and cleanup, and satisfy the existing admission and proof
   obligations. Functional tests and empirical quality supply no missing theorem.
4. **Complete cost and decision.** Measure training and deployment costs
   separately, including data movement and scratch, on each declared execution
   platform with matched resource envelopes for baseline and candidate. Retain
   host and target evidence separately;
   derive no fixed-slot WCET or target speedup from average H100 time. Freeze the
   ranking and improvement threshold before scoring, record losses as well as
   wins, and leave adoption open when the required evidence is unavailable.

This gate selects an optional workload under existing platform guarantees. It
does not require a benchmark campaign before a consumer or commit either project
to floating-point, clustering-library or upstream implementation work.
