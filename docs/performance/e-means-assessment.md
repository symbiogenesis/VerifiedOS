# e-means and SuperEMeans for clustering and codebook training

Status: optional research candidate, reviewed 2026-11-19. Retain e-means and its
dimension-pruned fusion SuperEMeans for a future named clustering consumer. No
current consumer, implementation, target measurement or release dependency is
selected. Q30g owns later compute-slice selection under the
[compute plan](../../PLAN.md#open-compute-qualification); Q4b consumes this lead
only if an inference candidate actually trains a codebook. Any implementation
first needs its own bounded, priced plan item. This assessment does not enlarge
the frozen Q30b/Q30c pilots or their estimates.

## Research identity and result

[Bessa et al., e-means v1](https://arxiv.org/html/2611.09501v1),
arXiv:2611.09501v1, trains k-means clusters using mini-batches and exponentially
averaged statistics, with scheduled updates and dead-cluster revival. Reported
embedding experiments reach Lloyd's 25-epoch test loss in 1.4–2.6 passes, with
roughly 10–45 times H100 GPU wall-clock speedups against Flash-KMeans. The
scaling laws are less suitable for tiny, low-dimensional datasets.

[Kuffo, SuperEMeans](https://www.lkuffo.com/superemeans/) (2026-11-17) fuses
e-means' few-epoch schedule with SuperKMeans' orthogonal dimension pruning from
[Kuffo, Hepkema and Boncz, arXiv:2603.20009v1](https://arxiv.org/abs/2603.20009)
in the [SuperKMeans repository](https://github.com/cwida/SuperKMeans), with
benchmark scripts in [reproducibility-superemeans](https://github.com/lkuffo/reproducibility-superemeans).
SuperEMeans leaves epoch 0 unpruned, then applies probabilistic ADSampling
dimension pruning over randomly rotated vectors (orthogonal QR or sign-flip and
DCT at high dimension), a columnar PDX centroid layout and dynamically tuned
partial-distance prefixes (`partial_d`) before unrotating output centroids. On a
single 16-core Zen 5 host (clustering time only, excluding data load and final
assignment), reported IVF index builds (1:256 centroid ratio) compare as
follows:

| Dataset and budget | Algorithm | Runtime (s) | Recall@100 at 1% probed | Vectors scanned at 1% probed |
| --- | --- | --- | --- | --- |
| OpenAI 5M x 1536d, 20k clusters, 10 iters | Lloyd's / SuperKMeans | 985 / 232 | 0.962 / 0.962 | 52,053 / 51,993 |
| OpenAI 5M x 1536d, 20k clusters, 2 epochs | e-means / SuperEMeans | 203 / 128 | 0.967 / 0.967 | 58,184 / 58,198 |
| OpenAI 5M x 1536d, 20k clusters, 5 epochs | e-means / SuperEMeans | 513 / 162 | 0.968 / 0.968 | 58,078 / 58,086 |
| Cohere 10M x 1024d, 40k clusters, 10 iters | Lloyd's / SuperKMeans | 2,504.4 / 623.3 | 0.919 / 0.919 | 112,714 / 112,547 |
| Cohere 10M x 1024d, 40k clusters, 2 epochs | e-means / SuperEMeans | 525.8 / 295.3 | 0.923 / 0.923 | 135,380 / 135,463 |
| Cohere 10M x 1024d, 40k clusters, 5 epochs | e-means / SuperEMeans | 1,283 / 436 | 0.927 / 0.927 | 136,212 / 136,191 |

Within the same C++ harness, dimension pruning accelerates e-means by roughly
1.6–1.8 times at 2 epochs and 2.9–3.2 times at 5 epochs with matched recall and
scan counts (the authors' FAISS/BLIS e-means baseline took 333 s on OpenAI and
927.1 s on Cohere at 2 epochs). The same experiments expose a cluster-balance
trade-off in e-means itself: mini-batch updates bloat clusters in frequently
queried regions despite lower WCSS/MSE, scanning roughly 12 percent more vectors
on OpenAI and 20 percent more on Cohere at 1 percent probed centroids. Matching
scanned vectors by probing 0.90 percent of centroids yields a small net win on
OpenAI (0.964 recall@100 at 51,962 vectors) but a loss on Cohere (0.918
recall@100 while still scanning 121,511 vectors, roughly 8 percent more than
Lloyd's). Raising the dead-cluster revival threshold from 0.1 to 0.3 every five
batches narrows Cohere's scan excess from 1.20 times to 1.06 times (119,548
vectors at 0.918 recall@100). The post also notes two separate observations:
hierarchical k-means improved balance for SuperKMeans but did not work well with
e-means (suspected revival interaction), and clustering pre-quantized vectors
(int8 scalar, 4-bit LVQ or 1-bit RaBitQ,
[Kuffo and Boncz, arXiv:2608.14648v1](https://arxiv.org/abs/2608.14648)) is an
orthogonal footprint and compute reduction that requires its own quality gate.

These are the authors' host GPU and CPU measurements; universal quality, query
balance and a VerifiedOS performance factor remain unestablished. The
[e-means project page](https://e-means.github.io/) and SuperEMeans post are
discovery and experimental records; versioned papers and exact upstream
revisions govern any later reuse. No implementation source, dataset or
dependency is incorporated or pinned. A selected reuse candidate needs the
exact-revision licence and dependency reading required by
[the incorporation rules](../../AGENTS.md#before-incorporating-an-upstream).

## Where the candidate fits

Potential consumers are semantic-search index construction, photo/document
clustering and vector-quantization codebook training. These are candidate
applications, not additional release features. Training cost, downstream
quality, cluster balance, query latency, encoded bytes and inference throughput
are separate measurements. Faster centroid training alone changes none of the
[inference demand record's](inference-demand.md) resident bytes or token traffic,
and it does not replace the [lossless ternary packing comparison](quantization-assessment.md).
A codebook or approximation that changes model behavior needs its own quality
decision before its deployment cost is compared.

For high-dimensional, multi-epoch clustering of public embeddings on CPU or
vector hardware, SuperEMeans is the stronger training-time candidate over plain
e-means once upfront rotation and unpruned epoch 0 amortize. It is not an
unconditional drop-in upgrade under VerifiedOS's invariants: ADSampling pruning
is probabilistic (approximate) rather than exact distance minimization,
out-of-place rotation and columnar PDX layouts increase working storage (roughly
doubling dataset memory unless run in-place, plus rotation, unrotation and
partial-norm scratch), and data-dependent early exits with online `partial_d`
tuning neither reduce worst-case fixed-slot WCET (unless worst-case unpruned
work is bounded or execution runs inside a bounded-yield elastic domain) nor
comply with the constant-time discipline on secret-typed inputs. Quantized-input
clustering is a separate configuration requiring its own accuracy evidence.

An admitted implementation uses the existing confined compute path and
[numerical, resource and source-correspondence contract](../implementation/compute-compatibility.md#qualification-contract).
Its buffers, rotations, layouts, reductions and distance calculations need
actual V/M lowering and timing evidence. The research supplies no ISA, kernel,
trust-base or design-space-exploration change.

The prospective [HoldFast numerical workload](https://github.com/symbiogenesis/HoldFast/blob/main/docs/extensions/numerical-workloads.md)
can exercise dimensions, explicit mutable storage, finite loops and arithmetic
proof obligations. HoldFast's [first-release primitive semantics](https://github.com/symbiogenesis/HoldFast/blob/main/docs/language/first-release.md#primitive-semantics)
exclude floating-point runtime support. Its numerical semantics and target
correspondence must be qualified before a faithful runtime example; a
fixed-point adaptation needs its own accuracy evidence.

## Consumer selection and acceptance

Keep selection deferred until a real application names the clustering operation
and the cost it needs to reduce. Before implementation, the separate plan item
fixes its scope, estimate, retained baseline and the following decision inputs:

1. **Workload, quality and cluster balance.** Freeze dataset identity and
   permitted use, training and held-out splits, dimensions, cluster count,
   epoch/batch budget and the application quality threshold. Compare pruned and
   unpruned e-means (with explicit revival-threshold tuning) against the
   strongest applicable retained baseline (including Lloyd's and SuperKMeans) at
   that threshold. Measure downstream retrieval or quantization quality and
   query work (vectors scanned or distance evaluations at matched recall, plus
   cluster-size balance) separately from clustering loss.
2. **Finite numerical behavior.** Fix representations, rounding and accumulation
   order, seed/shuffle, orthogonal rotation/unrotation (QR or sign-flip/DCT),
   columnar layout conversion, ADSampling threshold (`epsilon0`), online
   `partial_d` adjustment, distance ties, schedule, revival threshold and
   finalization rules, including empty clusters and tails. Define refusal or
   recovery for invalid dimensions, non-finite values, overflow and zero or
   underflowed counts. A positive real-valued initial count alone proves no
   finite-precision division safe. Label exact assignment, ADSampling-pruned
   assignment, hierarchical clustering and quantized-input clustering as
   distinct configurations.
3. **Independent behavior and resource evidence.** Compare assignment, rotation,
   count/sum updates, revival and finalization against an independent scalar
   oracle on small boundary cases. Bound initialized storage (including in-place
   versus copied rotated data, rotation/PDX scratch and worst-case unpruned
   candidate buffers), index arithmetic, batches, restart and cleanup, and
   satisfy the existing admission, constant-time (no data-dependent pruning on
   secret-typed inputs) and proof obligations. Functional tests and empirical
   quality supply no missing theorem.
4. **Complete cost and decision.** Measure end-to-end training cost (including
   rotation, layout conversion, unrotation and final assignment, not only the
   clustering loop) and deployment query cost separately, including data
   movement and scratch, on each declared execution platform with matched
   resource envelopes for baseline and candidate. Retain host and target
   evidence separately; derive no fixed-slot WCET or target speedup from average
   H100 GPU or Zen 5 CPU time. Freeze the ranking and improvement threshold
   before scoring, record losses as well as wins, and leave adoption open when
   the required evidence is unavailable.

This gate selects an optional workload under existing platform guarantees. It
does not require a benchmark campaign before a consumer or commit either project
to floating-point, clustering-library or upstream implementation work.
