# Tying the register to the proofs: an evidence index

*A working note at the repository root, not a tracked document. Fold what survives into
[docs/critique.md](docs/critique.md) and the plan's Q-series, then delete this file.*

---

## 0. Read this first: the tooling is not slow, the machine is throttled

Measured on this host during this session, against the reference figures the tree already
records in `tools/README.md` and `tools/vos/env.py`:

| Instrument | Now (battery) | Recorded reference (AC) | Ratio |
| --- | --- | --- | --- |
| `Win32_Battery` BatteryStatus | 1 (discharging) | 2 (AC) | n/a |
| `% Processor Performance` | 22.4% then 35.6% | ~93% | ~3x |
| `python tools/check.py` | 3.73 s | 1.4 s | 2.7x |
| `python tools/run.py` (three host gates) | 81.2 s | 35.6 s to 52 s | ~2x |

**Plugging the laptop in is worth more than any optimisation proposed below**, and it costs
nothing. The checker's own cost was already investigated to its floor: the selftest is a
sandbox count times one `check.py` run, `--jobs` shows no reproducible optimum once power
state is controlled for, and the micro-optimisations already tried and rejected are listed
so nobody re-tries them. A run far off the reference figures **on AC** is a regression; a
run far off them on battery is the power state.

The second lever is already documented and worth repeating: after a document edit run
`python tools/check.py` alone (1.4 s on AC), not the whole wave (35 s to 52 s). The wave is
for landing, not for iterating.

---

## 1. The strategy, in one sentence

**Make the requirement citations the proof artifacts already carry machine-readable, and
derive every status cell, burn-down figure, and blast-radius answer from them.**

No new line in the register. No new prover dependency. No new tracked build artifact. No
new document that has to be kept in step by hand. The register stays exactly as it is; the
proofs gain one comment line per theorem; four documents stop being hand-maintained.

## 2. Why this shape and not another

**The prior art says to build it yourself.** Four methodologies exist:

1. *Antiquotation* (Isabelle `@{thm}`, Lean Verso, Alectryon): prose compiled by the
   prover, references typed and checked. Rejected here: it makes the prover a build
   dependency of the audited artifact, and the host gates run in CI with no toolchain.
2. *Document ontology with enforced invariants* (Isabelle/DOF): a typed `requirement`
   class, a `theorem` class, and invariants whose canonical examples are literally "all
   claims correspond to evidence" and "all evidence must contain at least one proven
   theorem". This is the right conceptual model and the wrong tool, being Isabelle-only.
3. *Conferral plus derived view plus both-direction check*: DOF's invariant implemented at
   file level. **This repository already does it** in `checks/confers.py`,
   `checks/views.py`, and `checks/bindings.py`.
4. *Refinement chains* (seL4, CompCert, CertiKOS, Everest, SAW/Cryptol): these do not trace
   prose to theorems at all. They make the specification a formal artifact and trace
   formal-to-formal; the informal-to-formal step is human review, which is exactly what
   Common Criteria EAL7 and DO-333 ask for and discharge with a hand-built matrix.

**No end-to-end verified system has mechanised the prose-to-theorem link.** So the move is
to extend the machinery here, which is ahead of published practice, rather than to import
anything.

**Four bindings of this shape already work in this tree**, and they are the templates:

| Existing binding | Holds | Cost |
| --- | --- | --- |
| `checks/bindings.py` K-42/43/44 | `ApexTheorem.v`'s record against `docs/field-bindings.md` | text parse |
| `checks/keccak.py` K-91 | `Keccak.v`'s known answers against the Sail unit's | text parse |
| K-76 | `rtl/synthesis-provenance.md` against the config package and the absence contract | text parse |
| `checks/confers.py` K-18..K-23, K-45, K-73 | three enumerations against their conferrals, both directions | id compare |

The proposal is one more instance of the same pattern, generalised from one record to the
whole proofs tree.

## 3. What the second pass changed

The first sketch was more expensive than it needed to be. Four things came out and one went
in; a later pass on the tooling question corrected one more.

| Change | Why |
| --- | --- |
| **Dropped** a new `· Machine-checked:` conferral line in the register | The `· Accept:` criterion **already** states what decides the entry. A second line stating what a theorem must say is one fact in two places, which is the defect the register's own rules forbid. Removes a rule, a mutant, and an edit at every entry the register carries. |
| **Dropped** `.glob` from the critical path | `.gitignore` ignores `proofs/*.glob`, so the host wave can never read it, and carrying guest facts across in a tracked JSON recreates the sync surface this is meant to remove. Everything phase 1 needs is in the tracked `.v` text, which `cli/proofs.py` already parses. Keep `.glob` for phase 3. |
| **Dropped** co-read pairs for every (requirement, theorem) pair | A prose edit already dirties a median of four pairs. Multiplying that by proof coverage makes register editing *slower*, which is the opposite of the goal. Scope co-read to crown-jewel rows, where the semantic reading actually matters. |
| **Reframed** the proofs-to-code leg around K-91 and K-76 | Both already exist and both work by comparing constants stated in two source files at zero prover cost. That beats inventing a refinement-tier vocabulary. |
| **Added** phase 0 | **The `.v` files already cite register ids in bulk**, 338 distinct ones across the 18 of them as measured at d942c1c. A file-level citation index therefore costs one regex pass and zero authoring, and answers blast-radius questions on day one. |
| **Corrected** the advice to reuse `scan_witnesses` | It came out of the tooling-verification pass (§6). That function approximates a *type* judgment with a regex, so extending it is the wrong direction. Phase 0 stays lexical; the semantic half moves to the prover in Phase A. |

## 4. The measured cost of the new group

Benchmarked over the real `proofs/*.v` (18 files, 2.40 MB), seven interleaved passes on the
throttled machine:

| Scan shape | Median |
| --- | --- |
| Read 2.40 MB from disk | 5.7 ms |
| **Whole-text `findall` for R-ids** | **1.7 ms** |
| Line iteration, regex per line | 15.3 ms |
| Line iteration with prefix prefilter | 11.0 ms |

**Use whole-text `findall`.** The line-oriented shapes are 6x to 9x slower here, because
the C-level engine over one large string beats Python-level line iteration. This inverts
the usual intuition and is exactly the trap `tools/README.md`'s scan-shape rule warns about.

Total added cost: about **8 ms per `check.py` run** (read plus scan), so under **1 s across
a whole selftest pass**, against a wave of 35 s to 52 s on AC. **Under 2%.** On AC the
figure is nearer 3 ms.

Note the corpus is markdown-only, `corpus.py` admitting a path only where it ends `.md`
and falls outside `UNREAD_PREFIX`, so the group reads `.v` itself rather
than through `ctx.corpus`. That is the 5.7 ms, and it is the larger half of the cost.

---

## 5. The work

### Phase A: two free wins, independent of everything else

Neither gates on anything below, neither touches the register, and both come out of §6's
pass on the tooling. Do them whenever.

- [ ] **Run `rocqchk` after the compile in `run.py proofs`.** It is already in the pinned
      switch (`vos/env.py` and `vos/gallina.py` both name it as shipping there) and **is run
      by nothing**. R-05-016a licenses exactly this and says why it costs no trust: a
      re-check can only reject, so a second implementation refusing a kernel-checked term is
      a finding, and one accepting a term adds no ground the first did not already give.
      Book the honest limit beside it, which that entry also states: `rocqchk` shares the
      kernel's lineage and its bug list records defects reaching that checker equally, so
      this is a second reading rather than independence.
      *Cost: one subprocess per artifact, inside a command that already compiles them all.*

- [ ] **Turn R-05-166's inhabitation approximation into a decision.** `cli/proofs.py`'s
      `scan_witnesses` regex-approximates a **type** judgment, and the dangerous direction is
      live: over-approximate and a non-vacuity gate goes false green. One line per carrier
      record fixes it, with no proof and no new machinery:

      Definition witness_Machine : Machine := demo true true true.

      The prover then decides inhabitation by type-checking that line, and the gate only
      checks that a constant of that name and shape exists. An approximation becomes a
      decision, and the fragile binder-and-quantifier half of `scan_witnesses` retires with
      it.
      *Cost: one line per quantified record across 18 files; the gate gets smaller.*

### Phase 0: free coverage, no `.v` edits

**Landed on main at 3f96243**, in two commits. Delivers blast radius from citations that
already existed.

- [x] **`tools/vos/proofcites.py`**: one whole-text `findall` per `.v`, returning
      `{file -> set of R-ids cited}` and `{file -> [constant names]}`.

      **Named `proofcites` and not `evidence`.** This tree pairs `vos/<name>.py` with
      `vos/cli/<name>.py` as a convention, the first being the machinery behind the command
      of that name, so `vos/evidence.py` would have promised the exit-evidence sweep that
      `run.py evidence` actually runs.

      **Keep it lexical, and this is a correction to the first sketch.** A
      `(*| ... |*)` comment and a `Theorem <name>` line are not Gallina and need no Gallina
      parser, which is precisely what lets the host wave run in CI with no toolchain. Do
      **not** extend into binder, quantifier or type analysis: that is the semantic half, it
      belongs to the prover, and Phase A retires the existing approximation of it rather
      than growing a second one.

      **The comment strip stays off the host wave**, which corrects this note's own earlier
      instruction to share `cli/proofs.py`'s `_strip_comments` and `_sentences` for both
      halves. Measured, that strip costs about 417 ms over `proofs/`, roughly 86x the
      budget §4 sets, because it is a per-character Python walk. The citation half does not
      need it: a Gallina identifier cannot carry a hyphen, so an `R-nn-nnn` token in a `.v`
      is inside a comment or a string by construction, which makes the whole-text scan equal
      to the stripped one as a rule rather than as a property of one tree. The two helpers
      were promoted to `vos/proofs.py` and serve the constant half alone, off the wave.
- [x] **Extend `run.py blast`** to answer `blast R-07-015` with the proof artifacts that
      cite it, alongside the apex fields it already reports.
      *Buys: the question "what does this register edit re-open?" goes from unanswerable to
      one command.*
- [x] **One rule** holding every cited R-id in `proofs/*.v` to a live requirement.
      Catches citations of retired or misspelled ids, which nothing catches today. Landed as
      **K-103**, over the tracked `.v` files, holding each cited id to an entry the register
      declares and has not struck. Reached from the register side too: the K-10 mutant, which
      renumbers an entry so two declare one id, now trips it as well.

**Gate: nothing. Do this first.** It was one module, one rule, one mutant.

### Phase 1: the annotation and the ledger

- [ ] **The annotation.** One structured comment immediately above a constant:

      (*| discharges: R-07-015, R-15-007i |*)
      Theorem restore_total_over_registers : ...

      `(*| ... |*)` is coqdoc's and Alectryon's existing convention, so it is not an
      invention and no prover setting changes. The annotation carries **only** the claim.
      Kind, witness status and coverage are computed, never declared, per the derived-facts
      rule.

      **The distinction that matters:** a file-level *citation* means the entry informed
      this artifact; a constant-level *discharge* means this constant claims to answer it.
      Phase 0 gives the first for free; this gives the second.

- [ ] **Annotate the existing 18 files.** They already cite the ids in prose; this promotes
      the load-bearing subset to checked claims and populates the ledger immediately.

- [ ] **`docs/proof-ledger.md`**, a derived view, one `VIEWS` row in `checks/views.py` with
      its governing requirement. Columns: requirement, artifact, constant, kind, refutation
      witness, cited-only or discharged. `--fix` rewrites it.

- [ ] **Three rules, one module, three mutants:**
      1. every `discharges:` names a live requirement and a constant the file actually
         defines;
      2. the ledger's rows equal the computed set, in a fixed order (`--fix` rewrites);
      3. the derived status tokens agree with the ledger.

- [ ] **Derive the status tokens.** Split the cell rather than replacing it:
      - [docs/crown-jewels.md](docs/crown-jewels.md) `Status`: the leading
        `authored` / `partial` / `not authored` token becomes derived; the prose beside it
        stays hand-authored and stays the review gate's.
      - [docs/field-bindings.md](docs/field-bindings.md) `Instantiated by`: derived from the
        ledger, `none yet` where empty.

      *Buys: landing a proof stops being a multi-document edit. This is the largest
      existing drift surface in the corpus and it closes here.*

- [ ] **Add an `AGENDAS` row in `checks/confers.py`** over the vocabulary of formal
      discharge, so entries that look like they should carry a theorem and do not are
      reported. This is the instrument that found R-17-030n through R-17-030q. It replaces
      the register line that was dropped, at no cost to the register.

**Gate: phase 0.**

### Phase 2: the authoring speedup

This is the item with the largest effect on how fast proofs actually get written, and it
was under-sold in the first pass.

- [ ] **Derived header region in each `.v`.** Every artifact today opens with 100 to 200
      lines of prose transcribing the register entries it answers to.
      `PartitionContext.v`'s header carries six gaps annotated "closed by ... (S1); carried
      back at S25", which is precisely a hand-maintained copy going stale and being
      repaired by hand later. Replace the transcribed half with a delimited region that
      `--fix` writes from the cited entries' normative lines:

      (*| BEGIN derived: cited entries |*)
      ... entry lines, regenerated ...
      (*| END derived |*)

      Keep the *readings*, *gaps* and *judgments* hand-authored above it. Only the
      transcription is derived.

      *Buys three things: authoring a new artifact starts from a filled skeleton instead of
      a blank file; the header can never go stale; and the transcription half of the K-61
      reading disappears, because there is nothing left to disagree.*

      **Watch:** keep the derived region to entry lines only, not criteria, or `.v` diffs
      get noisy and every register reword forces a recompile. `proofs/` takes default line
      endings, so `model/`'s verbatim-CRLF hazard does not apply, but the `--fix` writer
      still needs the LF discipline every other writer here uses.

**Gate: phase 1. Prototype on one file before committing to all 18.**

### Phase 3: the proofs-to-code leg

- [ ] **Generalise K-91 and K-76 into one cross-artifact constant table.** Any value stated
      in two artifacts (Gallina and Sail, Gallina and the RTL package, Sail and the
      SystemVerilog config package) gets a row; one rule holds every row. Both existing
      instances collapse into it. Zero prover, zero simulator, pure text extraction from
      two sources.
      *This is the honest shape of proofs-to-code here, and it already works twice.*
- [ ] **`.glob` for constant-level dependency graphs**, once there is something to point it
      at. `.glob` records every top-level constant as `def <byte-start>:<byte-end> <> <name>`
      plus every reference and a source `DIGEST`, so it gives an exact intra-proof blast
      radius and would let a `bound` tier be computed by checking whether a constant's
      transitive references reach the Sail-emitted Coq. **Defer until the Sail Coq backend
      lands**, because today every artifact would carry the same tier.

**Gate: phase 1, plus the Sail Coq backend for the second item.**

---

## 6. How much of the tooling belongs in Rocq

**Almost none of `tools/`, and the register has already decided it three times.** The
question matters here because the evidence index adds tooling, so the rule that governs the
new group is the rule that governs the old ones.

### Why verifying the checker is the wrong instrument

The decisive argument is not cost. It is that **verification does not catch the failure mode
that actually threatens a checker.** A checker's real risk is a rule that decides nothing: a
pattern encoding its own answer, a count with no predicate, a comparison made against an
empty set. A soundness proof is useless against that, because a rule that always passes is
trivially correct against a specification saying it always passes. The instrument for that
risk is falsification, and it already exists: `run.py selftest` requires every rule to
**fail** on a deliberately broken tree. That is strictly better assurance here than a proof.

Three further grounds, each already in the register:

- **Failure polarity.** A false green in `check.py` costs a drifted document, caught by
  R-05-150's review. A false red costs an author an afternoon. Nothing on the device rests
  on its verdict, and it is not among R-06-001's seven TCB items.
- **It would prove the wrong property.** `check.py` decides *agreement between documents*.
  R-17-016's whole point is that agreement is not correctness: proofs match the spec, never
  intent. A machine-checked guarantee that the corpus agrees with itself is a guarantee
  about the property that matters least.
- **Anchor budget.** Formalising it needs a semantics for the corpus format. R-05-020 admits
  a new anchor only on three shown conditions, one being that it retires an interim. It
  retires nothing.

And there is a settling precedent: **R-05-064 deleted the CryptOpt-style verified
translation-validation toolchain rather than deferring it**, booking the cost explicitly (a
net-new Coq equivalence-checker development, the checker-admitted-artifacts TCB category,
and a §18 workstream). R-05-066 states the general rule: an untrusted producer whose output
an **existing** checker re-validates is admissible and free to be arbitrarily aggressive.
**Verifying a producer instead of checking its output is the named anti-pattern.**

### The decision rule

Three tests. Verify only where (1) is yes and (2) is no; (3) raises priority.

1. Does anything rest on the verdict that a later act does not re-derive?
2. Is the output re-validated by something already in the trust base?
3. Is the decision irreversible?

| Tool | Verdict | Ground |
| --- | --- | --- |
| `check.py`, views, counts, figures, coread, blast | **No** | Review re-derives it. R-05-150 is the gate, not this. |
| `selftest` | **No** | It is itself the falsification instrument. |
| `memplan`, `placement` | **No** | R-08-014 says it outright: *the plan is checked, not trusted*; an overlap is a type error at the on-device TAL check. |
| `oracle`, `seed`, `quickchick`, `differential` | **No** | Untrusted finders by construction (R-05-018, R-05-045). Verifying an oracle is a category error. |
| `asm`, `encdec`, `capformat`, `dialect` | **No** | Already differentially checked against the Sail; `tools/oracle-specs/capformat.json` exists. R-15-007a's proof is owed over the Sail functions, not the Python. |
| `run.py proofs`' assumption gate | **No** | The trust sits in `Print Assumptions` and the kernel; the Python only compares strings. The answer is Phase A's `rocqchk`, not a proof. |
| The two admission checkers | **Yes, and already required** | TCB under R-06-001, and R-06-015d already obliges `CJ-ADMIT-IMPL`. These are a product deliverable, not `tools/`. |

### The three that should move, none of which is verification

1. **Inhabitation, from regex to type-check.** Phase A's second item. The one place a regex
   approximates a type judgment.
2. **Irreversible arithmetic.** The freeze figures are the strongest genuine candidate in the
   tree, because R-15-036i makes the dictionary a **permanent** commitment where a later
   change invalidates stored code wholesale. Do not verify the Python. State the arithmetic
   in Gallina, `Compute` it, and have the tool compare its own answer against the prover's.
   The machinery already exists: `tools/quickchick/Vectors.v` plus `gallina.py`'s
   `Compute`-output reader.
   - [ ] Add the R-15-036h density model as a Gallina definition and compare.
3. **Self-description over source-parsing.** `vos/apex.py` regex-parses a Gallina record out
   of `ApexTheorem.v`. Where a prover run already happens, the artifact should emit its own
   metadata rather than be parsed for it. The clean split, which Phase 0 and Phase A now
   implement between them:
   - **Lexical facts** (comment annotations, constant names): Python, host wave, no
     toolchain, CI-safe.
   - **Semantic facts about terms** (what a record declares, what a theorem quantifies over,
     whether a witness inhabits a type): the prover, guest wave.
   - [ ] Once Phase A lands, revisit whether `vos/apex.py`'s record parse can be replaced by
         a `Compute` in `ApexTheorem.v` that prints its own Prop-field list.

### The line

Move something into Rocq when its verdict is a **premise** of a claim nothing later
re-derives. Everything in `tools/` fails that test, because the review gate re-derives all
of it by construction. What belongs in Rocq is what the **device** rests on, and the register
already names those: the admission checkers under `CJ-ADMIT-IMPL`, and the crown jewels that
are specifications rather than tools.

---

## 7. What this decides, and what it does not

Stated plainly, because the repository's own discipline demands it and because the failure
mode here is a checker that certifies a set it cannot see the whole of.

**It decides:** that every cited id is live; that every annotated constant exists in the
file that claims it; that the ledger, the crown-jewel tokens and the field-binding cells
agree with the sources; and, through `run.py proofs` unchanged, that the artifact compiles,
is closed under the declared assumption set, and quantifies over a constructed record.

**It does not decide** that the theorem states the obligation. A proof against a wrong
statement matches it rather than checks it. That is R-05-150's job and it is R-17-016's
crown-jewel residual one level down. **Do not let the ledger's green column be read as
"discharged".** The column name should say `claims`, not `discharges`, and the view's
preamble should say so in its first paragraph the way every other derived view here does.

**It adds no completeness claim.** Conferral closes the collection's disagreement with the
sources and nothing else, exactly as `confers.py` says of the three sets it already holds.
The vocabulary sweep is the weak instrument against the residue, honestly described.

---

## 8. Calls that are yours

1. **Does the ledger live in `docs/`?** It is a derived view like the other ten, which
   argues for `docs/proof-ledger.md`. Against: it is a burn-down of work in progress rather
   than a statement about the design, which argues for `tools/`.
2. **How much of the `.v` header is derived** (phase 2). Entry lines only is the
   conservative call and the one recommended above. Entry lines plus criteria would make
   the artifacts near self-contained at the price of much noisier diffs.
3. **Whether phase 2 happens at all.** It is the biggest authoring win and the only item
   that writes into tracked `.v` sources. Everything else is read-only against them.
4. **Whether to raise the crown-jewel status token to a computed three-value tier now**, or
   leave it as the existing three words until more than one artifact would move.
5. **Whether `rocqchk` failing is a gate or a report** (Phase A). Gate is the honest reading
   of R-05-016a, since a re-check that only ever warns decides nothing. Against: it puts a
   second program on the path to a green proof run.
6. **Whether the freeze arithmetic moving to Gallina (§6) is worth doing before the second
   freeze act**, or whether it waits until there is a figure to check. It is the one place
   in the tree where a wrong tool output is irreversible.

---

## 9. Suggested order

Nothing here is blocked on anything outside this file except where noted.

| Order | Item | Gates on | Touches |
| --- | --- | --- | --- |
| 1 | Phase A: `rocqchk` | nothing | `cli/proofs.py` |
| 2 | Phase A: witness constants | nothing | 18 `.v` files, `cli/proofs.py` |
| 3 | **Done.** Phase 0: `proofcites.py`, `blast`, K-103 | nothing | landed at 3f96243, 11 paths under `tools/` |
| 4 | Phase 1: annotation, ledger, three rules, derived tokens | 3 | new view, `views.py`, `confers.py`, two docs |
| 5 | §6.2: freeze arithmetic in Gallina | nothing (call 6) | `tools/quickchick/` |
| 6 | §6.3: retire `apex.py`'s record parse | 2 | `vos/apex.py`, `ApexTheorem.v` |
| 7 | Phase 2: derived `.v` headers | 4, and call 3 | 18 `.v` files, a `--fix` writer |
| 8 | Phase 3: cross-artifact constant table | 4 | `checks/keccak.py`, K-76 |
| 9 | Phase 3: `.glob` dependency graphs | Sail Coq backend | new |

Items 1 through 3 gate on nothing and deliver the blast-radius answer and the two assurance
fixes before any register or view changes at all. **Item 3 is landed**, at 3f96243, and
items 1 and 2 are in flight on `lane/proofs-gate-0907`. Nothing below item 3 has started.

Two of this note's own instructions were falsified by building item 3, both caught only
because the implementer measured rather than complied: sharing the comment strip on the
host wave, corrected in Phase 0 above, and the module name, corrected with it. **Treat the
unexecuted phases as carrying the same density of error**, and measure the load-bearing
claim before acting on it rather than after.
