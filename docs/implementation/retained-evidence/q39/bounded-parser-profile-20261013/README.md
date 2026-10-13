# Bounded Parser-only checker diagnosis

This bundle records focused Q39 debugging against the unchanged VM compilation,
following the [shelving decision](../../../contained-compiler-port-decisions.md#shelve-the-incomplete-audits-after-checkpoint-and-release-triage).
The integrator bounded the new owned checker to ninety seconds, with no compiler,
proof, prover, installed-package or assumption change and no complete-audit restart.

[The operation record](operation.json) owns the actual command, environment,
absolute temporary working directory, deadline, signal, exit and duration. The
checker examined only `compcert.cparser.Parser`: `-norec` excludes recursive
dependency checks. The original whole-environment acceptance predicate is
unchanged. This diagnostic is neither a benchmark nor a qualification attempt.

The checker ended on the newly owned child's scheduled `SIGINT`. Its log again
ends at
`compcert.cparser.Parser.MenhirLibParser.Complete.Valid.is_validator_forall_items`.
The operation rehashed the complete historical seal population, actual copied
proof sources and objects, helper/tool/library identities and lock before and
after execution, with no mismatch. The original compiler producers and their
retained inputs and outcomes were preserved.

[The profile observation](observation.json) explicitly describes the truncated
stream. Default signal termination did not flush the profile channel or write its
footer. The retained fragment ends inside an earlier constant's end event; the
later target constant's begin event is unavailable. An unclosed prefix event
therefore identifies no active operation. Neither the last log name nor this
fragment establishes a root cause, a nonterminating conversion, completion of the
Parser check or progress toward complete qualification.

[The manifest](manifest.json) binds the stored and decompressed hashes of the
raw profile fragment, checker output and input-digest population, alongside the
operation and observation records. Compressed files contain metadata and textual
diagnostics; no compiler source, proof object or executable is exported. Native
captures remain at the operation's explicit temporary paths. The raw profile
fragment is deliberately retained as incomplete bytes and must not be presented
as a complete JSON profile.

Run `python verify.py` from this directory to check the immutable stored and
decompressed bytes, input-population binding and derived observation.
`python verify.py --show-observation` regenerates that view on stdout without
changing any retained record. These checks validate the evidence export, not the
native compiler or its proofs.

Q39 remains open. A next bounded diagnostic needs a supported way to retain the
unfinished profile event, or other checked reduction-specific evidence, before
selecting a repair or restarting a complete audit. No checker patch, proof
optimization, package change or additional complete qualification follows from
this result. Q43 still needs genuine complete qualification for whole-set reuse.
