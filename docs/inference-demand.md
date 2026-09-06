# Inference demand: the host baseline and the target traffic budget

*The report Q4a owes: what one inference configuration demands of the second class in bytes per token, resident bytes and operations per token, measured on a host and stated against the supply floor the register fixes. It supplies the demand side of R-12-085's ceiling ahead of M6.8, which is where the admitted token rate is derived from the bank grant at composition. No host token rate is carried into the target estimate: the host figures show the shape of the cost, and the budget is derived from bytes, the register's own rate and the register's own supply floors.*

**What decides the verdict is arithmetic over quantities the register already states.** R-18-004a(vii) makes the first release's inference member a three-billion-parameter four-bit dense model wholly resident on the second class, generating at least five tokens per second sustained over a declared context of at least 8,192 tokens, the rate being the admitted token rate the bank grant fixes. R-18-004b prices that floor in capacity, bandwidth and area: a usable second-class capacity of at least 4 GB of payload, each class's exclusivity fraction at most 20%, at least 8 GB/s of sustained second-class read granted to the M-class island, and at least 20 GB/s of sustained aggregate read plus write across all islands covering that grant concurrently with scanout, the compositor's per-frame surface traffic, the decode frame pool and the camera burst ring. R-12-085 names the terms a ceiling is declared in, the resident bytes, the context length, the quantization formats, the expert count and top-k, the KV footprint per token and the R-15-247p bank grant, and R-15-247p makes the token rate a composition-time constant of that grant. The demand below is stated in exactly those terms, so that the comparison is decidable at the floor.

## 1. What is measured, and what is not

Measured here, on the host, from one dense model at every quantization its publisher ships:

- **Static demand**, read from the file: the bytes of every tensor, the bytes read per generated token, the KV footprint per token in two cache formats, and the resident buffers the loader allocates at an 8,192-token context.
- **The host baseline**: prompt processing and generation throughput at depth 0 and depth 8,192 with `llama-bench`, whose own documentation excludes tokenization and sampling; and one end-to-end run per file with tokenization, sampling and first-token latency included and the maximum resident set taken by `/usr/bin/time`.
- **The quality comparator**: KL divergence, top-1 agreement and perplexity of each narrower weight against the widest weight of the same model, over this repository's own prose.
- **The budget**: bytes per token at the register's rate against the register's bandwidth floors, resident bytes against the register's usable payload, and operations per token beside the estimates' claim that compute does not bind.

Not measured here, each with the reason:

- **The target kernels and the fixed bandwidth grant.** No inference-server kernel exists in the tree (M6.6 sits after the M8a gate) and no bank grant exists (M6.8 sits after it, and R-15-108's exploration has no cell). That half is Q4b's.
- **Energy.** No energy instrument reaches WSL on this host, so joules per token are taken by nothing here.
- **The rest of the simultaneous workload.** R-18-004a's other seven members share the aggregate bandwidth and the two capacities; only the inference member is measured, and the budget says so where the aggregate is compared.
- **Concurrency above one session.** One session, batch size one, which is the low-batch case [the critique](critique.md) names as the one that streams the weight set each token.
- **A mixture-of-experts model.** R-12-085's expert-count and top-k terms are unmeasured; R-15-171 admits such a model only with every expert resident and top-k fixed, which makes its demand the dense arithmetic below over the resident expert set, and no MoE weight was loaded.
- **The acceptability threshold.** The comparator is recorded and the threshold that makes a configuration quality-acceptable is Q1's, owned by the product-gate contract at `docs/product-gate-contract.md` as its inference-quality `PG-` predicate over this same comparator; quality-acceptable is Q1's to decide, and nothing here declares a configuration acceptable. That contract is named rather than linked here because Q1 is the item that creates it.

## 2. The instrument

The instrument is llama.cpp at commit `427291b5b34cd914a31b3fd3b61a68f6184f4b9f`, which its own binaries report as `version: 0.4.0-dev (build 10816, commit 427291b5b)`, and every benchmark file under [inference-demand/](inference-demand/) carries that pair as `build_commit` and `build_number`. **The pin is a build tag and not a release**: `git tag --points-at` at that commit answers `b10816` alone, the `v0.4.0` tag is `5266f24da75dc449bd56cbed7addb9c8e4a6a73e`, and the pin is seven commits after it, which is why the version string reads `0.4.0-dev`. Nothing here needs the release, the licence reading being at the pin's own files, but the identity is stated as it is rather than as the release name it was taken for. It is a development tool contained by use, read at its own licence file and at each vendored dependency's, and [THIRD-PARTY.md](../THIRD-PARTY.md) carries the row and the readings. It is cloned into a build lane under `/root/build/` and is not a gitlink: nothing in this tree opens it, ships it or links it. It is the host benchmark and behavioural comparator the plan names, and not an admitted runtime; [the porting survey](userspace-porting.md) already declines it as a base.

The build is CPU-only, on the guest's own compiler: cmake 4.2.3, GNU 15.2.0, Ninja, `Release`, `GGML_NATIVE=ON` (the configure detected `-mcpu=oryon-1+rng+crc+dotprod+i8mm+nosve+nosme`), `GGML_CPU_KLEIDIAI=OFF`, `LLAMA_CURL=OFF`, `LLAMA_BUILD_TESTS=OFF`, OpenSSL absent. The build produces exactly five executables, `llama-bench`, `llama-completion`, `llama-perplexity`, `llama-cli` and `llama-gguf`, no `llama-server` binary among them and no web front end; the release's shared-library layout does link a `libllama-server-impl.so` beside them, which nothing here runs. The build ran with `ccache` on and was resumed once, so no build wall time is quoted here as evidence of anything.

## 3. The weight

The weight is `Qwen/Qwen3-4B-GGUF` on Hugging Face at revision `bc640142c66e1fdd12af0bd68f40445458f3869b`, the publisher's own conversions, under Apache-2.0 read at that revision's `LICENSE` (the stock text with its appendix filled in as "Copyright 2025 Alibaba Cloud") and at its README front matter, on 2026-09-05. Its five files, with the sizes and the SHA-256 the repository's tree listing states for each at that revision, are:

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `Qwen3-4B-Q4_K_M.gguf` | 2,497,280,256 | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| `Qwen3-4B-Q5_0.gguf` | 2,823,710,976 | `7f99c1aeefbcf991f04f67104e3d6f7b899e95170359ce081b0618d4f11878f5` |
| `Qwen3-4B-Q5_K_M.gguf` | 2,889,513,184 | `aca596860e8cb40af6539e3f2ea40df305f42515deac56d49c08d39a02e6533f` |
| `Qwen3-4B-Q6_K.gguf` | 3,306,260,704 | `8a08533841623c2a689763b9318d8e27b3e052ad5b38015d4be4c04fa96f68a3` |
| `Qwen3-4B-Q8_0.gguf` | 4,280,404,704 | `8c2f07f26af9747e41988551106f149b03eb9b5cb6df636027b6bf6278473300` |

Each file is downloaded by that revision, and `sha256sum` over the downloaded bytes equals the listed digest before the file is loaded; the digests and sizes the run measured are in [manifest.json](inference-demand/manifest.json). No f16 or bf16 file is published at that revision, so **the widest weight is Q8_0 and it is the base of the quality comparator**, stated as such; and no `q4_0` file is published, so the four-bit row is Q4_K_M, whose block tensors are `q4_K` and whose embedding is `q6_K`.

**The weight is a four-billion-parameter model, not the floor's three-billion-parameter one, and the arithmetic says so wherever it matters.** The model carries 4,022,468,096 parameters (the product of every tensor's dimensions as `llama-gguf` prints them, the tied head counted once), 36 layers, a hidden width of 2,560, 32 query heads and 8 key-value heads of 128, and a vocabulary of 151,936. The candidates at three billion were each refused on terms or on form rather than on quality, each read at the publisher's own metadata on 2026-09-06: `HuggingFaceTB/SmolLM3-3B` is Apache-2.0 and publishes **no GGUF file at all**, its file list carrying `.safetensors` alone, so a GGUF of it would be a third party's conversion under a second repository's terms; `Qwen/Qwen2.5-3B-Instruct-GGUF` at revision `7dabda4d13d513e3e842b20f0d435c732f172cbe` declares `license: other` with `license_name: qwen-research`, which is not a permissive grant; and `meta-llama/Llama-3.2-3B-Instruct` is `gated: manual` under the Llama 3.2 Community License, and accepting it is a personal act no lane takes. So this is the smallest publisher-converted permissively licensed dense GGUF at or above the floor's size. Where the budget is scored against the floor, the measured demand is stated first and a scaled three-billion-parameter projection beside it, labelled as a projection.

## 4. The machine, the power state and the contention

A Snapdragon X Elite X1E78100 (Oryon, aarch64, twelve cores, `asimddp`, `i8mm`, `bf16`, no SVE) under WSL 2 (kernel 6.18.33.2-microsoft-standard-WSL2) with 15 GB of guest memory and no GPU, so every figure is CPU-only at twelve threads and no host GPU token rate can arise.

**Two conditions qualify every timed figure and neither qualifies the bytes.** The first is power. The host was on battery for the first stretch of the run, on AC for the middle, and on battery again for the last, which the guest reports at `/sys/class/power_supply/*/status`; every stage stamps that state into the run log and **every table below that carries a timed figure carries the state beside it, per row**. The second is contention: nine sibling agent lanes ran on the same twelve cores throughout, one of them a proof build, so every throughput figure here is a lower bound taken under a load that was neither constant nor measured. **The bytes-per-token, resident-bytes, buffer-size and budget figures are power-independent and contention-independent, and they are the load-bearing evidence.** No timed figure here is offered as a characterization of this host, let alone of any other.

## 5. Static demand

**Weight bytes.** `llama-gguf` reads the file and prints every tensor's name, type and byte size, the size being `ggml_nbytes` as its own reader computes it; [static.py](inference-demand/static.py) sums those lines, and each file's sums are in `inference-demand/static-<quant>.json`. The predicate is *the sum of the `size` field over every `gguf_ex_read_1: tensor[i]` line the tool prints*.

**Bytes read per generated token.** Under dense decoding every block tensor is read once per token, so are the 145 `f32` normalization tensors, and so is the language-model head. The head is tied: no file carries an `output.weight` tensor, so the head is `token_embd.weight` read whole, and the input lookup adds one row of it. Bytes read per token are therefore every tensor of the file plus one embedding row, a row being 2,100 bytes where the embedding is `q6_K` and 2,720 where it is `q8_0`. An untied model would read one embedding row and a separate head of the same shape, and the figure would be the same to within a row.

| File | Tensors | Total tensor bytes | Block-tensor type | `token_embd.weight` | Bytes read per token | Bits per parameter |
| --- | --- | --- | --- | --- | --- | --- |
| Q4_K_M | 398 | 2,491,323,904 | `q4_K` | 319,065,600 (`q6_K`) | 2,491,326,004 | 4.955 |
| Q5_0 | 398 | 2,817,754,624 | `q5_0` | 319,065,600 (`q6_K`) | 2,817,756,724 | 5.604 |
| Q5_K_M | 398 | 2,883,556,864 | `q5_K` | 319,065,600 (`q6_K`) | 2,883,558,964 | 5.735 |
| Q6_K | 398 | 3,300,304,384 | `q6_K` | 319,065,600 (`q6_K`) | 3,300,306,484 | 6.564 |
| Q8_0 | 398 | 4,274,448,384 | `q8_0` | 413,265,920 (`q8_0`) | 4,274,451,104 | 8.501 |

The bits-per-parameter column is the tensor bytes over 4,022,468,096 parameters, and is what a four-bit format costs once its block scales and its `q6_K` embedding and down-projections are counted: the floor's *four-bit* is 4.955 bits here, and the loader's own `4.95 BPW` agrees. **No published format of this model is at or below four bits per parameter**, which is the first thing the projection in section 8 has to carry.

**KV bytes.** The cache holds one key and one value vector per layer per token, each of `n_head_kv` by `n_embd_head`, 8 by 128, so 1,024 elements, over 36 layers: 73,728 elements per token. At f16 that is **147,456 bytes per token** and at `q8_0` (34 bytes per block of 32) **78,336 bytes per token**; at 8,192 tokens, **1,207,959,552 bytes** (1,152.00 MiB) and **641,728,512 bytes** (612.00 MiB). The loader's own `KV buffer size` line at `n_ctx` 8,192 reads 1,152.00 MiB and 612.00 MiB for every one of the five files, which is that arithmetic exactly. Under dense attention the whole cache is read once per generated token, so at depth 8,192 the KV read per token is the cache's size; averaged from an empty cache over a full 8,192-token generation it is about half that, and the budget uses the steady state at the declared context, which is what R-18-004a(vii)'s *sustained over a declared context* names.

**What the loader allocates is not what the target holds, and the second copy is measurable to the byte.** The CPU backend of this release maps the file and then repacks the block-quantized matrices it has an interleaved kernel for into a `CPU_REPACK model buffer` beside the mapping, so the host process holds those weights twice. The repacked set is exactly identifiable: for the four files whose block type this backend repacks, the buffer is every tensor of the file except the 784,384 bytes of `f32` normalizations, and for `Q5_0`, whose block type it does not repack, it is the `q6_K` embedding alone.

| File | `CPU_Mapped model buffer` | `CPU_REPACK model buffer` | What the repack buffer is | One copy and the buffers | Maximum resident set |
| --- | --- | --- | --- | --- | --- |
| Q4_K_M | 2,362.55 MiB | 2,375.16 MiB | every tensor but the `f32` norms | 3,835.24 MiB | 6,047.62 MiB |
| Q5_0 | 2,687.22 MiB | 304.28 MiB | the `q6_K` embedding alone | 4,146.55 MiB | 4,294.01 MiB |
| Q5_K_M | 2,733.65 MiB | 2,749.23 MiB | every tensor but the `f32` norms | 4,209.30 MiB | 6,726.07 MiB |
| Q6_K | 3,127.93 MiB | 3,146.67 MiB | every tensor but the `f32` norms | 4,606.75 MiB | 5,727.16 MiB |
| Q8_0 | 4,051.20 MiB | 4,075.68 MiB | every tensor but the `f32` norms | 5,535.76 MiB | 7,218.31 MiB |

Each repack figure is the arithmetic of the column beside it: 2,491,323,904 less 784,384 is 2,375.16 MiB, 2,883,556,864 less 784,384 is 2,749.23 MiB, 3,300,304,384 less 784,384 is 3,146.67 MiB, 4,274,448,384 less 784,384 is 4,075.68 MiB, and `Q5_0`'s embedding of 319,065,600 bytes is 304.28 MiB. The fifth column is the tensor bytes plus the f16 KV, compute and output buffers, and the sixth is `/usr/bin/time -v`'s maximum resident set over the end-to-end run. For the four repacked files the resident set sits between that one-copy figure and the two-copy one, a mapped page the repack has consumed not needing to stay resident; for `Q5_0`, the one file with no repacked matrix, it sits just above the one-copy figure, which is the same mechanism read from the other side. **The resident figure the budget scores is one copy**: the tensor bytes, the KV buffer, the compute buffer and the output buffer, which is what a target holding the weights in the layout its own kernels read needs; the second copy is a property of this host backend and is recorded rather than charged.

## 6. The host baseline

**`llama-bench`, per file.** For each file and each cache format, `-p 512 -n 128 -d 0,8192 -t 12`, the `q8_0` cache with `-fa 1`: the predicate is *`avg_ts` over the repetitions the row states, as `llama-bench -o json` reports*, with `stddev_ts` beside it, and every JSON file is tracked under [inference-demand/](inference-demand/). These figures exclude tokenization and sampling.

| File | Cache | Reps | Power | pp512 at depth 0 | tg128 at depth 0 | pp512 at depth 8,192 | tg128 at depth 8,192 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q4_K_M | f16 | 5 | battery | 44.86 ± 5.22 | 1.12 ± 0.25 | 6.99 ± 3.09 | 1.24 ± 0.99 |
| Q4_K_M | `q8_0` | 3 | AC | 120.37 ± 3.63 | 3.25 ± 0.09 | 8.86 ± 0.42 | 2.43 ± 0.01 |
| Q5_K_M | f16 | 3 | AC | 106.89 ± 0.87 | 7.99 ± 1.18 | 25.10 ± 2.37 | 1.65 ± 0.95 |
| Q5_K_M | `q8_0` | 3 | AC | 85.01 ± 5.98 | 7.92 ± 1.59 | 11.31 ± 0.16 | 1.94 ± 0.18 |
| Q6_K | f16 | 3 | AC | 99.02 ± 1.11 | 6.30 ± 0.41 | 26.44 ± 0.14 | 2.61 ± 0.03 |
| Q6_K | `q8_0` | 3 | AC | 74.30 ± 27.74 | 1.92 ± 0.70 | 8.41 ± 2.50 | 2.55 ± 0.79 |
| Q8_0 | f16 | 3 | AC | 168.74 ± 8.39 | 4.64 ± 0.21 | 27.68 ± 0.84 | 2.71 ± 0.14 |
| Q8_0 | `q8_0` | 3 | AC | 159.86 ± 2.99 | 8.23 ± 0.92 | 10.32 ± 1.94 | 1.33 ± 0.63 |

`Q5_0` has no row: its first two attempts ran against a download that had truncated at `curl` exit 56 and refused to load, and once the file was re-fetched whole the two passes below were taken instead, being the comparison that decides.

**This table does not order by bytes per token, and that is a measurement about the conditions rather than about the model.** Its eight rows were taken in eight windows spread over nearly three hours, from 01:43Z to 04:37Z, beside nine sibling lanes and across a power-state change; one row's standard deviation reaches 37% of its mean; and the widest file, `Q8_0`, is the fastest in all four throughput columns, which is the opposite of what bytes per token predicts. **So nothing here is offered as evidence for or against the bandwidth-bound shape**; what the rows establish is that a throughput figure taken this way carries no ordering information, which is why the budget below is derived from bytes and not from any of them.

**`llama-bench`, one invocation over every file, twice.** The comparison the shape needs is one process, one window, the files interleaved by the tool's own loop rather than by a script: `-p 256 -n 64 -d 0 -t 12 -r 3` with an f16 cache and every file passed to a single invocation. It was taken twice. **The first pass spans a power transition and its bias runs the same way as its result**, the guest reporting AC at the invocation's first stamp and battery two minutes after its last, and the files are passed in ascending order of bytes per token, so a monotone slowdown over the run would fake the ordering on its own. **The second pass was taken whole inside one power state**, a sampler at ten-second intervals reporting `Discharging` on all 131 of its samples from the invocation to its last row, which is what makes it the one that decides. The last column is the derived quantity the claim is about, generation throughput times the bytes read per token, which is the rate at which the configuration actually moves weight bytes.

| File | Bytes read per token | Pass 1 pp256 | Pass 1 tg64 | Pass 1 byte rate | Pass 2 pp256 | Pass 2 tg64 | Pass 2 byte rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q4_K_M | 2,491,326,004 | 120.65 ± 11.46 | 3.251 ± 0.696 | 8.10 GB/s | 77.79 ± 8.52 | 2.449 ± 0.103 | 6.10 GB/s |
| Q5_0 | 2,817,756,724 | 26.81 ± 2.41 | 2.247 ± 0.138 | 6.33 GB/s | 25.39 ± 0.76 | 0.945 ± 0.355 | 2.66 GB/s |
| Q5_K_M | 2,883,558,964 | 56.88 ± 6.88 | 2.146 ± 0.074 | 6.19 GB/s | 38.40 ± 2.26 | 1.260 ± 0.270 | 3.63 GB/s |
| Q6_K | 3,300,306,484 | 50.54 ± 4.98 | 1.824 ± 0.096 | 6.02 GB/s | 20.78 ± 16.68 | 1.005 ± 0.078 | 3.32 GB/s |
| Q8_0 | 4,274,451,104 | 117.91 ± 11.03 | 1.777 ± 0.130 | 7.60 GB/s | 59.31 ± 9.47 | 0.811 ± 0.269 | 3.46 GB/s |

**Three things hold across both passes and one does not.** Generation throughput falls as bytes per token rise over the four files this backend repacks, in both passes and in the same order, `Q4_K_M` to `Q5_K_M` to `Q6_K` to `Q8_0`; a file reading 72% more per token generates at 55% of the rate in the first pass and 33% in the second. The `Q5_0` row is out of that order in the second pass, generating below both files that read more than it does, and at the lowest byte rate of any row in either pass; that is the absence of a repacked matmul kernel that section 5 identifies from its buffer sizes, read from the other side, and it is a kernel fact rather than a bandwidth one. The prompt-processing column does not order by bytes and is not expected to, prompt processing at a 512-token micro-batch reading each weight once for many tokens.

**What does not hold is a flat byte rate, and that is worth stating plainly.** A purely bandwidth-bound machine would move about the same bytes per second whatever the format; this host varies by a factor of 1.35 across the first pass and 1.84 across the second pass's repacked files, and `Q4_K_M` is disproportionately fast in both. **So the host does not establish that decoding is bandwidth-bound; it establishes only that throughput falls with bytes per token at a rate short of proportional.** The bandwidth-bound reading of the target is [the estimates](performance-estimates.md)' and R-15-247p's, and the budget below is derived from bytes and the register's own rate rather than from any figure in this table.

**End to end.** One `llama-completion` run per file at `-c 8192 -n 128 -t 12 --temp 0.7` over a fixed prompt, the first 24 lines of [the spec](spec.md) at this revision ([prompt.json](inference-demand/prompt.json) carries the text and its SHA-256), with `-no-cnv` so no chat template is applied. The figures are the `common_perf_print` lines the tool prints: `prompt eval time` is first-token latency with tokenization included, `eval time` is per-token generation with sampling included, and `total time` is the whole. The prompt tokenizes to 556 tokens and 127 tokens are generated after the first.

| File | Power | Load | Prompt eval | Prompt eval per token | Eval per token | Sampling | Total | Maximum resident set |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q4_K_M | AC | 11,930.71 ms | 5,390.92 ms | 9.70 ms | 290.79 ms | 27.87 ms | 42,364.20 ms | 6,192,764 KiB |
| Q5_0 | battery | 3,476.64 ms | 31,233.33 ms | 56.18 ms | 705.38 ms | 30.04 ms | 120,860.07 ms | 4,397,064 KiB |
| Q5_K_M | AC | 3,407.82 ms | 5,475.19 ms | 9.85 ms | 194.44 ms | 26.48 ms | 30,206.75 ms | 6,887,492 KiB |
| Q6_K | AC | 4,036.00 ms | 5,059.35 ms | 9.10 ms | 194.27 ms | 26.25 ms | 29,767.94 ms | 5,864,616 KiB |
| Q8_0 | AC | 4,707.95 ms | 3,891.07 ms | 7.00 ms | 283.62 ms | 25.37 ms | 39,946.40 ms | 7,391,552 KiB |

**What the end-to-end run adds over `llama-bench` is the two terms `llama-bench` excludes, and both are small here.** Sampling is 25.37 to 30.04 ms over 684 tokens against a total of 29.8 to 120.9 seconds, under a tenth of one percent in every row, and the whole difference between the sum of the parts and the total is the `unaccounted time` the tool prints, 10.18 to 14.61 ms on the four AC rows. So on this host the two excluded terms do not move a token-rate figure, and the reason to take the end-to-end run is the first-token latency and the maximum resident set, neither of which `llama-bench` reports at all. The `Q5_0` row was taken on battery and its timings are not comparable with the four above it; its resident set is, and it is the row that shows the repack second copy by its absence.

**Resident bytes.** The loader's `model buffer size`, `KV buffer size`, `compute buffer size` and `output buffer size` lines at `n_ctx` 8,192, batch 2,048 and micro-batch 512, per file and per cache format, are the separate weight, KV, scratch and decoding-buffer figures the item asks for; the predicate is *the buffer-size lines the loader logs under `-v` at `n_ctx` 8192, batch 2048*, recorded in `inference-demand/e2e-<quant>.json`.

| Cache | KV buffer at 8,192 | Compute buffer | Output buffer | Graph nodes |
| --- | --- | --- | --- | --- |
| f16 | 1,152.00 MiB | 306.75 MiB | 0.58 MiB | 1,266 |
| `q8_0`, flash attention | 612.00 MiB | 311.75 MiB | 0.58 MiB | 1,698 |

**None of the three varies with the weight format**, the graph being the same shape whatever the matrices are quantized to, and the loader reports the same figures for all five files; the model buffer, which does vary, is the table in section 5. The output buffer is one row of logits, 151,936 by 4 bytes, which the loader rounds to 0.58 MiB, and the compute buffer is the graph's scratch at a 512-token micro-batch. The `q8_0` cache costs 5.00 MiB of extra scratch and 432 more graph nodes and saves 540.00 MiB of cache.

## 7. The quality comparator

`llama-perplexity` at `-c 2048 --chunks 5` over this repository's own prose, [the spec](spec.md) and [the register](requirements-register.md) concatenated at this revision (2,050,087 bytes, SHA-256 `740ba746a70121052138205f07e192ce9fa8881b9398d8d5ddad3de6b90e97e1`), so that no fourth licence is read for a text. The Q8_0 file writes the base logits with `--kl-divergence-base`, and each other file is scored against them with `--kl-divergence` over the same 5 chunks of 2,048 tokens, 10,240 tokens in all. The predicate is *the cumulative row of the tool's `kl_divergence` table at the last chunk, top-1 agreement being its `Same top p` column*.

| File | Bits per parameter | Bytes read per token | Mean KL divergence | Top-1 agreement | Perplexity | ln(PPL/PPL base) |
| --- | --- | --- | --- | --- | --- | --- |
| Q4_K_M | 4.955 | 2,491,326,004 | 0.095627 ± 0.002759 | 85.064 ± 0.498 % | 33.6094 | 0.10535 ± 0.00876 |
| Q5_0 | 5.604 | 2,817,756,724 | 0.088814 ± 0.002093 | 84.848 ± 0.501 % | 33.8962 | 0.11384 ± 0.00835 |
| Q5_K_M | 5.735 | 2,883,558,964 | 0.015998 ± 0.000364 | 93.177 ± 0.353 % | 30.2817 | 0.00108 ± 0.00392 |
| Q6_K | 6.564 | 3,300,306,484 | 0.008798 ± 0.000544 | 95.073 ± 0.303 % | 30.3026 | 0.00177 ± 0.00292 |
| Q8_0 (the base against itself) | 8.501 | 4,274,451,104 | 0.000000 ± 0.000000 | 100.000 ± 0.000 % | 30.3696 | 0.00398 ± 0.00161 |

**The base row is the instrument's self-check and it passes**: the widest file scored against its own logits gives a mean KL divergence of zero, 100.000% top-1 agreement and the base's own perplexity to four places, so the comparator's zero is where it should be. Its `ln(PPL/PPL base)` of 0.00398 is the one figure of that row that is not zero and is an artifact of the tool's own ratio column, which the KL and agreement columns settle.

**Bits per parameter is not a sufficient statistic for quality, and one row of the ladder proves it.** `Q5_0` costs 13.1% more bytes per token than `Q4_K_M` and buys nothing: its top-1 agreement is **lower** (84.848% against 85.064%), its perplexity is **higher** (33.8962 against 33.6094), and only its mean KL divergence is marginally better. The two formats' own declarations in the pin's `ggml/src/ggml-common.h` say why. `block_q5_0` is 32 elements under one `ggml_half` scale and no offset, so it is symmetric with a single level of scaling; `block_q4_K` is 256 elements under a `ggml_half` super-block scale **and** a super-block minimum, with twelve further bytes carrying a six-bit scale and a six-bit minimum for each of its eight sub-blocks of 32, so it is asymmetric with two levels. **`Q4_K_M` therefore dominates `Q5_0` on this model at both ends**, on bytes and on quality together, and a reader ordering formats by nominal bit width would pick the worse one. It is also the file whose block type this backend does not repack, so it is dominated on host throughput as well.

**Over the k-quant ladder the comparator is monotone and the four-bit row is where quality falls fastest.** Between Q4_K_M and Q5_K_M, 0.78 more bits per parameter divides the mean KL divergence by 6.0 and lifts top-1 agreement by 8.1 points; between Q5_K_M and Q6_K, 0.83 more bits divides it by 1.8 and lifts agreement by 1.9 points. So the format the floor names, four bits, is on the steep part of this model's curve, and the format one step above it costs 16% more bytes per token for that difference. **Which of those is quality-acceptable is exactly the judgment this report does not make.**

**The comparator is recorded and the threshold is not this report's.** Which mean KL divergence and which top-1 agreement make a configuration quality-acceptable is the inference-quality `PG-` predicate of the product-gate contract at `docs/product-gate-contract.md`, Q1's document, and **quality-acceptable is Q1's to decide**. Nothing here declares a configuration acceptable, and the corpus is this repository's own prose rather than a representative task set, which is Q1's to fix as well.

## 8. The target traffic budget

The budget takes the register's rate and its supply floors and this report's bytes. For a configuration with W weight bytes read per token and a KV cache of K bytes at the declared context, the sustained read the second class must grant the M-class island at r tokens per second is **r times (W + K)**, dense attention reading the whole cache each token; at the floor's r = 5 and context 8,192. The usable second-class payload is R-18-004b's 4 GB less its exclusivity fraction of at most 20%, **3.2 GB**, and the resident bytes are the tensor bytes, the KV buffer at 8,192, the compute buffer and the output buffer. Both comparisons are taken in decimal gigabytes, the unit the register writes.

**The two bandwidth figures are floors on supply and not caps on demand.** R-18-004b says *at least* 8 GB/s granted to the M-class island and *at least* 20 GB/s aggregate, so a demand above 8 GB/s is not by itself a violation: it is met by a grant above the floor, and it fails only against a supply at the floor. The two columns below therefore say two different things. The multiple of 8 GB/s is what the grant must be raised to; the fraction of 20 GB/s is what that grant would take out of an aggregate R-18-004b requires to cover the scanout reservation, the compositor's per-frame surface traffic, the decode frame pool at the declared ceiling and the camera burst ring **concurrently** with it.

| Configuration | W per token | K at 8,192 | Demand at 5 tokens/s | Grant needed, in 8 GB/s floors | Share of the 20 GB/s aggregate | Resident bytes | Against 3.2 GB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q4_K_M, f16 cache | 2,491,326,004 | 1,207,959,552 | 18.50 GB/s | 2.31 | 93% | 4,021,541,888 | 1.26 |
| Q4_K_M, `q8_0` cache | 2,491,326,004 | 641,728,512 | 15.67 GB/s | 1.96 | 78% | 3,460,553,728 | 1.08 |
| Q5_0, f16 cache | 2,817,756,724 | 1,207,959,552 | 20.13 GB/s | 2.52 | 101% | 4,347,972,608 | 1.36 |
| Q5_0, `q8_0` cache | 2,817,756,724 | 641,728,512 | 17.30 GB/s | 2.16 | 87% | 3,786,984,448 | 1.18 |
| Q5_K_M, f16 cache | 2,883,558,964 | 1,207,959,552 | 20.46 GB/s | 2.56 | 102% | 4,413,774,848 | 1.38 |
| Q5_K_M, `q8_0` cache | 2,883,558,964 | 641,728,512 | 17.63 GB/s | 2.20 | 88% | 3,852,786,688 | 1.20 |
| Q6_K, f16 cache | 3,300,306,484 | 1,207,959,552 | 22.54 GB/s | 2.82 | 113% | 4,830,522,368 | 1.51 |
| Q6_K, `q8_0` cache | 3,300,306,484 | 641,728,512 | 19.71 GB/s | 2.46 | 99% | 4,269,534,208 | 1.33 |
| Q8_0, f16 cache | 4,274,451,104 | 1,207,959,552 | 27.41 GB/s | 3.43 | 137% | 5,804,666,368 | 1.81 |
| Q8_0, `q8_0` cache | 4,274,451,104 | 641,728,512 | 24.58 GB/s | 3.07 | 123% | 5,243,678,208 | 1.64 |

The resident column is, in bytes, the tensor bytes plus the KV buffer plus the compute buffer section 6 records for that cache format (306.75 MiB is 321,650,688 bytes with an f16 cache, 311.75 MiB is 326,893,568 with a `q8_0` cache) plus one row of logits (151,936 by 4, 607,744 bytes). **The 3.2 GB it is scored against is the whole second class's payload and not inference's share of it**: R-18-004b's second-class comparison sums R-15-247s's second list, over which the inference server is one consumer, so a multiple below one is not yet a fit and a multiple above one is a shortfall before any other consumer is placed. Which of the compute and output buffers sits on which class is the whole-program memory plan's (R-08-012a) and is not decided here; both are summed into the one figure with that stated.

**The projection to the floor's own member.** The floor's model is three billion parameters at four bits, and this file's four-bit format costs 4.955 bits per parameter. At that density a three-billion-parameter dense model reads 1.858 GB per token, which is 9.29 GB/s at five tokens per second **before any cache is read**; at `q4_0`'s 4.5 bits per parameter, 1.688 GB and 8.44 GB/s; at a pure four bits with no block scale, which no format of this model has, 1.5 GB and 7.5 GB/s. Adding this model's own cache geometry, the three-billion-parameter projection demands 12.50 GB/s with a `q8_0` cache and 15.33 GB/s with an f16 cache at 4.955 bits, and 10.71 and 13.54 GB/s at a pure four bits. So:

- **The weight stream alone exceeds the 8 GB/s M-class grant floor at every four-bit format that exists**, and clears it only at a hypothetical pure four bits with no block scale.
- **With the cache, every projection takes more than half the 20 GB/s aggregate floor**, 54% at the most favourable combination this report can construct and 63% at the measured four-bit density with the cheaper cache, out of an aggregate that R-18-004b also requires to cover scanout, the compositor, the decode pool and the camera ring concurrently.

That is a tension between two entries of the same floor: R-18-004a(vii)'s member and R-18-004b's bandwidth line are jointly satisfiable only by a grant well above the stated minimum, and the aggregate is where the room for it has to come from. **It is a register-level act and it is reported rather than taken here.** On storage the projection lands on the other side of the line: 1.858 GB of weights with this model's cache geometry is 2.83 GB resident under a `q8_0` cache, inside the 3.2 GB payload at 88% of it, and 3.39 GB under an f16 cache, outside it. So at the floor's own model size the cache format decides the capacity comparison, and the bandwidth comparison is the binding one either way.

**Compute.** Two operations per parameter per token over the 4,022,468,096 parameters is 8.04 GFLOP per token, plus attention over the cache at 8,192 tokens, two multiply-accumulates per cached element per token over 36 layers of 32 heads of 128, 4.83 GFLOP; at five tokens per second, 64.4 GFLOP/s. Compute is not the binding term at the floor's rate, which is what [the estimates](performance-estimates.md) already say; what this report adds is the number, and it is stated as a demand rather than compared against a supply, no measured M-class array throughput existing to compare it to. The host's own de-quantization cost is a different quantity on a different machine and neither confirms nor refutes R-15-117a's external price.

**The slot grant** is undecidable here: the admitted token rate is the bank grant's (R-15-247p), the grant is M6.8's to derive at composition, and R-15-108's exploration has no cell.

**The verdict, per term.** *Bandwidth* is the limit. At the floor's rate and context the measured four-bit configuration demands about twice the stated M-class grant floor, the projection to the floor's own model size stays above it under every published four-bit format, and the aggregate floor is where the shortfall has to be found. *Storage* fits at the floor's model size under a `q8_0` cache and not under an f16 one, and the fit is against the whole second class's payload rather than inference's share of it. *Compute* does not bind at the floor's rate, its whole demand there being 64.4 GFLOP/s. *The slot grant* is undecidable until M6.8 and R-15-108. Quantization reduces bytes and so traffic, the `q8_0` cache removes 2.83 GB/s at the floor's context and costs 5.00 MiB of scratch and 432 graph nodes, and a smaller model or a shorter context reduces the demand and the function together; useful quality decides which of those is a configuration and which is a smaller product, and that decision is Q1's.

## 9. The reproducible invocation

Every command below ran in the build lane at the paths shown, `$B` being the built binaries' directory, `$M` the models directory and `$L` the lane. Shell scripts in the lane ran them in this order, one model resident at a time, with the free memory and the power state stamped at each stage; the scripts are not tracked, a `.sh` being a kind no marks ruling covers, and the commands here are their whole content.

```console
$ git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp && git checkout 427291b5b34cd914a31b3fd3b61a68f6184f4b9f
$ cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF
$ cmake --build build -j8 --target llama-bench llama-completion llama-perplexity llama-cli
$ cmake --build build -j8 --target llama-gguf
$ curl -L -C - -o $M/<file> https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/<file> && sha256sum $M/<file>
$ $B/llama-gguf $M/<file> r n > <quant>-tensors.txt && python3 static.py <quant>-tensors.txt > static-<quant>.json
$ $B/llama-bench -m $M/<file> -p 512 -n 128 -d 0,8192 -t 12 -r 3 -ctk f16 -ctv f16 -o json > bench-<quant>-kvf16.json
$ $B/llama-bench -m $M/<file> -p 512 -n 128 -d 0,8192 -t 12 -r 3 -ctk q8_0 -ctv q8_0 -fa 1 -o json > bench-<quant>-kvq8.json
$ $B/llama-bench -m $M/<file1> -m $M/<file2> ... -p 256 -n 64 -d 0 -t 12 -r 3 -ctk f16 -ctv f16 -o json > bench-controlled-kvf16.json
$ ( while true; do echo "$(date -u +%FT%TZ) $(cat /sys/class/power_supply/*/status | head -1)"; sleep 10; done ) &   # beside the second pass
$ /usr/bin/time -v $B/llama-completion -m $M/<file> -c 8192 -n 128 -t 12 --temp 0.7 -f $L/text/prompt.txt -no-cnv -v
$ $B/llama-completion -m $M/<file> -c 8192 -n 1 -t 4 -p x -no-cnv --no-warmup -ctk q8_0 -ctv q8_0 -fa on -v
$ $B/llama-perplexity -m $M/Qwen3-4B-Q8_0.gguf -f $L/text/corpus.txt -c 2048 --chunks 5 -t 12 -tb 12 --kl-divergence-base $L/kld/base-q8_0.kld
$ $B/llama-perplexity -m $M/<file> -f $L/text/corpus.txt -c 2048 --chunks 5 -t 12 -tb 12 --kl-divergence --kl-divergence-base $L/kld/base-q8_0.kld
```

No `run.py` command runs any of it: the item is one experiment, and the plan's rule is that an experiment enters [tools/run.py](../tools/run.py) when it becomes recurring work.

## 10. The files

[inference-demand/](inference-demand/) carries the machine-readable output, every file ASCII and LF, and a `.json` carries no licence mark because the kind admits no comment:

- [manifest.json](inference-demand/manifest.json), the instrument, the weight, the machine and each downloaded file's measured size and digest against the listed one.
- `static-<quant>.json`, the per-tensor sums and the derived per-token bytes, one per file.
- `bench-<quant>-kvf16.json` and `bench-<quant>-kvq8.json`, the rows `llama-bench -o json` reported, and [bench-controlled-kvf16.json](inference-demand/bench-controlled-kvf16.json) and [bench-controlled2-kvf16.json](inference-demand/bench-controlled2-kvf16.json), the two one-invocation passes.
- `e2e-<quant>.json`, the perf lines, the buffer sizes in both cache formats and the maximum resident set.
- `kl-<quant>.json`, the comparator's figures against the Q8_0 base.
- [budget.json](inference-demand/budget.json), the budget's terms, its arithmetic, the measured rows and the three-billion-parameter projection.
- [prompt.json](inference-demand/prompt.json), the end-to-end prompt and its digest, and [static.py](inference-demand/static.py), the extractor the static figures come from.
