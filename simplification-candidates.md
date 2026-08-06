# Simplification Candidates (non-normative)

> Companion to [verification-maximal-os.md](verification-maximal-os.md) and [isa-profile.md](isa-profile.md).
> Where [performance-recovery-todo.md](performance-recovery-todo.md) enumerates levers that buy **performance** at no cost on the scarce axis, this doc enumerates levers that buy **the scarce axis itself** — specification and proof surface — at no cost in performance.
> Both lists exist because the design's premise ("engineering is free; trust is the scarce resource") makes the two currencies non-interchangeable: a deletion that shrinks the Sail model and the proof burden is worth pursuing even when it recovers not one cycle, and *especially* when it recovers cycles too.
> An item can sit on both lists; where one does, this doc holds the deletion argument and the other holds the row.
> Nothing here is normative. Each item is a proposal against the frozen profile, and adopting one is a profile amendment that reruns the review gate (R-18-034).
> This list records **open** proposals only: an item that lands in the spec leaves it, the spec thereafter being the record.
> The list is deliberately short. This spec has already run the deletion argument to a fixed point across eighteen sections; what remains are places the argument was **not run**, not places it was run and got the wrong answer.

## The simplification gate

An item earns a place on this list iff it clears all five:

1. **Deletes specification or proof surface** — Sail semantics, a proof obligation, a state inventory entry, a `fence.t` flush-set member, or a hedge — measurably, not rhetorically.
2. **Costs nothing in performance, or gains.** A deletion that trades cycles for surface belongs in [performance-estimates.md](performance-estimates.md) as an accepted cost, not here. This is the gate that rejects most candidates.
3. **Sheds no security property.** Every theorem the spec claims still holds, unchanged.
4. **Follows the spec's own stated grounds** — *delete rather than defend* (R-15-012), *verify rather than hedge* (R-15-013), or the *no consumer* parsimony that cut `Zacas` (R-15-026) and `Zifencei` (R-15-047) — rather than inventing a new principle to justify itself.
5. **Reduces, never relocates.** A deletion that reappears as a software obligation, a new checker, or a hand-waved assumption has moved the cost, not paid it.

**Why gate 4 matters.** Every item below is an application of a rule the spec already states to a case the spec did not reach. That is the difference between a simplification and a redesign: none of these asks §15 to change its mind, and each can be argued from a requirement already in the register.

---

## Considered and rejected

Recorded so they are not re-proposed. Each fails a specific gate.

| Proposal | Fails | Why |
|---|---|---|
| **Freeze `vtype` by dropping fractional LMUL and fixing tail/mask policy** | 2, 5 | Fractional LMUL is not merely compile-time convenience: mixed-width ML, DSP, crypto, and codec chains use it to keep widening results in smaller register groups. Removing it can increase live-register pressure, add moves or spills, and therefore cost hot-loop cycles. Fixing an agnostic policy can likewise require explicit preservation where undisturbed elements are needed; fixing an undisturbed policy can require preservation work where agnostic results suffice. Moving those costs into generated code relocates rather than deletes them. Enumerating configurations after measuring kernels may still be useful profile hygiene, but until the measured set proves no generated-code delta, restricting the set is not a pure win. |
| **Sequential consistency** (at any core count or width) | 2, 4 | Grounds (1)–(4) of R-15-018, whose invariance clause states the absence of any hart-count or issue-width term: single-copy memory (R-15-087) keeps the deviation from SC local to each hart's store buffer, so nothing scales with harts. Ground (3) is decisive and invariant: it trades a *structural* obligation (a FIFO cannot expose ordering weaker than TSO, bookable in the absence contract) for an *interlock-correctness* obligation (no load bypasses the drain, on any path, proven present and complete), which runs *delete rather than defend* backwards. Wider cores make it worse, not better. |
| **Delete hardware integer DIV/REM**, do it in software | 2 | [performance-estimates.md](performance-estimates.md) already books −1% to −6% for the always-worst-case fixed-latency divider (R-15-080). Shift-subtract or Newton–Raphson in software is several times that latency; the deletion buys one datapath unit and one timing-contract row for a real cycle loss. |
| **Delete vector masking** | 2 | Tempting because R-15-085 mandates mask-*independent* timing, so masking buys no cycles — but if-converted vector code then needs explicit merges, which need masks to generate. The surface returns as instructions and the cycles go negative. |
| **Collapse the three VLENs to one** | 2 | VLEN is where the vector performance argument lives (R-15-113, R-15-115). Real surface win, real perf loss; belongs in the multi-objective DSE trade the spec already specifies (§15, [implementation-plan.md](implementation-plan.md) §1), not here. |
| **Delete indexed gather/scatter and segment load/store** | 2 | Large surface with per-element capability checks (R-15-115), but segment load/store is the AoS↔SoA path the radio and codec kernels on the V-class need most. Deleting it moves the cost into every kernel's inner loop. |
| **A hardware store-buffer bypass predictor**, or any dynamic ordering optimization | 3, 4 | Hidden state that survives a partition switch; fails admission test 3 outright (R-15-011). Already out of scope in [performance-recovery-todo.md](performance-recovery-todo.md). |
