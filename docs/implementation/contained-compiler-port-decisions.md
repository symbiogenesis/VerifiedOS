# Contained compiler port decisions

Q39 owns the contained compiler's locked switch, compatibility port and acceptance
predicate in the [implementation checklist](implementation-checklist.md). This
record commissions a bounded follow-up under that predicate; it changes no proof
statement, executable definition, hypothesis, admitted lemma or compiler flag.

## Follow-up after the initial repair budget

The initial twelve-candidate repair budget stopped after candidate 12. That check
exited 2 after 57.94 seconds. Its existing-lemma strategy closed
`regset_rel_return_from_builtin`; the next failure was the unchanged register
exclusion assertion in `nextinstr_pc_return_builtin_value` at
`security/Recomposition.v:5901`. The diagnostic is retained at
`/root/build/lane-checklist-20261010-c/q39/port-candidate-12.log`.

The stopped source is based on contained revision
`d08768db051ebb5cbe92ea24eeacbd63b9eaf84a`, with the bounded working patch.
`security/Recomposition.v` has SHA-256
`2cc945af9cd3801d31c19e0fc577ecb8f7e5c981fd01c6c92927f27299c2c680`.

The integrator commissions at most two further candidates or eight active repair
minutes, whichever comes first, applying the demonstrated `preg_notin_charact`
and `preg_of_not_PC` strategy to that second assertion. Active time includes
candidate editing and check waits. The earlier census remains part of the record;
this is a scoped follow-up within Q39's existing port allowance. A new unrelated
failure ends this follow-up and returns to the integrator before any further edit.

The decision is justified by the successful preceding proof and the identical
exclusion pattern at the new failure. It uses existing lemmas and preserves the
frozen declaration. No new assumption, admission, global hint or relaxed compiler
flag is authorized. Exact elaborated types and transparent bodies must still
compare with the frozen baseline under the same prover identity. A comparison
difference ends the repair and returns to the requirement owner.

The final acceptance remains Q39's clean lock-import build, complete environment
kernel reading and axiom classification, output comparisons, target replay,
manifest identities and hosted handoff. A successful candidate check supplies no
substitute for those checks.

## Follow-up for the remaining repeated assertions

The first follow-up used one candidate, candidate 13, and stopped at its new
failure. The check exited 2 after 82.76 seconds. It closed the second standalone
exclusion lemma and reached the same assertion pattern in `step_E0_strong` at
`security/Recomposition.v:8869`.

The integrator read the remaining six `H'` assertion bodies at lines 8863, 8884,
8905, 8988, 9009 and 9115 of that stopped source, whose SHA-256 is
`02fba81e5ab76720b83384acf88dbc15125f8a267789002559d5beb5739cb889`.
Each asserts `preg_notin PC (destroyed_by_builtin ef)` or its `ef0` variant and
uses the same failing expansion. The other `destruct orb` sites at lines 5818
and 5828 belong to already compiled lemmas and are outside this repair.

A further scope permits at most two candidates or eight active repair minutes,
whichever comes first, replacing only those six assertion bodies with the
existing general-characterization/not-PC strategy now demonstrated twice.
Preserve the original net transparency-setting effects as well as the frozen
declarations, definitions, hypotheses, admissions and compiler flags. The reason
for batching these sites is their matching propositions and proof pattern; the
integrator has read the sites rather than assuming every Boolean case is the same.

Retain both earlier censuses and the complete diff. A new unrelated failure ends
this scope before another edit. Exact frozen comparison and all Q39 acceptance
checks remain required.
