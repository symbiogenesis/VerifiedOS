# The Reviewer's Onramp

*Non-normative. This document teaches the repository's own machinery to the person the release gate exists to convince: an independent reviewer of [requirements-register.md](requirements-register.md), arriving with the formal-methods background the subject needs and none of the local conventions. It states no obligation. Where it and the register disagree, the register wins and this document is defective.*

*It exists because the onboarding cost is real, is paid once per reviewer and never amortized, and was previously carried nowhere: a reviewer had to reconstruct conferral, seams, co-read blessings, derived views, and the rule registry from the artifacts that use them before auditing a single entry. That reconstruction is not review, and time spent on it is time not spent on the machine.*

## 1. What is being reviewed, and what is not

The gate audits **the register**, entry by entry (R-05-150, R-05-152). Four consequences follow, and each is a habit to acquire before starting.

- **[spec.md](spec.md) is commentary.** It carries the worked derivations, the alternatives weighed, and the development of arguments the register states in one clause. It is where you go to *understand* an entry and never the thing you sign off. A review record cites requirement IDs, not prose sections.
- **The derived views state nothing of their own.** [coverage-matrix.md](coverage-matrix.md), [crown-jewels.md](crown-jewels.md), [absence-contract.md](absence-contract.md), [isa-profile.md](isa-profile.md), and the contracts under §15 are computed from the register and are defective, never authoritative, where they disagree with it (R-15-001a). A finding against a view is a finding against the entry it derives from.
- **A feature present in Sail is specified, not thereby verified.** Sail gives it executable formal semantics; that fact alone proves neither a property of those semantics nor that hardware implements them. The former needs a named theorem over Sail, and the latter the `RTL ⊑ Sail` artifact; [crown-jewels.md](crown-jewels.md) and [implementation-checklist.md](implementation-checklist.md) carry their status.
- **The register is not complete because it is finished.** Whether every obligation inside a normative section was captured at all is the first question this gate asks (R-05-151), and a claim that could not be captured is booked as an extraction defect rather than dropped.

## 2. How to read one entry

```
**R-ss-nnn** MUST: the obligation, stated so that you can agree or disagree with it alone
· Accept: what you check to decide whether the obligation is met
· Fail-closed: (where the obligation specifies a refusal) what stops, and what the stop costs
· RoT-fresh: (where the obligation places state under the monotonic counter) which state, and what advances it
· Trace: CJ-… (the crown-jewel specs it constrains)
```

Six things about that shape are not guessable and cost a first-time reviewer the most time.

1. **Modality is three-valued.** `MUST` and `MUST NOT` are obligations on the built system or its process. **`IS` is a definition or classification the rest of the register quantifies over**, and it is reviewable for *correctness*, never for compliance. Asking "is this implemented" of an `IS` entry is a category error, and it is the commonest one.
2. **The criterion is the reviewable object.** An entry with no `· Accept:` line is a finding rather than an entry awaiting one. Where an entry carries several criterion lines they are **conjunctive**: each decides, one failing fails the entry, and none is commentary you may skim.
3. **A criterion must decide without reference to the prose.** If you find yourself opening [spec.md](spec.md) to determine whether a criterion is met, that is either your unfamiliarity or a finding, and the way to tell is whether the prose supplies a *fact the criterion needs* or merely the argument for why the criterion is the right one. The second is normal; the first is the defect.
4. **Length is not the test.** The longest entries are long because their criterion enumerates: a sorting rule against the roster it sorts, a parameter set against the parameters in it, a disposition against the alternatives it is taken over. A clause that decides nothing is a finding at any length, and the repair is to delete it or make it decide, never to move it into the prose.
5. **`· Fail-closed:` and `· RoT-fresh:` are not annotations. They confer membership** in sets that other entries collect: the fail-closed seam register and the freshness enumeration respectively. A conferral no register collects, and a register member no entry confers, are both findings, and `tools/check.py` decides both directions. This is why the sets are asserted entry by entry rather than listed once: a list that certifies its own totality by inspection silently stops being the set.
6. **The trace is derived and is not a citation you check by hand.** It names the crown-jewel specifications the requirement constrains, and its pointer into the prose is the bookmark the requirement's own number gives. A trace written out where the derived form would do is itself a finding, reported exactly as a hand-copied figure is.

## 3. Five conventions that will otherwise read as errors

- **IDs are permanent and order is the prose's.** Entries appear in the order of the text they extract, so a section may run `031, 032, 034, 035, 033` and that is correct. A letter-suffixed ID (`R-05-022a`) is an entry inserted between two others and is a full entry counted as one. A retired requirement keeps its number and is struck. Renumbering would break every review record that cites it, so it never happens.
- **Derived facts are computed, not copied.** Every count, table, list, and cross-artifact figure the documents assert is recomputed from the artifact that owns it by `tools/check.py`, which reports drift and rewrites it under `--fix`. Do not audit arithmetic by hand: run the tool, and treat a figure it does not own as the finding.
- **A set stated in one place is cited from elsewhere, never repeated.** Where an entry needs a set another entry states, it cites that entry. Two statements of one membership are free to drift, which is the failure the conferral machinery exists to foreclose.
- **`§n` is resolved by hand.** The checker holds only that *some* document numbers that section, because the numbering is shared. A bare `§n` names the register's section; the profile's where the sentence says the profile states it.
- **The letter-suffix density is high, and that is a signal rather than a defect.** 437 of the register's 1390 entries are post-hoc insertions, which is evidence about edit rate against review stability. [critique.md](critique.md) reads it that way and does not charge it as an error.

## 4. The co-read ledger, and what blessing means

An entry and the prose it cites are **read together**, and that reading is recorded. When either side is edited the pair goes stale, and rule K-61 reports it as owed.

```console
$ python tools/run.py coread --show R-15-073c    # print the two sides against each other
$ python tools/run.py coread --bless R-15-073c   # record that you read them
```

**Blessing is a judgment and is deliberately not available under `--fix`.** That is the point of the mechanism: a stale pair cannot be cleared by repairing arithmetic, and a prose edit that silently changes what an entry means has to meet a person. A prose edit dirties a median of four pairs, so expect several after any substantive change and do not treat the count as alarming.

As a reviewer you are not obliged to bless anything. You are obliged to know that a green checker over a freshly-edited document means the *arithmetic* is repaired and the *readings* may still be owed, and that the owed list is where a semantic change would hide.

## 5. What the machinery cannot decide, and where you come in

`tools/check.py` decides reference, membership, and arithmetic. It cannot decide whether a statement is the **right** statement, and no checker can. That residue is the whole of your subject, and [critique.md](critique.md) already prices three parts of it against the project rather than for it:

- a criterion that checks the *presence of a booking* rather than the truth of the claim it books;
- an enumeration closed by convention, whose totality no tool quantifies over;
- a proof against a wrong specification, which verifies perfectly and leaks.

Read [critique.md](critique.md) before starting. It is the project's own catalogue of what it knows is weak, it is maintained against the current register, and a finding you raise that it already carries is a finding it has already priced. Where your reading and its reading differ, that difference is the valuable output of the review.

## 6. The commands, in the order a first reading needs them

```console
$ python tools/run.py                             # every host gate, one run, one exit code
$ python tools/check.py                           # the checker alone
$ python tools/run.py coread --show <id>          # a pair K-61 says is owed a reading
$ python tools/run.py view                        # the register, rendered as the derived views read it
$ python tools/run.py rtl provenance              # each claimed absence, and the build that binds it
$ python tools/run.py oracle list                 # the differential oracles, and how large each is
```

There is no continuous integration in this repository. Nothing runs these but a person, by hand, before anything lands, which is a fact about the assurance position and not only about the workflow. [tools/README.md](../tools/README.md) states what each command does and which lane it runs in; [tools/check-rules.md](../tools/check-rules.md) is the rule registry, one row per rule, and is the right place to look when a rule's name appears in output you did not expect.

## 7. Where a finding goes

[findings-register.md](findings-register.md) holds the findings the project has raised against itself, indexed against the plan's items. A review finding is stated against a **requirement ID**, names which of the three it is, and stops there:

1. **the obligation is wrong**, in which case say what the right one is;
2. **the criterion does not decide the obligation**, in which case say what it admits or refuses that it should not;
3. **the obligation is uncaptured**, a normative claim in the prose that no entry restates, which is an extraction defect (R-05-153) and is the finding this gate most wants.

A finding against the prose alone is not a finding of this gate. A finding against a derived view is a finding against the entry beneath it. And a finding that some artifact does not exist yet is almost never one: [crown-jewels.md](crown-jewels.md) carries the status column that already says so, and [critique.md](critique.md) states the dominant fact that every hedge is spent while no primary is verified. That position is booked; what is wanted from you is whether the statements are the right ones.
