# The Checker's Rule Registry

*The enumerated reach of [check.ps1](check.ps1): one row per check the tool carries, stating what passing means and on what ground. [proofs](../proofs/) are gated separately by [proof-gate.sh](proof-gate.sh), whose whole contract is one sentence: every shipped constant's assumption set equals the declared set R-05-164 reads from the register, which is empty today.*

## Why this document exists

The checker is untrusted machinery: a defect in it costs reviewer attention, never soundness, so it is not verified and never will be. What the review gate is owed instead is a readable account of the tool's reach, so that the gate can price what is machine-held and what is not without reading the source. This table is that account. Each rule's **Passing means** column is the claim the run's `ok` line asserts; the **Ground** column names the requirement or discipline the check serves.

The closure is the register's own conferral shape applied to the tool: this registry and the code are two artifacts, and `check.ps1`'s meta group holds them in agreement in both directions on every run, failing on a registered rule no check carries and on a check carrying no registered rule. What no closure can decide is whether a registered claim is the *right* claim; that residue is a person's, exactly as it is for every enumeration the tool checks.

## The rules

| Rule | Group | Passing means | Ground |
| --- | --- | --- | --- |
| K-00 | meta | the registry and the code agree on the rule set, in both directions | the conferral discipline, applied to the tool itself |
| K-01 | traces | every bookmark a trace cites resolves in the prose | R-05-151, R-05-152 |
| K-02 | traces | no trace writes out the citation its own id derives | R-05-151 |
| K-03 | traces | every bookmark id is unique in the document declaring it | R-05-151 |
| K-04 | traces | no bookmark sits in a fenced block, where it is text and not a target | R-05-151 |
| K-05 | traces | every requirement carries a trace | R-05-151 |
| K-06 | traces | every requirement carries at least one acceptance criterion | R-05-152 |
| K-07 | traces | every entry states its criteria before its conferrals and its trace | R-05-152 |
| K-08 | traces | every prose r-* bookmark names a live requirement | R-05-151, R-05-152 |
| K-09 | traces | every written-out trace displays the section its bookmark sits in | R-05-151 |
| K-10 | names | the register declares each requirement id exactly once | R-05-152 |
| K-11 | names | every R-, CJ-, A-, B- and P- id used names one its declarer holds | R-05-152 |
| K-12 | links | every link resolves to a file, and every fragment to a bookmark or heading | cross-document hygiene; a dead link renders as working prose |
| K-13 | links | every section number a sentence names is carried by some heading | the same hygiene, for the reference Markdown cannot break visibly |
| K-14 | views | every requirement a view must carry is carried, and every view exists | R-15-001a, R-15-100a, R-17-016a, R-18-034 |
| K-15 | views | the coverage matrix carries every boundary-by-property pair exactly once | R-17-001b |
| K-16 | views | every coverage-matrix cell cites a requirement | R-17-001b |
| K-17 | views | the crown-jewel inventory accounts for every CJ- target | R-17-016 |
| K-18 | confers | every inventory row cites a requirement conferring the status | R-17-016, R-17-016a |
| K-19 | confers | every Accept-line use of the status is a conferrer's or dispositioned | R-17-016 |
| K-20 | confers | every fail-closed conferral is collected by a seam | R-17-030r, R-03-008 |
| K-21 | confers | every fail-closed seam stands on a conferred refusal | R-17-030r |
| K-22 | confers | every RoT-fresh conferral names the enumeration collecting it | R-10-013a |
| K-23 | confers | every candidate the judgment vocabulary catches is conferred, collected, or dispositioned by name | R-17-016, R-17-030r, R-10-013a |
| K-24 | counts | every asserted count agrees with the artifact it derives from | R-18-034 |
| K-25 | counts | every crown-jewel status is in one of the three declared classes | R-17-016a, R-18-034 |
| K-26 | counts | no counted figure is restated where no claim holds it | R-18-034 |
| K-27 | counts | the register's Coverage table carries one row per section | R-05-152 |
| K-28 | counts | every Coverage row's count matches the register | R-05-152 |
| K-29 | counts | the register and the profile agree on the open CSR rows | R-15-001a |
| K-30 | compounds | every estimate figure is a range over its scope, or n/a | the estimate document's own declared column shape |
| K-31 | compounds | every dominant term reads its own big-table row | the same declared shape |
| K-32 | compounds | the compounded product agrees with the rows beneath it | arithmetic is nobody's opinion; only the credit is a judgment |
| K-33 | compounds | every credit is the gap between the band and its product | the same split of arithmetic from judgment |
| K-34 | estimates | every checklist item carries an estimate cell the tool can read | the checklist's own declared shape |
| K-35 | estimates | every open item's midpoint is the mean of its own range | the same declared shape |
| K-36 | estimates | every item cell and subtotal agrees with the hours beneath it | the same declared shape |
| K-37 | estimates | every restated total, share, and gate figure agrees with the items | the same declared shape |
| K-38 | tables | every table row is the width its header declares | the counts above read cells by position |
| K-39 | tables | every table row belongs to a table with a header rule | the same; a ruleless run renders as prose and is read by nothing |
| K-40 | glyphs | no document carries an em-dash | house style; the rule is absolute so it needs no audited carve-out |
| K-41 | glyphs | no document carries mojibake or a replacement character | encoding damage survives a rendered read |
| K-42 | bindings | the field-bindings view carries exactly the apex record's Prop fields, in declaration order | R-18-031 |
| K-43 | bindings | every consumer cell restates what the statement does with its field | R-18-031, R-05-160, R-05-161 |
| K-44 | bindings | every instantiation cell is 'none yet' or a link to the instantiating artifact | R-18-031 |

## What the registry is not

It is not a specification of the checks' algorithms, which stay in the source where they can be read beside their data, and it is not a promise of semantic coverage: a rule can hold while the sentence it guards states the wrong thing, which is the residue the register's own gate discussion names. A rule whose claim has drifted from what its check decides is a defect of this table, repaired by editing the row, never by widening the claim to fit.
