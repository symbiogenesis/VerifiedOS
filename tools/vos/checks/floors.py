# SPDX-License-Identifier: Apache-2.0
"""Check non-emptiness floors for checker enumerations, view citations, and two-class memory figures (`K-46`..`K-48`, `K-55`).

To prevent rules from passing vacuously when a document heading or pattern stops matching:
- `K-46` checks every computed quantity in `ctx.q` against its owner policy in
  [counts.py](counts.py).
- `K-47` checks that every uncounted enumeration recorded in `floors` is non-empty.
- `K-48` checks that every governing requirement ID, section number, and body pattern in
  `VIEWS` ([views.py](views.py)) resolves against the register.
- `K-55` checks that every per-class capacity figure in `CAPACITY` is still stated by
  its owning requirement and that the per-class bank count remains booked as open in
  `BOOKED_OPEN` until the freeze measurement lands.
"""

import re
from typing import TYPE_CHECKING

from vos.checks.counts import count_owner_findings

if TYPE_CHECKING:
    from . import Context

HEADING = "=== floors: every enumeration this tool reads has members ==="

# `(req_id, description, expected_literal)` for per-class capacity figures (`K-55`).
CAPACITY: list[tuple[str, str, str]] = [
    ("R-15-247", "the two classes the plan places against", "two static latency classes"),
    ("R-15-002c", "the first-class ceiling", "the first class is capped at 16 GB"),
    ("R-15-002c", "the second-class ceiling", "the second at 40 GB"),
    ("R-15-173a", "the first class's single planar tier", "order 0.5–1 GB"),
    ("R-15-170", "the phone-class first-class budget", "4–8 GB"),
    ("R-15-170", "the laptop and desktop first-class budget", "8–16 GB"),
    ("R-15-247a", "the bulk tier the sidecar is priced against", "40 GB bulk tier"),
]

# Artifacts that book the per-class bank count (`R-15-247p`) as open until the freeze.
BOOKED_OPEN: list[tuple[str, str, str]] = [
    ("register", "R-15-014a",
     "(viii) the per-class bank count (R-15-247p)"),
    ("register", "R-15-247p",
     "the per-class bank count is in R-15-014a's frozen parameter set"),
    ("docs/implementation/contracts/freeze-measurement.md", "",
     "the per-class bank count (R-15-247p) are re-derived at the final freeze"),
]


def _two_class(ctx: Context) -> tuple[int, list[str]]:
    """Return `(owned_count, findings)` for `CAPACITY` and `BOOKED_OPEN` (`K-55`)."""
    reg = ctx.reg
    moved: list[str] = []
    owned = 0
    for ident, what, literal in CAPACITY:
        entry = reg.body.get(ident, "") + reg.accept_text.get(ident, "")
        if not entry:
            moved.append(f"{ident} owns {what} and the register no longer declares it")
        elif literal not in entry:
            moved.append(f"{ident} no longer states {what}, which this floor reads as "
                         f"'{literal}'")
        else:
            owned += 1

    for where, ident, literal in BOOKED_OPEN:
        text = reg.body.get(ident, "") if where == "register" else ctx.text(where)
        if literal not in text:
            names = ident or where
            moved.append(f"{names} no longer books the per-class bank count as open, so "
                         "the figure it withholds may now be stated and this floor is "
                         "the wrong instrument for it")
    return owned, moved


def run(ctx: Context) -> None:
    rep, reg, art, sh = ctx.rep, ctx.reg, ctx.art, ctx.shared
    rep.line(HEADING)

    rep.report("K-46", "computed quantity owner guard(s) not satisfied:",
               count_owner_findings(ctx.q),
               f"all {len(ctx.q)} computed quantities satisfy their owner guards")

    owned, moved = _two_class(ctx)

    # These counts need at least one member. Each name identifies the input
    # that K-47 reports when a reader finds an empty enumeration.
    floors = {
        "prose bookmarks": len(ctx.corpus.anchor_count),
        "licence texts the third-party page locates": sh.get("licence_texts", 0),
        "tag-plane figures the granule fixes": sh.get("tag_plane", 0),
        "welded block sizes the constraints admit": sh.get("block_candidates", 0),
        "items of the freeze's closed delta": sh.get("delta_items", 0),
        "states the freshness enumeration names": sh.get("rot_states", 0),
        "core-class table sites the rule can read": sh.get("core_class_sites", 0),
        "VLEN tokens the composition answers": sh.get("vlen_tokens", 0),
        "requirement citations in the model files read": sh.get("model_citations", 0),
        # K-88 reads source owners from the generated bundle. Require a nonempty
        # owner list so an omitted inventory cannot pass the source comparison.
        "sources the model's generated bundle records": sh.get("bundle_owners", 0),
        # The profile excludes mnemonics and Sail constructors. Compare mnemonics
        # with assembly spellings and encoder rows, and constructors with decode
        # results. Each input needs its own floor.
        "names the profile's exclusion rows spell": sh.get("exclusion_names", 0),
        "Sail constructors the profile's exclusion rows mark":
            sh.get("exclusion_markers", 0),
        "mnemonic spellings the model's assembly clauses make":
            sh.get("decode_spellings", 0),
        "names the model's decode surface decodes to": sh.get("decoded_names", 0),
        "rows of the corpus assembler's encoder table": sh.get("encoder_rows", 0),
        "values the shipped configurations state": sh.get("shipped_config_values", 0),
        # K-94 derives apertures from each composition's `platform` object.
        # The floor catches an empty aperture list even if those comparisons pass.
        "apertures the shipped configurations declare": sh.get("declared_apertures", 0),
        # K-78 checks vectorless geometry against the model's minimum vector
        # lengths even when there is no configuration key.
        "minimum-vector-length rungs the model declares": sh.get("zvl_rungs", 0),
        "per-class capacity figures the register owns": owned,
        "region classes the placement compound reads": sh.get("placement_terms", 0),
        "physical byte classes the composition is charged":
            sh.get("charged_terms", 0),
        # K-74 checks mode usage and residual coverage independently. Each
        # check needs a nonempty input.
        "discharge modes the coverage matrix declares": sh.get("cm_modes", 0),
        "coverage cells booking a residual": sh.get("cm_residual", 0),
        # K-95 reads specification targets and theorem premises independently.
        # A theorem target may have no premises, so the floor checks the whole
        # premise enumeration.
        "inventory rows the coverage cells reach": sh.get("cm_standing_rows", 0),
        "theorem targets the inventory resolves to premise rows":
            sh.get("cm_theorem_premises", 0),
        # K-76 compares the declared absences and their synthesis bindings.
        # Require members on both sides of the comparison.
        "absences the contract enumerates": sh.get("absence_ids", 0),
        "rows of the synthesis provenance record": sh.get("provenance_rows", 0),
        # K-79 needs both model declarations and their restatements to check
        # agreement.
        "capability-format parameters the model declares":
            sh.get("cap_format_params", 0),
        "sites restating a capability-format parameter":
            sh.get("cap_format_sites", 0),
        "CSR rows the profile presents": len(art.csr_rows.get("5.1", [])),
        "CSR rows the profile excludes": len(art.csr_rows.get("5.2", [])),
        "Prop fields of the apex record": len(sh["apex"].fields) if sh.get("apex") else 0,
        "rows of the field-bindings view": len(sh.get("row_order", [])),
        "checklist items": len(sh.get("items", [])),
        "checklist subtotals": len(sh.get("sections", [])),
        # K-96 checks rows against completed attended items. The floor also
        # identifies a missing or unreadable table.
        "rows of the plan's calibration record": sh.get("calibration_rows", 0),
        # K-96 reads the nested agent-parallel table separately. If its heading
        # stops matching, the calibration reader can consume its rows.
        "rows of the plan's agent-parallel record": sh.get("parallel_rows", 0),
        "dominant terms read from the big table": len(sh.get("ends", [])),
        "differential corpus members": len(sh.get("corpus_members", [])),
        # K-85 already detects a missing coverage row for each declared kind.
        # The floor catches an empty schema, which would skip those comparisons.
        "record kinds the commit-trace schema declares":
            sh.get("record kinds the commit-trace schema declares", 0),
        "files that must carry a license mark": len(sh.get("markable", [])),
        # K-81 compares the licence record with the index and checks downstream
        # restatements against the record. Require both inspected populations.
        "upstream pins the licence record states": sh.get("record_pins", 0),
        "sites restating an upstream pin": sh.get("pin_restatements", 0),
        # K-82 compares the findings index with the maintained findings blocks.
        # Check both inputs for a change that makes either reader return no rows.
        "findings the register indexes": sh.get("findings the register indexes", 0),
        "findings the plan's notes count":
            sh.get("findings the plan's notes count", 0),
        # K-82 also checks completion-log entries against landed plan items.
        # The floor identifies an empty completion-log reading.
        "landed items the completion log carries an entry for":
            sh.get("landed items the completion log carries an entry for", 0),
    }
    ctx.floors = floors
    rep.report("K-47", "enumeration(s) the tool reads and finds empty:",
               [f"the tool finds no {name}; whatever it reads them from has moved"
                for name, size in floors.items() if not size],
               f"all {len(floors)} uncounted enumerations have members")

    # the register citations the view table carries, which live in a .py and so reach
    # neither the names group nor the links group
    populated = {sub for sub in reg.subsection.values() if bool(sub)}
    cited = 0
    unanswered: list[str] = []
    for view in ctx.views:
        cited += 1
        if view["governing"] not in reg.id_set:
            unanswered.append(f"{view['file']} is governed by {view['governing']}, "
                              "which the register does not declare")
        for sub in view.get("secs", []):
            cited += 1
            if sub not in populated:
                unanswered.append(f"{view['file']} draws its members from §{sub}, "
                                  "where the register carries no entries")
        if bool(view.get("body")):
            cited += 1
            pattern = re.compile(view["body"], re.IGNORECASE)
            if not any(pattern.search(body) for body in reg.body.values()):
                unanswered.append(f"{view['file']} selects its members with a pattern "
                                  "no register entry matches")
    rep.report("K-48", "view citation(s) the register no longer answers:", unanswered,
               f"all {cited} register citations in the view table resolve")

    rep.report("K-55", "two-class figure(s) whose owner or booking has moved:", moved,
               f"all {len(CAPACITY)} per-class capacity figures are owned by the entry "
               f"that fixes them, and {len(BOOKED_OPEN)} artifacts still book the "
               "per-class bank count as open")
    rep.line()
