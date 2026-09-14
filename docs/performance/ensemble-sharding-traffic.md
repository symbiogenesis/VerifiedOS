# Ensemble sharding traffic: what a shard exchange costs per token, per link and per frame

*The report Q23e owes: for layer-wise and tensor-wise sharding of the declared model over two, four and eight members, the bytes exchanged per token per link, the serial exchanges and frames that costs per decode step, and the single-session token rate as the composition of the three terms R-15-171a names. It buys arithmetic and no kernel, no grant and no silicon. Every byte here is a target byte for the partition, derived from a file's own tensor sizes; no figure is a device measurement and no host time from [the inference demand report](inference-demand.md) enters any of them.*

**The result the schedule emitter needs is that link bandwidth decides nothing and the frame count decides everything.** At the floor's rate the busiest shape below moves 6.45 MB/s on its busiest link, which no plausible link is short of; what separates the shapes by two orders of magnitude is the number of serial exchanges one decode step contains, because R-11-017a charges each of them a slot period plus a guard band and R-12-015d charges each frame of it to the crypto core. So the traffic tables below are read as slot-table demands rather than as bandwidth demands, which is what R-15-171a means by *the frames per step fixed by those tables and never by the tokens*.

Every figure is taken on [traffic.json](ensemble-sharding-traffic/traffic.json), which is [shard.py](ensemble-sharding-traffic/shard.py)'s output whole over the tracked [static-Q4_K_M.json](inference-demand/static-Q4_K_M.json), at revision `f528852`, with each figure's predicate stated where it is derived and carried in that file's `predicate` field.

## 1. What is derived here, and what is not

Derived: the partition of the declared model over members, the bytes one decode step exchanges per link in each direction, the serial exchanges that step contains, the frames those exchanges cost at a declared frame payload, the crypto-core operations they charge each member, the slot period and guard band the floor's rate leaves for them, and each member's second-class read against R-18-004b's grant floor.

Not derived, each because no artifact in this tree states it, and each recorded as a term of the arithmetic rather than filled in:

- **The frame payload.** R-15-228d makes the frame size a per-link composition constant of the attested schedule artifact and R-15-228e makes the frame one codeword of this design's own block code, owing its geometry to no standard's table; the link contract that would state it is Q23b's, and no landed artifact declares a size. The register admits no candidate set either, so the sweep below is this report's declared convention on the precedent of [the inference demand report](inference-demand.md)'s unit-base convention, and every frame figure is a function of the payload the reader substitutes.
- **The encode and decode cost per frame.** R-15-228e makes each one entry in the endpoint's device row of the timing-annotated model, and R-15-119c says outright that *the magnitudes are R-17-041's to fix and not this entry's*. The model's table landed at M0.9 and it carries **27 core operation classes and no device row of any kind** ([core/timing.sail](../../model/model/core/timing.sail)), its `qualified` field is `false` in the shipped configuration ([verifiedos.json](../../model/config/verifiedos.json)) and every number in it is a placeholder that file says is one, and R-17-041's crown-jewel row over the magnitudes is unauthored. So there is no magnitude to quote and none is invented; what the two constants do have is a **shape**, one fixed latency per direction independent of the frame's symbols and of whether it was correctable, which is what lets them enter the arithmetic below as symbols.
- **The crypto core's authenticated-encryption throughput.** R-12-015d bounds the link's line rate above by it as a composition constant the slot tables respect, *stated as a cost and never absorbed*. No artifact in this tree gives it a value. So the crypto core's share is stated below as the inequality each shape must satisfy and never as a fraction.
- **The per-island bank grant.** R-15-247p makes the token rate a composition-time constant of it; M6.8 has not run and R-15-108's exploration has no cell, which [the inference demand report](inference-demand.md) already records.
- **The slot period, the slot count per major frame and the guard band.** R-11-017a's fourth output, owed by Q23d over Q23b's constants.
- **The floor's own model's shape.** R-18-004a(vii) fixes a parameter count, a quantization, a rate and a context and declares no hidden width and no layer count. Link traffic is a function of both, so **no per-token link byte figure for the floor's own model is stated here**, exactly as the inference demand report declines to state that model's own tensor sizes. One quantity does carry across unchanged: the layer-wise serial exchange count is the member count and is a function of neither.

## 2. The declared parameters

Each is a parameter of this report rather than a choice taken by it, and each names what owes it. They are the axes [traffic.json](ensemble-sharding-traffic/traffic.json) is emitted over.

| Parameter | This report's declaration | Who owes the value |
| --- | --- | --- |
| Frame payload | 256 to 16,384 bytes in powers of two, the range over which the frames one exchange costs moves from 40 to 1 | Q23b's link contract, under R-15-228d |
| Activation width | 2 and 4 bytes per element, 4 the default read | No entry declares the dtype or width of a shard-to-shard activation exchange |
| Topology | a cycle of point-to-point links, two endpoints per member above two members and one at two | R-02-003a joins members pairwise, carries each link's two endpoints in the attested devicetree, and declares no count per member |
| Collective | reduce-and-broadcast at two members, ring reduce-scatter plus all-gather above two | No entry declares a collective algorithm |
| Embedding placement | replicated under tensor-wise sharding, resident on the first member under layer-wise | R-08-012a's whole-program memory plan, as the KV placement is |

**Two of those five deserve their reason rather than only their owner.** The topology is a cycle because an endpoint is a block and not a port: R-15-228c makes each one matter carrying its own absence-contract rows A-18 through A-21, so a fully connected ensemble costs each member `M-1` such blocks where a cycle costs two, and the traffic that shape saves is traffic no figure below finds binding. The collective is declared rather than read out of R-15-171a: that entry's *declared ring exchanges* are R-15-223a's ring-buffer IPC layout, each exchange sized and phased to complete within one granted slot of its window's TDM grant, and reading the phrase as a ring **topology** would be a claim the register does not make.

## 3. The model, its geometry and its partition

The declared model is the one [the inference demand report](inference-demand.md) measures, and its section 3 states why it is a four-billion-parameter file and not the floor's three-billion-parameter one. The geometry the traffic depends on is its hidden width of 2,560 and its 36 layers, read from `token_embd.ne[0]` and `n_layers` of the tracked [static-Q4_K_M.json](inference-demand/static-Q4_K_M.json), whose own predicate is the sum of the `size` field over every `gguf_ex_read_1` tensor line `llama-gguf` prints.

**The head is tied and that is a term of the partition rather than a detail.** The file carries no `output.weight`, so `token_embd.weight` is the language-model head read whole once per token as well as the input lookup's matrix. Under a layer-wise split it sits on one member, which therefore reads 319,065,600 more bytes per token than any other, and that asymmetry is what decides the two-member verdict in section 8. Under a tensor-wise split it is column-sharded by vocabulary and the asymmetry disappears.

**The layer partition is stated at the file's mean layer and the file's layers are not uniform.** `block_bytes` over `n_layers` divides exactly at 60,340,224 bytes, and layer 0's own tensors sum to 63,888,384, an excess of 3,548,160 bytes over that mean, because Q4_K_M assigns `q6_K` to some layers' down projections and attention value matrices and `q4_K` to others. The tracked static file carries layer 0's breakdown and the block total and no other layer's sum, so the exact contiguous partition is not derivable from it: fixing it needs a re-read of the tensor listing, which needs the weight file and `llama-gguf` in a build lane. Every layer-wise per-member figure below is therefore the **uniform-layer partition**, labelled as such, with layer 0's measured excess as the evidence that a real partition differs from it by single-digit percentages and not by more.

**Eight is the largest tensor-wise member count this model's geometry admits without splitting an indivisible object.** The model has 8 key-value heads, so at eight members each holds exactly one; its FFN width of 9,728 divides by 2, 4 and 8 exactly (4,864, 2,432 and 1,216); and 36 layers over 8 members is five layers on four members and four on the other four, which is where the layer-wise slowest shard is.

## 4. What each shape exchanges, and why

**Layer-wise (pipeline).** Contiguous layers per member. One decode step drives the hidden vector across the `M-1` internal stage boundaries and then back to the member holding the tied head, so the step is `M` serial exchanges around the cycle and every link carries exactly one of them. The sampled token id crosses no link, the next step's input lookup being on the member that sampled it.

**Tensor-wise.** Every layer's attention heads and FFN columns split across members, so the partial sums after the attention output projection and after the FFN down projection must be summed across members: **two all-reduces of the hidden vector per layer**, 72 per decode step at 36 layers, and they are serial because layer `n+1`'s input is layer `n`'s output. At two members the all-reduce is one exchange of the whole partial in each direction; above two it is `2(M-1)` ring hops of one `S/M` chunk each. R-02-003a forbids a member forwarding a frame, so each hop is a fresh frame under the receiving member's own schedule and is charged as one.

## 5. The per-step traffic pattern

`S` is the activation vector, the hidden width times the activation width, 10,240 bytes at 4 bytes per element. Serial position, direction, bytes and the transmitting member are in [traffic.json](ensemble-sharding-traffic/traffic.json)'s `pattern` block per shape, as the motif and its repetition count rather than as an expanded list, which is the form an emitter reads and the form that does not grow to a thousand rows at eight members.

| Shape | Members | Links | Endpoints per member | Serial exchanges per step | Bytes per exchange | Bytes per link per direction per step | Bytes per link per step | Ensemble bytes per step |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Layer-wise | 2 | 1 | 1 | 2 | 10,240 | 10,240 | 20,480 | 20,480 |
| Layer-wise | 4 | 4 | 2 | 4 | 10,240 | 10,240 | 10,240 | 40,960 |
| Layer-wise | 8 | 8 | 2 | 8 | 10,240 | 10,240 | 10,240 | 81,920 |
| Tensor-wise | 2 | 1 | 1 | 72 | 10,240 | 737,280 | 1,474,560 | 1,474,560 |
| Tensor-wise | 4 | 4 | 2 | 432 | 2,560 | 1,105,920 | 1,105,920 | 4,423,680 |
| Tensor-wise | 8 | 8 | 2 | 1,008 | 1,280 | 1,290,240 | 1,290,240 | 10,321,920 |

At the floor's five tokens per second the busiest row is 6.45 MB/s per link per direction and the quietest is 51.2 kB/s. **Under a layer-wise split the per-link bytes are the activation vector and nothing else**, whatever the member count and whatever the model's depth, because each link carries one exchange per step; what grows with the member count is the exchange count, not the bytes. Under a tensor-wise split the per-link bytes barely move with the member count either, the ring's `2(M-1)/M` factor rising from 1 to 1.75 across the range while the chunk shrinks in step.

## 6. Frames per step, at the frame payload Q23b fixes

One exchange of `E` bytes costs `ceil(E / P)` frames at a payload of `P`, each frame a fixed-size codeword whatever it carries (R-15-228d). A link's frames per direction per step are that times the exchanges the link carries, which is one for layer-wise and all of them for tensor-wise. The member's crypto core encrypts and tags every frame it transmits and verifies every frame it receives (R-12-015d, R-15-228e), and under the declared cycle a member transmits on one direction and receives on one, so its charge is twice the per-direction frame count.

| Shape | Members | Frames per exchange at 512 / 2,048 / 8,192 | Frames per link per direction per step at 2,048 | Crypto operations per member per second at 2,048 |
| --- | --- | --- | --- | --- |
| Layer-wise | 2 | 20 / 5 / 2 | 5 | 50 |
| Layer-wise | 4 | 20 / 5 / 2 | 5 | 50 |
| Layer-wise | 8 | 20 / 5 / 2 | 5 | 50 |
| Tensor-wise | 2 | 20 / 5 / 2 | 360 | 3,600 |
| Tensor-wise | 4 | 5 / 2 / 1 | 864 | 8,640 |
| Tensor-wise | 8 | 3 / 1 / 1 | 1,008 | 10,080 |

**The layer-wise crypto charge per member is independent of the member count**, at every payload, because a member sends one exchange and receives one whatever the ensemble's size. That is the single most useful fact in this report for a schedule emitter: layer-wise sharding scales the ensemble without scaling any member's crypto slot.

**These are minima on the slot grant and not the grant itself.** R-15-228d puts an authenticated idle frame in every transmit slot an established session has nothing to send in, so a table granting more slots than the table above needs is charged the full crypto operation for each surplus one; the frames per step are the table's and never the tokens', and what this report supplies Q23d is the floor beneath its table rather than the table.

## 7. What one decode step leaves for a slot

R-11-017a gives a chain across a link its slot period plus its guard band as the per-hop term. The serial exchanges of one step must fit inside the decode period, so at the floor's rate:

> `E · (slot period + guard band) + compute per step  ≤  1 / r`

with `r` = 5 tokens per second. Dropping the compute term gives the largest cadence each shape could admit even on a member that computed instantaneously, which is an upper bound and not a budget:

| Shape | Members | Serial exchanges per step | Serial exchanges per second | Slot period plus guard band, upper bound |
| --- | --- | --- | --- | --- |
| Layer-wise | 2 | 2 | 10 | 100 ms |
| Layer-wise | 4 | 4 | 20 | 50 ms |
| Layer-wise | 8 | 8 | 40 | 25 ms |
| Tensor-wise | 2 | 72 | 360 | 2.78 ms |
| Tensor-wise | 4 | 432 | 2,160 | 463 us |
| Tensor-wise | 8 | 1,008 | 5,040 | 198 us |

The two columns are the same measurement read two ways and the second is the one an admission check uses, because R-11-017a refuses an artifact whose guard band on any link falls below the composition's skew bound plus that link's latency bound: at 198 us the guard band, the skew bound and the endpoint's two latency constants have to fit inside a fifth of a millisecond, and none of those four has a magnitude yet.

## 8. What a two-member ensemble admits at the floor's rate, and what it refuses

The three terms of the answer are each stated against its own floor, and the two that can be decided are decided.

**On the bank grant, two members put both shapes near the floor and one of them across it.** Each member's second-class read per token is its own weight bytes plus its share of the cache, at the floor's rate and its declared 8,192-token context, against R-18-004b's *at least 8 GB/s granted to the M-class island*. The comparison baseline is the one machine's 12.46 GB/s weight stream that [the inference demand report](inference-demand.md)'s section 8 states for this file, which is 1.56 of that floor.

| Shape | Members | Member | Weight stream, in grant floors | With a `q8_0` cache | With an f16 cache |
| --- | --- | --- | --- | --- | --- |
| Layer-wise | 2 | the head holder | 0.88 | 1.08 | 1.26 |
| Layer-wise | 2 | the other | 0.68 | 0.88 | 1.06 |
| Tensor-wise | 2 | either | 0.78 | 0.98 | 1.16 |
| Layer-wise | 4 | the head holder | 0.54 | 0.64 | 0.73 |
| Tensor-wise | 4 | any | 0.39 | 0.49 | 0.58 |
| Layer-wise | 8 | the head holder | 0.39 | 0.44 | 0.49 |
| Tensor-wise | 8 | any | 0.20 | 0.25 | 0.29 |

**Two members bring the weight stream inside the grant floor under both shapes**, which is what the split buys on the member, and with a `q8_0` cache added tensor-wise fits at 0.98 while layer-wise does not, at 1.08 on the member holding the tied head and 0.88 on the other. The 319,065,600 bytes of that head are the whole of the difference, so the asymmetry is a placement question the whole-program memory plan (R-08-012a) can answer and not a property of layer-wise sharding. At four members and above every row is inside the floor under both shapes with either cache format, and R-15-171a's rule that no single session's rate rises above what one member's grants fix stands unmoved by any of it: what the split buys is capacity and grant headroom, not rate.

**On the crypto core's share, the two shapes differ by a factor of 72 and that is the deciding term.** At equal frames per exchange a tensor-wise two-member ensemble charges each member's crypto core 72 times the operations a layer-wise one does, 3,600 per second against 50 at a 2,048-byte payload, and the ratio is `2L`, the all-reduce count, at every payload where both shapes take the same frames per exchange. Since no artifact declares the crypto core's authenticated-encryption throughput, the verdict is an inequality over declared operands and not an assertion. Writing `t_aead` for the crypto core's per-frame authenticated-encryption time at the declared frame size, `t_enc` and `t_dec` for the endpoint's encode and decode constants, and `phi` for the fraction of a member's slot allocation its crypto core grants the link server, a shape is admitted at the floor's rate only where

> `2 · F · r · t_aead  ≤  phi`   and   `E · (slot period + guard band) + compute  ≤  1 / r`

with `F` the per-direction frames per step of section 6 and `E` the serial exchanges of section 7, and where the endpoint's own `t_enc + t_dec` fits inside the guard band R-11-017a already refuses an artifact for undersizing. So:

- **Layer-wise at two members is admitted on every term this tree can decide.** Its cadence bound of 100 ms is slacker than any plausible slot period, its crypto charge is 50 operations per second at a 2,048-byte payload, and its only tension is the head holder's 1.08 grant floors with a `q8_0` cache, which R-18-004b meets by a composition declaring a grant above the stated minimum exactly as the single machine's 1.56 must be met.
- **Tensor-wise at two members is refused or admitted by `t_aead` alone.** It fits the grant at 0.98 floors and it needs a slot period plus guard band under 2.78 ms before any compute is charged, so the deciding question is whether the crypto core can authenticate 3,600 frames per second per member at the declared frame size while leaving the rest of the member's roster its slots. That is the figure R-12-015d owes and nothing here supplies.
- **Above two members tensor-wise is refused on cadence before `t_aead` is reached.** At eight members the 198 us bound has to contain the guard band, the skew bound and both endpoint latency constants, and an ensemble schedule that meets it is a claim about four magnitudes none of which exists.

## 9. The admitted token rate, as a law and not a figure

R-15-171a makes the admitted token rate of a sharded model a constant of three terms, and each is owned elsewhere. The rate is the **minimum** of the three and not a product of them, each being an independent ceiling on the same decode period, and it is read on the slowest member because a pipeline runs at its slowest stage:

| Term | The ceiling it puts on the rate | Its owner | The gate that decides it |
| --- | --- | --- | --- |
| The slowest shard's bank grant | `min over members of G / (W + K)`, `G` the member's M-class grant and `W + K` its per-token second-class read | R-15-247p, the grant a composition-time constant | M6.8 and the R-15-108 exploration, neither run; the supply side at the R-15-247m qualification |
| The link slots | `1 / (E · (slot period + guard band) + compute)` | R-11-017a's fourth output | Q23d's emission over Q23b's constants, refused where the guard band falls below the skew and latency bounds |
| The crypto core's per-frame share | `phi / (2 · F · t_aead)` | R-12-015d, the throughput a composition constant the slot tables respect | The link contract and the crypto core's own qualification; no artifact states it |

This report supplies `W`, `K`, `E` and `F` for six shapes and supplies none of `G`, `phi`, `t_aead`, the slot period or the guard band. **No token rate is stated as a number anywhere in it**, which is what R-15-171a's own Accept line makes the rate: a composition-time constant of grants, not a performance property this or any artifact measures.

## 10. Mixture of experts, refused by name

No mixture-of-experts shard set is stated here. R-15-171 admits such a model only with every expert resident and top-k fixed and R-15-171a adds that every expert is resident on the member the composition names, so a shard set would have to name a member per expert and a fixed top-k. R-12-085 makes the expert count and top-k terms of the declared ceiling, no artifact in this tree declares either, [the inference demand report](inference-demand.md)'s section 1 records that no such weight was loaded, and the floor's model is dense. Stating a shard set on invented operands is the one move this report's subject makes tempting and it is not made. What does carry over is the arithmetic itself: with every expert resident and top-k fixed, work per token is a constant regardless of which experts route, so the exchange counts of section 5 hold unchanged over the resident expert set and only `W` moves.

## 11. The reproducible invocation

```console
$ python docs/performance/ensemble-sharding-traffic/shard.py \
    docs/performance/inference-demand/static-Q4_K_M.json $(git rev-parse HEAD) \
    > docs/performance/ensemble-sharding-traffic/traffic.json
```

[shard.py](ensemble-sharding-traffic/shard.py) is an extension of [the inference demand instrument](inference-demand/static.py) and not a second harness: it loads no weight file, runs no model, takes no time and reads only that instrument's own tracked output, which is why it runs on the host in milliseconds where the instrument it extends needs the GGUF files and `llama-gguf` in a build lane. It is not modified in place for the same reason the report does not regenerate `static-<quant>.json`: those files are their own script's output byte for byte and reproducing them needs the weights. No `run.py` command runs either of them, on the rule [the inference demand report](inference-demand.md) states at the end of its section 9.

The revision is an argument rather than a `git` call inside the script, so the recorded revision is the invocation's and a re-run at another revision says so rather than silently restamping.

## 12. The files

[ensemble-sharding-traffic/](ensemble-sharding-traffic/) carries the machine-readable half, ASCII and LF:

- [traffic.json](ensemble-sharding-traffic/traffic.json), the geometry, the declared parameters with what owes each, the floors with their owners, the four undeclared terms with what they wait on, and per shape and member count the exchange pattern, the per-link bytes, the frames and crypto operations at each payload of the sweep, and each member's second-class read against both bandwidth floors.
- [shard.py](ensemble-sharding-traffic/shard.py), which emits it whole.
