# SPDX-License-Identifier: Apache-2.0
"""Document counts follow declared subjects and owners, not numeric coincidences."""

from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos.checks import Context, counts
from vos.register import read_artifacts, read_register
from vos.report import Reporter

_REGISTER = "# Register\n\n## §1. Goals\n\n**R-01-001** MUST: fixture.\n· Trace: t\n"
_CRITIQUE = "docs/background/critique.md"


def _context(root: Path, fix: bool = False) -> Context:
    corpus = corpus_mod.load(root)
    return Context(root, corpus, read_register(corpus), read_artifacts(corpus),
                   Reporter(), fix=fix)


def _source_counts() -> dict[str, int]:
    """A nonempty owner for every family, with empty but valid status buckets."""
    quantities = dict.fromkeys(counts.REQUIRED_COUNTS, 1)
    quantities.update(dict.fromkeys(counts.OPTIONAL_COUNTS, 0))
    quantities.update({"cj-authored": 1, "cells-partial": 1})
    return quantities


def _growth_does_not_reclassify_counts() -> None:
    files = {
        counts.REGISTER: _REGISTER,
        _CRITIQUE: "Seventeen crown-jewel specifications are named.\n"
                   "Fourteen obligations carried a hypothesis in the reviewed proof.\n",
        counts.LOG: "Fourteen crown-jewel specifications were recorded in this run.\n",
    }
    with sandbox_tree(files) as root:
        ctx = _context(root)
        before: list[str] | None = None
        for size in (3, 14, 17, 157, 17000):
            ctx.q = {"cj-specs": size, "type-obligations": size}
            findings = counts.unheld_counts(ctx)
            ensure(len(findings) == 1 and "Seventeen" in findings[0],
                   f"only the explicit live inventory statement is a candidate: {findings}")
            ensure(before is None or findings == before,
                   "inventory growth cannot reclassify an unrelated historical number")
            before = findings


def _scopes_and_count_tokens() -> None:
    files = {
        counts.REGISTER: "# Register\n\n37 requirements are extracted.\n\n"
                         "## §1. Goals\n\n**R-01-001** MUST: satisfy two requirements.\n",
        _CRITIQUE: "521,712 crown-jewel specifications are named.\n"
                   "3.14 crown-jewel specifications is a displayed version, not a count.\n"
                   "```text\n99 crown-jewel specifications in an example.\n```\n",
        "docs/unrelated.md": "12 properties describe this independent contract.\n",
    }
    with sandbox_tree(files) as root:
        findings = counts.unheld_counts(_context(root))
        ensure(len(findings) == 2, f"only the declared live count scopes apply: {findings}")
        ensure(any("'521,712'" in item for item in findings),
               "a comma-separated integer is one complete count")
        ensure(any("'37'" in item for item in findings),
               "the register introduction holds its declared scope")


def _registered_claim_offsets_follow_repairs() -> None:
    raw = "# Register\n\nAll eighteen normative sections are extracted.\n\n" + _REGISTER
    with sandbox_tree({counts.REGISTER: raw}) as root:
        ctx = _context(root, fix=True)
        ctx.fixed[counts.REGISTER] = raw.replace("eighteen", "twenty-two")
        ensure(not counts.unheld_counts(ctx),
               "a registered count remains held when a repair changes its width")


def _missing_owner_and_valid_zero_buckets() -> None:
    quantities = _source_counts()
    ensure(not counts.count_owner_findings(quantities),
           "empty status buckets and commandless-row sets are valid within present owners")
    quantities["type-obligations"] = 0
    found = counts.count_owner_findings(quantities)
    ensure(len(found) == 1 and "R-05-029" in found[0],
           f"a missing unclaimed enumeration still fails its owner guard: {found}")
    del quantities["type-obligations"]
    ensure(counts.count_owner_findings(quantities) == found,
           "a reader removed entirely is as invalid as one that reads an empty owner")


def _owner_policy_is_total() -> None:
    quantities = _source_counts()
    quantities["unregistered-family"] = 10
    ensure(any("unregistered-family" in item
               for item in counts.count_owner_findings(quantities)),
           "an unknown computed quantity needs a declared source guard")
    del quantities["unregistered-family"]
    for bad in (-1, 2):
        quantities["cj-partial"] = bad
        ensure(any("cj-partial" in item
                   for item in counts.count_owner_findings(quantities)),
               "optional buckets must stay inside their parent enumeration")
    quantities = _source_counts()
    with patch.dict(counts.OPTIONAL_COUNTS, {"cj-specs": "cj-specs"}):
        ensure(any("both required and optional" in item
                   for item in counts.count_owner_findings(quantities)),
               "overlapping policies cannot silently select the weaker guard")
    with patch.dict(counts.OPTIONAL_COUNTS, {"cj-partial": "unknown-parent"}):
        ensure(any("not a recorded required owner" in item
                   for item in counts.count_owner_findings(quantities)),
               "an empty bucket cannot hide a misspelled parent owner")


def _missing_enumeration_is_not_repaired() -> None:
    register = _REGISTER + "\n**R-05-029** MUST: the owner wording moved.\n"
    with sandbox_tree({counts.REGISTER: register}) as root:
        ctx = _context(root, fix=True)
        ctx.shared.update(cj_confer=[], fc_seams=[], fc_confer=[], rf_confer=[],
                          dispositions=0, rot_cases=0)
        quantities = counts._quantities(ctx)
        ensure(quantities["type-obligations"] == 0,
               "the actual owner reader cannot invent a list from moved wording")
        ensure(any("type-obligations" in item
                   for item in counts.count_owner_findings(quantities)),
               "removing prose claims does not remove the canonical list's guard")


def _historical_evidence_is_not_live_repair_input() -> None:
    history = ("# Completion evidence\n\n"
               "The generated table carries **931** admitted mnemonics.\n"
               "Twenty rows, one per switch. This lane now carries four.\n"
               "The lane is twenty stated facts and all but eight of them carry a command.\n")
    with sandbox_tree({counts.REGISTER: _REGISTER, counts.LOG: history}) as root:
        ctx = _context(root, fix=True)
        ctx.shared.update(cj_confer=[], fc_seams=[], fc_confer=[], rf_confer=[],
                          dispositions=0, rot_cases=0)
        counts.run(ctx)
        ensure(counts.LOG not in ctx.fixed and ctx.text(counts.LOG) == history,
               "repair must preserve exact recorded evidence despite different live facts")
        ensure(not any(file == counts.LOG for file, _, _, _ in counts.CLAIMS),
               "completion evidence cannot be registered as a live count repair target")


def cases() -> list[Case]:
    return [
        Case("growth-does-not-reclassify-counts", _growth_does_not_reclassify_counts),
        Case("scopes-and-count-tokens", _scopes_and_count_tokens),
        Case("registered-claim-offsets-follow-repairs", _registered_claim_offsets_follow_repairs),
        Case("missing-owner-and-valid-zero-buckets", _missing_owner_and_valid_zero_buckets),
        Case("owner-policy-is-total", _owner_policy_is_total),
        Case("missing-enumeration-is-not-repaired", _missing_enumeration_is_not_repaired),
        Case("historical-evidence-is-not-live-repair-input",
             _historical_evidence_is_not_live_repair_input),
    ]
