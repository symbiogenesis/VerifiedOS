# Vela declaration-documentation qualification

## Accepted boundary

Q25s's [documentation contract](../languages/vela/authoring-tools.md#documentation-comments)
is satisfied for the existing pure compiler's public functions and constants.
Documentation remains plain-text diagnostic presentation with no semantic,
contract or proof authority. The
[qualification predicate](../languages/vela/authoring-tools.md#qualification)
requires no native parser, prover or migrated WSL installation. Two-editor
interoperability remains with Q25n/Q25o under the
[navigation contract](../languages/vela/lsp-prototype.md#pure-navigation-increment).

## Independent review

Review on 2026-11-03 used implementation input
`bd51161f7858b55cb1a3e854730998c1c22c3204`. The production implementation is
unchanged by this qualification; the added controls exercise attachment across
formatting, use-site comments and the distinction between orphan and attached
presentation budgets.

| Owner predicate | Reviewed mechanism and independent evidence |
| --- | --- |
| Direct declaration attachment; orphan and break behavior | The parser records each public declaration's start before elaboration. [The fact collector](../../tools/vos/vela_facts.py) attaches comments only at that compiler-selected site. [The trivia reader](../../tools/vos/vela_documentation.py) walks immediately preceding physical lines and stops at a non-documentation line. Independently expected text and original-byte spans distinguish module orphans, blank lines, ordinary comments, trailing comments, locals and use-site comments. |
| Unicode, mixed newlines and bounded text | The reader recognizes CRLF, CR and LF separately from UTF-8 content, removes the slash prefix and at most one following space, and bounds the normalized presentation by UTF-8 bytes. Exact-bound and over-bound supplementary-character fixtures distinguish bytes from characters and authored newline bytes. Oversized orphan blocks remain ordinary comments. |
| Declaration and use hover agreement | [The projection](../../tools/vos/vela_lsp_services.py) follows the producer's declaration identity. It verifies the recorded comment, source adjacency, declaration/name prefix and declaration-kind marker before emitting plain text. A nearby use-site comment cannot replace the declaration's text; XML-looking text stays literal. |
| Forged and stale facts refuse completely | Independent substitutions alter text, spans, field population, declaration offsets, declaration identity and constant/function kind. Projection refuses the inspection rather than returning a partial hover. Changed comment bytes reject the old fact. |
| Versioned edit invalidation and real stdio | [The server](../../tools/vos/vela_lsp.py) requests inspection from the current immutable overlay for each navigation query. Changed and removed documentation is checked through incremental edits, and a real isolated stdio process exercises UTF-8 frame lengths, unsaved replacement, correlated hover replies and current diagnostic versions. |
| Formatting preserves attachment and content | The formatter checks its ordered token/comment fingerprint, attachment breaks, reparsed syntax and idempotence. The qualification also compares the independently expected documented-symbol map before and after formatting, including ordinary local/use-site comments and broken attachment. |
| Comments grant no semantic authority | Complete translation precedes publication of facts; invalid or unsupported source yields no accepted documentation facts. The fixtures compare generated definitions with and without documentation. The public-documentation lint consumes compiler facts and retains its advisory status. |

No production defect remained after this review. Scope remains the existing
public-function/constant diagnostic increment: parameter/local documentation,
XML interpretation, wider-language semantic facts and production compiler
acceptance are outside its commissioned boundary.

## Local validation and handoff

The following focused host commands passed in the isolated qualification lane:

```console
python tools/run.py prepare python --path tools/tests/test_vela_documentation.py
python tools/run.py test --only test_vela_documentation --jobs 2
python tools/run.py test --only test_vela_format --jobs 2
python tools/run.py test --only test_vela_lint --jobs 2
```

[The documentation controls](../../tools/tests/test_vela_documentation.py)
provide the independent attachment, forgery, bound, formatting and wire cases;
the existing formatter and lint controls retain their separate consumer checks.
The integrator owns Python checks and corpus validation on the settled batch.

Host CI on Windows and Ubuntu and the selected Guest CI recommendation follow
the [shared handoff](../../AGENTS.md#tool-execution-and-validation). Their
verdicts remain pending and supply no passing evidence in this record. The
batch's local fanout journal binds the settled revision and recommended checks;
the user owns publication and hosted execution.
