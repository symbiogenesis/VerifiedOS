# Prompt-processing term for the inference floor

Status: **proposed contract; target magnitude owed to Q4b**. Q12 can state the
measurement and refusal rules without transferring a host throughput figure to
the target. This document makes no register amendment and lowers no floor.

## The missing quantity

R-18-004a(vii) fixes parameter count, weight format, residence, sustained token
generation and minimum context. R-12-085 fixes the server's composition-time
slot, worker set and pools against its memory, context, format, expert, KV and
bank-grant ceiling. Neither entry supplies a prompt-processing deadline or
defines the start of a first-token latency interval.

Consider a member satisfying those declarations and all other simultaneous
members. Before producing the first token, it spends an additional declared
number D of its own visits processing a prompt; each visit stays within its
existing slot and preallocated state. After that prefix it produces tokens at
the required admitted constant rate over the declared context. Other members,
the bank grant, the model's format and resident bytes remain as declared. The
two entries have no clause comparing D with a prompt deadline. Increasing that
prefix within the admitted resource contract fails no stated prompt bound,
because none is stated. A sustained rate measured over token generation alone
does not bound the prefix. This construction identifies the missing clause;
it supplies no target implementation or physical feasibility result.

The defect cannot be repaired by reporting a host's `prompt eval time` as a
target limit, or by treating an unspecified finite completion as a numerical
pass condition. The [existing demand report](inference-demand.md) separates
prompt processing, token generation and end-to-end observations. Its timing
instrument and target scope remain distinct.

## Quantity and proposed text

Use **milliseconds from complete request acceptance to first token delivery**
for the user-visible pass condition. Declare prompt length in tokens under a
named tokenizer and prior context length in tokens alongside that interval.
For kernel diagnosis, also report prompt tokens processed per second with
start/end events and the prior context fixed. A kernel-only rate omits queueing,
tokenization and first-token sampling and cannot replace the end-to-end bound.

The following additions are exact text templates for a future joint register
act. `P_demo`, `C_demo` and `L_pp_ms` must be replaced by independently selected
finite values in the versioned demonstration set before candidate scoring;
an unresolved symbol is an open finding, never an accepted declaration.

| Owner | Proposed addition |
| --- | --- |
| R-18-004a(vii) | For the prompt and prior-context cases fixed by R-18-004d, complete prompt acceptance to delivery of the first generated token is at most L_pp_ms milliseconds, including all queueing after acceptance, tokenization, prompt processing and first-token sampling. The named tokenizer, P_demo prompt tokens and C_demo prior-context tokens are fixed with the cases before candidate scoring. The sustained generation floor and context floor remain separately required. A missing bound, an omitted case or any observed or proved worst-case interval above the bound fails this member. |
| R-12-085 | The declared session ceiling includes a maximum prompt length and prior-context length, with end-to-end first-token bounds for their admitted combinations and the declared maximum concurrent sessions. The bound starts when the complete request is accepted and ends when its first token reaches the granted result endpoint. An over-ceiling request is refused at opening; an inside-ceiling request cannot be converted into a refusal to avoid its admitted bound. The slot, pools and island bank grant remain composition-time constants. |
| R-18-004d | The inference member fixes the tokenizer and model object identities, prompt bytes, tokenized lengths, prior-context contents and lengths, concurrency, endpoint, power mode and simultaneous workload before the exploration. Its pass condition compares the maximum complete-acceptance-to-first-token interval against L_pp_ms milliseconds in every named case, records timeout and refusal as failures for admitted cases, and separately checks sustained token generation over the declared context. The set carries the numerical prompt and context cases and the numerical latency limit; an omitted value is a finding and cannot be supplied after the candidates are known. |

Choosing `L_pp_ms` requires a product limit, while demonstrating that the target
can meet it requires Q4b's target kernels, composition and qualified operating
point. Q1 owns the useful limit and representative cases; Q4b owns the target
measurement and WCET evidence. R-18-004c's instrument boundary requires both
the latency magnitudes and the admitted operating point and slot share. The
present item has neither target evidence nor a ratified numerical prompt
limit. It therefore records the refusal to claim that this second-half
predicate is met. No host number fills the missing field.

## Fixed grant and optional two-partition arm

The island receives one bank grant under R-15-247p. Prompt processing and token
generation may have different admitted service rates inside that grant; no
bank ownership changes with the phase. R-15-188 keeps shared memory and fabric
resources from scaling with the compute island.

Two operating points are an optional arm only as **two admitted partitions on
the composition-fixed wheel**, each with its own constant operating point.
Their crossings incur the applicable R-15-220 relock and other platform terms,
the R-15-220a context term and the R-07-040 padded boundary. R-11-009 charges
the resulting boundary constant at the visit rate. The admission comparison
must account for the R-11-011 switch-duty threshold and any resulting static
pinning and core occupancy. Extra state transfer, endpoint buffers and idle
reservations are charged to the composed roster. The energy benefit, if any,
belongs to the compute island; the memory grant remains reserved.

This arm is not selected here. A single partition that changes its point when
the prompt finishes would use a data-dependent transition excluded by A-12.
A prompt-triggered global mode transition is not the rare, attested transition
R-11-018 admits. Neither shape is a substitute for the fixed-wheel arm.

## Weight-format act and acceptance

The [ternary static record](inference-demand/) is a demand comparison, not a
replacement of R-18-004a(vii)'s four-bit member. Adopting a ternary member would
jointly amend that entry, the R-18-004d demonstration set and the ternary
alternative's disposition. It would retain the recorded size, generation,
context and supply floors, and require Q1's quality decision. A byte saving
alone confers no quality acceptance or target rate.

This authorable contract is acceptable when the unbounded-prefix defect is
identified, the timing interval and workload identity are reproducible, each
proposed entry has a failure condition, the missing magnitude has named
owners, and the operating-point arm preserves the fixed bank grant. Q12's
numerical prompt predicate remains open until the ratified limit and target
evidence fill those fields and the joint register/prose act is taken.
