# Inference demand: the host baseline and the target traffic budget

*The report Q4a owes: what one quality-comparable inference configuration demands of the second class in bytes per token, resident bytes and operations per token, measured on a host and stated against the supply floor the register fixes. It supplies the demand side of R-12-085's ceiling ahead of M6.8, which is where the admitted token rate is derived from the bank grant at composition. No host token rate is carried into the target estimate: the host figures show the shape of the cost, and the budget is derived from bytes, the register's own rate and the register's own floor.*

**What decides the verdict is arithmetic over three quantities the register already states.** R-18-004a(vii) makes the first release's inference member a three-billion-parameter four-bit dense model wholly resident on the second class, generating at least five tokens per second sustained over a declared context of at least 8,192 tokens. R-18-004b prices that floor in capacity and bandwidth: a usable second-class capacity of at least 4 GB of payload, each class's exclusivity fraction τ at most 20%, and at least 8 GB/s of sustained second-class read granted to the M-class island inside an aggregate of at least 20 GB/s across all islands. R-12-085 names the terms a ceiling is declared in, the resident bytes, the context length, the quantization formats, the expert count and top-k, the KV footprint per token and the R-15-247p bank grant, and R-15-247p makes the token rate a composition-time constant of that grant. The demand below is stated in exactly those terms, so that the comparison is decidable at the floor.

## 1. What is measured, and what is not

Measured here, on the host, from one dense model at every official quantization its publisher ships:

- **Static demand**, read from the file: the bytes of every tensor, the bytes read per generated token, the KV footprint per token in two cache formats, and the resident buffers the loader allocates at an 8,192-token context.
- **The host baseline**: prompt processing and generation throughput at depth 0 and depth 8,192 with `llama-bench`, whose own documentation excludes tokenization and sampling; and one end-to-end run per file with tokenization, sampling and first-token latency included and the maximum resident set taken by `/usr/bin/time`.
- **The quality comparator**: KL divergence, top-1 agreement and perplexity of each narrower weight against the widest weight of the same model that fits, over this repository's own prose.
- **The budget**: bytes per token at the register's rate against the register's bandwidth floor, resident bytes against the register's usable payload, and operations per token beside the estimates' claim that compute does not bind.

Not measured here, each with the reason:

- **The target kernels and the fixed bandwidth grant.** No inference-server kernel exists in the tree (M6.6 sits after the M8a gate) and no bank grant exists (M6.8 sits after it, and R-15-108's exploration has no cell). That half is Q4b's.
- **Energy.** No energy instrument reaches WSL on this host, so joules per token are taken by nothing here.
- **The rest of the simultaneous workload.** R-18-004a's other seven members share the aggregate bandwidth and the two capacities; only the inference member is measured, and the budget says so where the aggregate is compared.
- **Concurrency above one session.** One session, batch size one, which is the low-batch case the critique names as the one that streams the weight set each token.
- **A mixture-of-experts model.** R-12-085's expert-count and top-k terms are unmeasured; R-15-171 admits such a model only with every expert resident and top-k fixed, which makes its demand the dense arithmetic below over the resident expert set, and no MoE weight was loaded.
- **The acceptability threshold.** The comparator is recorded and the threshold that makes a configuration quality-acceptable is Q1's, owned by the product-gate contract, `docs/product-gate-contract.md`, as its inference-quality `PG-` predicate over the same comparator; quality-acceptable is Q1's to decide, and nothing here declares a configuration acceptable.

## 2. The instrument

The instrument is llama.cpp at release `v0.4.0`, commit `427291b5b34cd914a31b3fd3b61a68f6184f4b9f`, which its own binaries report as `version: 0.4.0-dev (build 10816, commit 427291b5b)`, and every JSON file under [inference-demand/](inference-demand/) carries that pair as `build_commit` and `build_number`. It is a development tool contained by use, read at its own licence file and at each vendored dependency's, and [THIRD-PARTY.md](../THIRD-PARTY.md) carries the row and the readings. It is cloned into a build lane under `/root/build/lane-q4-demand/` and is not a gitlink: nothing in this tree opens it, ships it or links it. It is the host benchmark and behavioural comparator the plan names, and not an admitted runtime; [the porting survey](userspace-porting.md) already declines it as a base.

The build is CPU-only, on the guest's own compiler: cmake 4.2.3, GNU 15.2.0, Ninja, `Release`, `GGML_NATIVE=ON` (the configure detected `-mcpu=oryon-1+rng+crc+dotprod+i8mm+nosve+nosme`), `GGML_CPU_KLEIDIAI=OFF`, `LLAMA_CURL=OFF`, `LLAMA_BUILD_TESTS=OFF`, OpenSSL absent. The targets built are `llama-bench`, `llama-completion`, `llama-perplexity`, `llama-cli` and `llama-gguf`; the server and the web front end are not built. The build ran with ccache on and was resumed once, so its 128 s wall figure (on battery, discharging) is not a clean-build figure and is not evidence of anything here.

## 3. The weight

The weight is `Qwen/Qwen3-4B-GGUF` on Hugging Face at revision `bc640142c66e1fdd12af0bd68f40445458f3869b`, the publisher's own conversions, under Apache-2.0 read at that revision's `LICENSE` (the stock text with its appendix filled in as "Copyright 2025 Alibaba Cloud") and at its README front matter, on 2026-09-05. Its five official files, with the sizes and the SHA-256 the repository's tree listing states for each at that revision, are:

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `Qwen3-4B-Q4_K_M.gguf` | 2,497,280,256 | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| `Qwen3-4B-Q5_0.gguf` | 2,823,710,976 | `7f99c1aeefbcf991f04f67104e3d6f7b899e95170359ce081b0618d4f11878f5` |
| `Qwen3-4B-Q5_K_M.gguf` | 2,889,513,184 | `aca596860e8cb40af6539e3f2ea40df305f42515deac56d49c08d39a02e6533f` |
| `Qwen3-4B-Q6_K.gguf` | 3,306,260,704 | `8a08533841623c2a689763b9318d8e27b3e052ad5b38015d4be4c04fa96f68a3` |
| `Qwen3-4B-Q8_0.gguf` | 4,280,404,704 | `8c2f07f26af9747e41988551106f149b03eb9b5cb6df636027b6bf6278473300` |

Each file is downloaded by that revision, and `sha256sum` over the downloaded bytes equals the listed digest before the file is loaded; the digests and sizes the run measured are in `inference-demand/manifest.json`. No f16 file is published at that revision, so **the widest weight is Q8_0 and it is the base of the quality comparator**, stated as such; and no q4_0 file is published, so the four-bit row is Q4_K_M, whose block tensors are `q4_K` and whose embedding is `q6_K`.

**The weight is a four-billion-parameter model, not the floor's three-billion-parameter one, and the arithmetic says so wherever it matters.** The model carries 4,022,468,096 parameters (the product of every tensor's dimensions as `llama-gguf` prints them, the tied head counted once), 36 layers, a hidden width of 2,560, 32 query heads and 8 key-value heads of 128, and a vocabulary of 151,936. The candidates at three billion were each refused on terms rather than on quality: `HuggingFaceTB/SmolLM3-3B` publishes no official GGUF, `Qwen/Qwen2.5-3B-Instruct-GGUF` is under the Qwen Research licence, and the Llama 3.2 weights are gated, so this is the smallest official permissively licensed dense GGUF above the floor's size. Where the budget is scored against the floor, the measured demand is stated first and a scaled three-billion-parameter projection beside it, labelled as a projection.

## 4. The machine and the power state

A Snapdragon X Elite X1E78100 (Oryon, aarch64, twelve cores, `asimddp`, `i8mm`, `bf16`, no SVE) under WSL 2 (kernel 6.18.33.2-microsoft-standard-WSL2) with 15 GB of guest memory and no GPU, so every figure is CPU-only at twelve threads and no host GPU token rate can arise. **Every timed figure below was taken on battery, discharging**, which the guest reports at `/sys/class/power_supply/*/status` and each stage stamp in the run log records, with nine sibling build lanes sharing the same twelve cores; the machine runs at a fraction of its clock in that state, so the throughput figures are a lower bound on this host and carry no information about any other. The bytes-per-token, resident-bytes and budget figures are power-independent and are the load-bearing evidence.

## 5. Static demand

**Weight bytes.** `llama-gguf` reads the file and prints every tensor's name, type and byte size, the size being `ggml_nbytes` as its own reader computes it; [static.py](inference-demand/static.py) sums those lines, and each file's sums are in `inference-demand/static-<quant>.json`. The predicate is *the sum of the `size` field over every `gguf_ex_read_1: tensor[i]` line the tool prints*, and each file's total is the file's size less its header (the data offset the tool prints).

**Bytes read per generated token.** Under dense decoding every block tensor is read once per token, and so is the language-model head. The head is tied: no file carries an `output.weight` tensor, so the head is `token_embd.weight` read whole, and the input lookup adds one row of it (its bytes divided by 151,936, a few kilobytes) to a figure the whole matrix already dominates. Bytes read per token are therefore the block tensors plus the output norm plus the whole embedding matrix, which is every tensor in the file; an untied model would read one embedding row and a separate head of the same shape, and the figure would be the same to within a row.

| File | Tensors | Total tensor bytes | `token_embd.weight` | Bytes read per token | Bits per parameter |
| --- | --- | --- | --- | --- | --- |
| Q4_K_M | 398 | 2,491,323,904 | 319,065,600 (`q6_K`) | 2,491,323,904 | 4.955 |
| Q8_0 | 398 | 4,274,448,384 | 413,265,920 (`q8_0`) | 4,274,448,384 | 8.501 |

The bits-per-parameter column is the tensor bytes over 4,022,468,096 parameters, and is what a four-bit format costs once its block scales and its `q6_K` embedding and down-projections are counted: the floor's *four-bit* is 4.955 bits here, and the loader's own `4.95 BPW` agrees.

**What the loader allocates is not what the target holds.** The CPU backend of this release maps the file (a `CPU_Mapped model buffer` equal to the tensor bytes) and then repacks every block-quantized matrix into an interleaved layout for its `i8mm` kernels, a `CPU_REPACK model buffer` of the same order beside it, so the host process holds the weights twice; the host's maximum resident set is read with that in mind, and the resident figure the budget scores is the tensor bytes, the KV buffer, the compute buffer and the output buffer, which is what a target holding one copy needs.

**KV bytes.** The cache holds one key and one value vector per layer per token, each of `n_head_kv × head_dim` = 8 × 128 = 1,024 elements, over 36 layers: 73,728 elements per token. At f16 that is **147,456 bytes per token** and at `q8_0` (34 bytes per block of 32) **78,336 bytes per token**; at 8,192 tokens, **1,207,959,552 bytes** (1,152 MiB) and **641,728,512 bytes** (612 MiB). The loader's own `KV buffer size` line at `n_ctx` 8,192 is the measured counterpart of that arithmetic, recorded in section 6. Under dense attention the whole cache is read once per generated token, so at depth 8,192 the KV read per token is the cache's size.

## 6. The host baseline

**`llama-bench`.** For each file and each cache format, `-p 512 -n 128 -d 0,8192 -t 12 -r 5 -o json`, the `q8_0` cache with `-fa 1`: the predicate is *`avg_ts` over 5 samples as `llama-bench -o json` reports*, with `stddev_ts` beside it, and every JSON file is tracked verbatim under [inference-demand/](inference-demand/). These figures exclude tokenization and sampling. The depth-8,192 rows against the depth-0 rows isolate the cost of reading and attending over the cache; the rows across files at equal depth isolate what narrower weights save against what their de-quantization costs, on this CPU.

| File | Cache | pp512 t/s, depth 0 | tg128 t/s, depth 0 | pp512 t/s, depth 8,192 | tg128 t/s, depth 8,192 |
| --- | --- | --- | --- | --- | --- |
| Q4_K_M | f16 | 44.9 ± 5.2 | | | |

**End to end.** One `llama-completion` run per file at `-c 8192 -n 128 -t 12 --temp 0.7` over a fixed prompt, the first 24 lines of [spec.md](spec.md) at this revision ([prompt.json](inference-demand/prompt.json) carries the text and its SHA-256), with `-no-cnv` so no chat template is applied. The figures are the `common_perf_print` lines the tool prints: `prompt eval time` is first-token latency with tokenization included, `eval time` is per-token generation with sampling included, and `total time` is the whole; the maximum resident set is `/usr/bin/time -v`'s.

**Resident bytes.** The loader's `model buffer size`, `KV buffer size`, `compute buffer size` and `output buffer size` lines at `n_ctx` 8,192, batch 2,048 and micro-batch 512, per file and per cache format, are the separate weight, KV, scratch and decoding-buffer figures the item asks for (predicate: *the buffer-size lines the loader logs under `-v` at `n_ctx` 8192, batch 2048*, in `inference-demand/e2e-<quant>.json`), and the maximum resident set beside them is what the whole process took, the repacked second copy included.

| File | Cache | Mapped model buffer | KV buffer at 8,192 | Compute buffer | Output buffer |
| --- | --- | --- | --- | --- | --- |
| Q4_K_M | f16 | 2,362.55 MiB | 1,152.00 MiB | 306.75 MiB | 0.58 MiB |
| Q4_K_M | q8_0, flash attention | 2,362.55 MiB | 612.00 MiB | 311.75 MiB | 0.58 MiB |
| Q8_0 | f16 | 4,051.20 MiB | 1,152.00 MiB | 306.75 MiB | 0.58 MiB |
| Q8_0 | q8_0, flash attention | 4,051.20 MiB | 612.00 MiB | 311.75 MiB | 0.58 MiB |

The KV buffers are the arithmetic of section 5 exactly (1,207,959,552 and 641,728,512 bytes), the output buffer is one row of logits (151,936 × 4 bytes), and the compute buffer is the graph's scratch at a 512-token micro-batch.

## 7. The quality comparator

`llama-perplexity` at `-c 2048` over this repository's own prose, [spec.md](spec.md) and [the register](requirements-register.md) concatenated at this revision (2,050,087 bytes, SHA-256 `740ba746a70121052138205f07e192ce9fa8881b9398d8d5ddad3de6b90e97e1`), so that no fourth licence is read for a text. The Q8_0 file writes the base logits with `--kl-divergence-base`, and each other file is scored against them with `--kl-divergence`: the figures are the mean KL divergence, the top-1 agreement (the same token argmax between the file and the base) and the perplexity the tool prints, over the same chunks. **The comparator is recorded and the threshold is not this report's.** Which KL divergence and which top-1 agreement make a configuration quality-acceptable is the inference-quality predicate of the product-gate contract, `docs/product-gate-contract.md`, Q1's document, and quality-acceptable is Q1's to decide.

## 8. The target traffic budget

The budget takes the register's rate and floor and this section's bytes. For a configuration with W weight bytes read per token and a KV cache of K bytes at the declared context, the sustained read the second class must grant the M-class island at r tokens per second is **r × (W + K)**, dense attention reading the whole cache each token; at the floor's r = 5 and context 8,192. The usable second-class payload is R-18-004b's 4 GB less its τ of at most 20%, **3.2 GB**, and the resident bytes are the model buffer, the KV buffer at 8,192, the compute buffer and the output buffer. Both comparisons are taken in decimal gigabytes, the unit the register writes, and a binary reading of the floor moves it by 7.4% without changing any verdict below.

| Configuration | W, bytes per token | K at 8,192 | Demand at 5 tokens/s | Against 8 GB/s | Resident bytes | Against 3.2 GB |
| --- | --- | --- | --- | --- | --- | --- |
| Q4_K_M, f16 cache | 2,491,323,904 | 1,207,959,552 | 18.50 GB/s | 2.31 × the floor | 4,021,542,318 | 1.26 × the payload |
| Q4_K_M, q8_0 cache | 2,491,323,904 | 641,728,512 | 15.67 GB/s | 1.96 × the floor | 3,460,554,158 | 1.08 × the payload |
| Q8_0, f16 cache | 4,274,448,384 | 1,207,959,552 | 27.41 GB/s | 3.43 × the floor | 5,804,666,798 | 1.81 × the payload |
| Q8_0, q8_0 cache | 4,274,448,384 | 641,728,512 | 24.58 GB/s | 3.07 × the floor | 5,243,678,638 | 1.64 × the payload |

The resident column is the tensor bytes plus the KV buffer plus the compute and output buffers section 6 records, in bytes; the Q8_0 rows take the compute buffers the Q4_K_M rows measured, the graph being the same shape.

**The projection to the floor's own member.** At this file's 4.955 bits per parameter a three-billion-parameter dense model reads 1.858 GB per token, 9.29 GB/s at five tokens per second before any cache is read; at `q4_0`'s 4.5 bits per parameter, 1.688 GB and 8.44 GB/s; at a pure four bits with no scale, which no format has, 1.5 GB and 7.5 GB/s. So under every four-bit format that exists, the weight stream of the floor's (vii) alone exceeds the 8 GB/s M-class grant floor of R-18-004b at the floor's own rate and before its KV term, and the two entries are in tension at the arithmetic this item exists to do. That is a register-level act, reported in the completion note and taken by nobody here. On storage the projection lands on the other side of the line: 1.858 GB of weights with this model's own cache geometry is 2.83 GB resident under a `q8_0` cache, inside the 3.2 GB payload, and 3.39 GB under an f16 cache, outside it, so at the floor's model size the cache format is what decides the capacity comparison and the bandwidth comparison is failed either way.

**Compute.** Two operations per parameter per token over the 4,022,468,096 parameters is 8.0 GFLOP per token, plus attention over the cache at 8,192 tokens, 2 × 2 × 36 × 8,192 × 4,096 = 4.8 GFLOP; at five tokens per second, about 64 GFLOP/s. That is small against an M-class array and against the vector unit the estimates assign de-quantization to, so compute is not the binding term at the floor's rate, which is what [the estimates](performance-estimates.md) already say; what this report adds is the number. The host's own de-quantization cost is a different quantity on a different machine and neither confirms nor refutes R-15-117a's external price.

**The slot grant** is undecidable here: the admitted token rate is the bank grant's (R-15-247p), the grant is M6.8's to derive at composition, and R-15-108's exploration has no cell.

**The verdict, per term.** *Bandwidth* is the limit: at the floor's rate the measured configuration demands about twice the M-class grant floor, and the projection to the floor's own model size stays above it. *Storage* is scored in the table against 3.2 GB. *Compute* does not bind. *The slot grant* is undecidable until M6.8 and R-15-108. Quantization reduces bytes and so traffic, the `q8_0` cache removes 2.8 GB/s at the floor's context and costs attention work on the host, and a smaller model or a shorter context reduces the demand and the function together; useful quality decides which of those is a configuration and which is a smaller product, and that decision is Q1's.

## 9. The reproducible invocation

Every command below ran in the build lane at the paths shown, `$B` being `/root/build/lane-q4-demand/llama.cpp/build/bin`, `$M` the models directory and `$L` the lane. A shell script in the lane ran them in this order, one model resident at a time, with the free memory and the power state stamped at each stage; the script is not tracked, a `.sh` being a kind no marks ruling covers, and the commands here are its whole content.

```console
$ git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp && git checkout 427291b5b34cd914a31b3fd3b61a68f6184f4b9f
$ cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF
$ cmake --build build -j8 --target llama-bench llama-completion llama-perplexity llama-cli llama-gguf
$ curl -L -C - -o $M/<file> https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/<file> && sha256sum $M/<file>
$ $B/llama-gguf $M/<file> r n > <quant>-tensors.txt && python3 static.py <quant>-tensors.txt > static-<quant>.json
$ $B/llama-bench -m $M/<file> -p 512 -n 128 -d 0,8192 -t 12 -r 5 -ctk f16 -ctv f16 -o json > bench-<quant>-kvf16.json
$ $B/llama-bench -m $M/<file> -p 512 -n 128 -d 0,8192 -t 12 -r 5 -ctk q8_0 -ctv q8_0 -fa 1 -o json > bench-<quant>-kvq8.json
$ /usr/bin/time -v $B/llama-completion -m $M/<file> -c 8192 -n 128 -t 12 --temp 0.7 -f $L/text/prompt.txt -no-cnv
$ LLAMA_TRACE=1 $B/llama-completion -m $M/<file> -c 8192 -n 1 -t 12 -p x -no-cnv --no-warmup -v
$ $B/llama-perplexity -m $M/Qwen3-4B-Q8_0.gguf -f $L/text/corpus.txt -c 2048 --chunks 10 -t 12 -tb 12 --kl-divergence-base $L/kld/base-q8_0.kld
$ $B/llama-perplexity -m $M/<file> -f $L/text/corpus.txt -c 2048 --chunks 10 -t 12 -tb 12 --kl-divergence --kl-divergence-base $L/kld/base-q8_0.kld
```

No `run.py` command runs any of it: the item is one experiment, and the plan's rule is that an experiment enters [tools/run.py](../tools/run.py) when it becomes recurring work.

## 10. The files

[inference-demand/](inference-demand/) carries the machine-readable output: `manifest.json` (the instrument, the weight, the machine and each file's measured size and digest), `static-<quant>.json` (the per-tensor sums), `bench-<quant>-kvf16.json` and `bench-<quant>-kvq8.json` (`llama-bench -o json`, verbatim), `e2e-<quant>.json` (the perf lines, the buffer sizes and the maximum resident set), `kl-<quant>.json` (the comparator's figures), `prompt.json`, and `static.py`. Every file is ASCII and LF, and a `.json` carries no licence mark because the kind admits no comment.
