# Scalar width staging contract

R1b seam 2 binds the imported scalar datapath to the frozen capability widths
through explicit semantic transforms of its pinned sources. The integrator
authorizes this staging route: imported bodies remain behind the existing
`upstream/cva6-cheri` gitlink, and only the transformations are authored here.
This contract precedes their implementation. It supplements the
[reparameterization delta](rtl-reparameterization-delta.md) and does not select
instruction semantics for later seams.

## Transform boundary

The transform registry names each source, its SHA-256 identity, an ordered set
of exact replacements with match counts, and the resulting SHA-256 identity.
The runner rejects a missing source, an identity mismatch, a changed match
count, or an unexpected resulting identity. Source decoding uses UTF-8 and
normalizes source line endings to LF before these identities and replacements;
this makes the identity independent of Git's host text checkout conversion.
The selected source pin remains recorded separately.

Only the curated elaboration arm applies these transforms. The stock arm
continues to measure the stock source. Staged files retain all original notices
and add a modification notice naming this contract. The build lane contains
the input/output identities, exact replacements and source-to-staged diffs.
No imported body is copied into tracked `rtl/`. This is source provenance,
not formal equivalence or a synthesized absence result.

## Seam 2 decisions

`CLEN` is the frozen capability memory width, equal to `XLEN`, in both
`ariane_pkg` and `build_config_pkg`. Register and PCC transport widths continue
to derive from `$bits(cva6_cheri_pkg::cap_reg_t)`, the typedef of the Sail-owned
decoded record. No padded legacy register shape is introduced. The store
alignment function rotates bytes within one frozen word and has no upper
capability half; only the low address bits within that word select rotation.
Full-width accesses still require alignment at their architectural boundary.

The imported bounds metadata temporaries disappear. Their declarations,
assignments, and metadata-only helper arguments are removed together; the
frozen helpers derive bounds directly from the capability record. No replacement
`cap_meta_data_t` or ignored compatibility argument is introduced. The
permission-report and exception-type consumers remain later functional-unit
work, as do the single-root and single-sentry consumers. This seam must not
invent aliases for those unresolved architectural choices.

## Acceptance predicate

The exact-source and exact-output guards pass at the selected pin, and tests
refuse changed bytes, missing matches, extra matches and altered expected output.
Curated file-list staging applies every registry row exactly once; the stock
list remains unchanged. Standalone frozen packages lint, a width probe measures
the memory/register/PCC widths, and a store-rotation test covers every lane and
bit. The existing Sail-to-RTL capability vector crosscheck remains green.
Curated elaboration records its actual remaining errors, with the removed
metadata sites absent. A smaller/different diagnostic set is seam progress;
the remaining core need not elaborate, and this acceptance gives no instruction
refinement, functional-unit completion or SoC integration credit.
