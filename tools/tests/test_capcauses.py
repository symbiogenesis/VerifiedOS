# SPDX-License-Identifier: Apache-2.0
"""Generation and refusal boundaries of the capability-exception region."""

from tests.harness import Case, ensure, sandbox_tree
from vos import capcauses
from vos.checks import Context
from vos.checks.counts_capcauses import cap_causes
from vos.corpus import Corpus, find_root
from vos.register import Artifacts, Register
from vos.report import Reporter


def _sources() -> list[str]:
    root = find_root()
    return [(root / name).read_text(encoding="utf-8") for name in capcauses.OWNERS]


def _changed(index: int, old: str, new: str) -> list[str]:
    sources = _sources()
    ensure(sources[index].count(old) == 1, f"test needs one owner site {old!r}")
    sources[index] = sources[index].replace(old, new)
    return sources


def _refuses(sources: list[str], label: str) -> None:
    try:
        capcauses.render(*sources)
    except capcauses.CauseError as exc:
        ensure(label in str(exc), f"wrong refusal: {exc}")
    else:
        raise AssertionError(f"expected refusal naming {label}")


def _tracked_region_is_generated() -> None:
    root = find_root()
    text = (root / capcauses.ADAPTER).read_text(encoding="utf-8")
    expected = capcauses.replace(text, capcauses.emit(root))
    ensure(text == expected, "the tracked exception section differs from regeneration")


def _owner_changes_generate_the_new_value() -> None:
    changed = _changed(1, "0b011100", "0b011101")
    ensure("CAP_EXCEPTION = 29;" in capcauses.render(*changed), "mcause owner was ignored")
    changed = _changed(0, "=> 0b11000", "=> 0b11001")
    ensure("5'b11001" in capcauses.render(*changed), "cause table owner was ignored")


def _enum_growth_arrives_without_a_generator_edit() -> None:
    sources = _sources()
    sources[0] = sources[0].replace("  CapEx_None,", "  CapEx_Test,\n  CapEx_None,")
    sources[0] = sources[0].replace("  match ex {", "  match ex {\n    CapEx_Test => 0b00100,", 1)
    ensure("CapEx_Test" in capcauses.render(*sources), "the generator lost an added cause")


def _report_width_does_not_widen_the_register_file() -> None:
    sources = _changed(0, "type capreg_idx = bits(6)", "type capreg_idx = bits(7)")
    sources[0] = sources[0].replace("= 0b100000", "= 0b0100000")
    emitted = capcauses.render(*sources)
    ensure("CapRegIdxWidth = 7;" in emitted, "report width did not follow its owner")
    ensure("CapRegFileIdxWidth = 5;" in emitted, "report width changed the core index")
    ensure("logic [CapRegFileIdxWidth-1:0] r" in emitted, "core input has the report width")


def _composition_selects_the_register_file_width() -> None:
    changed = _changed(4, '"E": false', '"E": true')
    ensure("CapRegFileIdxWidth = 4;" in capcauses.render(*changed), "base.E was ignored")


def _duplicate_or_missing_table_rows_refuse() -> None:
    _refuses(_changed(0, "  CapEx_AccessSystemRegsViolation,",
                     "  CapEx_AccessSystemRegsViolation,,"), "empty row")
    _refuses(_changed(0, "    CapEx_None                          => 0b00000,",
                     "    CapEx_None => 0b00000,\n    CapEx_None => 0b00000,"), "duplicate")
    _refuses(_changed(0, "    CapEx_None                          => 0b00000,", ""),
             "exactly the CapEx enumeration")
    _refuses(_changed(0, "    CapEx_None                          => 0b00000,",
                     "    CapEx_None => unsupported,"), "unreadable")


def _duplicate_or_unsupported_definitions_refuse() -> None:
    _refuses(_changed(0, "type capreg_idx = bits(6)",
                     "type capreg_idx = bits(6)\ntype capreg_idx = bits(6)"), "found 2")
    _refuses(_changed(0, "zero_extend(regnum @ CapExCode(capEx))",
                     "zero_extend(CapExCode(capEx) @ regnum)"), "packing")
    _refuses(_changed(0, "zero_extend(r)", "sign_extend(r)"), "register index")
    _refuses(_changed(3, "type xlen : Int = 64", "type xlen : Int = 64 + 1"), "Sail xlen")
    sources = _sources()
    sources[0] += "\nfunction CapExCode(ex : CapEx) -> unsupported = ex\n"
    _refuses(sources, "found 2")
    _refuses(_changed(0, "zero_extend(regnum @ CapExCode(capEx))",
                     "zero_extend(regnum @ CapExCode(capEx))\n  @ 0b1"), "packing")


def _oversized_or_inconsistent_values_refuse() -> None:
    _refuses(_changed(3, "type xlen : Int = 64", "type xlen : Int = 10"), "payload")
    _refuses(_changed(1, "0b011100", "0b1" + "0" * 64), "EXC_CHERI literal width")
    _refuses(_changed(0, "=> 0b11000", "=> 0b00000"), "repeats a cause encoding")
    _refuses(_changed(0, "=> 0b11000", "=> 0b1100"), "literal width")
    _refuses(_changed(0, "= 0b100000", "= 0b10000"), "PCC_IDX literal width")


def _exception_mapping_uses_its_own_width() -> None:
    _refuses(_changed(1, "0b011100", "0b0011100"), "EXC_CHERI literal width")
    _refuses(_changed(5, "type exc_code = bits(6)", "type exc_code = bits(5)"),
             "EXC_CHERI literal width")
    _refuses(_changed(5, "type exc_code = bits(6)", "type exc_code = bits(65)"),
             "exc_code width does not fit")
    changed = _changed(5, "type exc_code = bits(6)", "type exc_code = bits(7)")
    changed[1] = changed[1].replace("0b011100", "0b1011100")
    ensure("CAP_EXCEPTION = 92;" in capcauses.render(*changed),
           "mapping did not follow its independently changed owner width")


def _trap_value_alias_must_reach_xlen() -> None:
    _refuses(_changed(3, "type xlenbits = bits(xlen)", "type xlenbits = bits(5)"),
             "Sail xlenbits")
    _refuses(_changed(3, "type xlenbits = bits(xlen)",
                     "type xlenbits = bits(xlen)\ntype xlenbits = unsupported"), "found 2")


def _region_repair_is_local_and_idempotent() -> None:
    generated = capcauses.render(*_sources())
    envelope = "authored prefix\n" + generated + "authored suffix\n"
    changed = envelope.replace("CAP_EXCEPTION = 28;", "CAP_EXCEPTION = 29;")
    repaired = capcauses.replace(changed, generated)
    ensure(repaired == envelope, "repair changed authored text or retained stale code")
    ensure(capcauses.replace(repaired, generated) == repaired, "repair has no fixpoint")
    changed = envelope.replace("capreg_idx_t  regnum;", "cap_ex_code_t regnum;")
    ensure(capcauses.replace(changed, generated) == envelope, "packing drift survived repair")


def _malformed_regions_refuse_repair() -> None:
    generated = capcauses.render(*_sources())
    for invalid in (generated.replace(capcauses.BEGIN, ""), generated + generated,
                    capcauses.END + "\n" + capcauses.BEGIN + "\n"):
        try:
            capcauses.replace(invalid, generated)
        except capcauses.CauseError:
            pass
        else:
            raise AssertionError("malformed region was repaired by guessing its extent")


def _checker_repair_preserves_authored_bytes() -> None:
    sources = _sources()
    generated = capcauses.render(*sources)
    prefix, suffix = "// authored prefix\r\n\r\n", "\r\n// authored suffix\r\n"
    stale = generated.replace("CAP_EXCEPTION = 28;", "CAP_EXCEPTION = 29;")
    tree = dict(zip(capcauses.OWNERS, sources, strict=True))
    tree[capcauses.ADAPTER] = prefix + stale.replace("\n", "\r\n") + suffix
    with sandbox_tree(tree) as root:
        path = root / capcauses.ADAPTER
        # Use bytes to make this probe independent of the fixture writer's newline policy.
        path.write_bytes(tree[capcauses.ADAPTER].encode("utf-8"))
        corpus = Corpus(root, [], {}, list(tree))
        ctx = Context(root, corpus, Register(), Artifacts(), Reporter(), fix=True)
        cap_causes(ctx)
        ensure(ctx.rep.findings == 0, f"repair refused CRLF delimiters: {ctx.rep.out}")
        expected = (prefix + generated + suffix).encode("utf-8")
        ensure(ctx.fixed[capcauses.ADAPTER].encode("utf-8") == expected,
               "checker normalized authored bytes outside the generated region")
        path.write_text(ctx.fixed[capcauses.ADAPTER], encoding="utf-8", newline="")
        ensure(path.read_bytes() == expected, "repair output changed authored line endings")
        again = Context(root, corpus, Register(), Artifacts(), Reporter(), fix=True)
        cap_causes(again)
        ensure(again.rep.findings == 0 and not again.fixed, "byte-preserving repair has no fixpoint")
        corpus.tracked.remove(capcauses.COMMON_TYPES)
        missing = Context(root, corpus, Register(), Artifacts(), Reporter(), fix=True)
        cap_causes(missing)
        ensure(missing.rep.findings == 1 and not missing.fixed,
               "an untracked mapped-width owner was accepted or repaired")


def _absent_or_undecodable_owner_refuses() -> None:
    with sandbox_tree({}) as root:
        try:
            capcauses.emit(root)
        except capcauses.CauseError as exc:
            ensure(capcauses.CAUSES in str(exc), f"wrong missing owner: {exc}")
        else:
            raise AssertionError("absent owner did not refuse")
        owner = root / capcauses.CAUSES
        owner.parent.mkdir(parents=True, exist_ok=True)
        owner.write_bytes(b"\xff")
        try:
            capcauses.emit(root)
        except capcauses.CauseError as exc:
            ensure("cannot read" in str(exc), f"wrong unreadable-owner refusal: {exc}")
        else:
            raise AssertionError("undecodable owner did not refuse")


def cases() -> list[Case]:
    return [Case(fn.__name__.removeprefix("_"), fn) for fn in (
        _tracked_region_is_generated, _owner_changes_generate_the_new_value,
        _enum_growth_arrives_without_a_generator_edit,
        _report_width_does_not_widen_the_register_file,
        _composition_selects_the_register_file_width,
        _duplicate_or_missing_table_rows_refuse, _duplicate_or_unsupported_definitions_refuse,
        _oversized_or_inconsistent_values_refuse, _region_repair_is_local_and_idempotent,
        _exception_mapping_uses_its_own_width, _trap_value_alias_must_reach_xlen,
        _checker_repair_preserves_authored_bytes,
        _malformed_regions_refuse_repair, _absent_or_undecodable_owner_refuses,
    )]
