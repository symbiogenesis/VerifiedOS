# SPDX-License-Identifier: Apache-2.0
"""The reporting convention, held to the shape its callers parse.

`Reporter`'s `FAIL `/`ok ` prefixes and seven-space finding indent are parsed by
check-selftest.py, so the exact strings are API rather than styling, and these
cases pin them as such: a reformat that reads better and breaks the selftest's
stdout grep must fail here first, beside the module that made the promise.
"""

from tests.harness import Case, ensure
from vos.report import Reporter, sites


def _falsy_items_dropped() -> None:
    # a check building findings in a comprehension yields None or "" for every
    # member it cleared; only the survivors are findings
    rep = Reporter()
    rep.report("K-99", "thing(s):", ["", None, "real"])
    ensure(rep.findings == 1, f"findings is {rep.findings}, not the 1 non-falsy item")
    ensure(rep.out == ["FAIL K-99: 1 thing(s):", "       real"],
           f"the FAIL shape moved: {rep.out!r}")


def _all_falsy_reads_ok() -> None:
    rep = Reporter()
    rep.report("K-98", "label:", [None, ""])
    ensure(rep.findings == 0, "all-falsy items must decide clean")
    ensure(rep.out == ["ok K-98: label:"],
           f"with no ok text the label is the ok line's text: {rep.out!r}")


def _ok_text_preferred() -> None:
    rep = Reporter()
    rep.report("K-01", "label:", [], ok="all 5 agree")
    ensure(rep.out == ["ok K-01: all 5 agree"],
           f"the ok argument names what was decided: {rep.out!r}")


def _findings_count_items_not_rules() -> None:
    rep = Reporter()
    rep.report("K-11", "a:", ["x", "y", "z"])
    rep.report("K-12", "b:", ["p", "q"])
    ensure(rep.findings == 5,
           f"findings counts items across rules, so 3 + 2 is 5, not {rep.findings}")
    ensure(rep.out[0] == "FAIL K-11: 3 a:" and rep.out[4] == "FAIL K-12: 2 b:",
           f"each FAIL line carries its own count: {rep.out!r}")


def _pad_prefixes_every_line() -> None:
    rep = Reporter()
    rep.report("K-05", "x:", ["f"], pad="  ")
    ensure(rep.out == ["  FAIL K-05: 1 x:", "         f"],
           f"pad must prefix the verdict and keep the seven-space indent: {rep.out!r}")


def _line_appends_verbatim() -> None:
    rep = Reporter()
    rep.line("=== heading ===")
    rep.line()
    ensure(rep.out == ["=== heading ===", ""],
           f"line() is verbatim accumulation: {rep.out!r}")
    ensure(rep.findings == 0, "line() decides nothing")


def _sites_uncapped() -> None:
    got = sites("a.md", [3, 4, 9])
    ensure(got == "a.md: 3 line(s): 3, 4, 9", f"sites moved: {got!r}")


def _sites_capped() -> None:
    got = sites("a.md", list(range(1, 15)))
    ensure(got == "a.md: 14 line(s): 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, and 2 more",
           f"the cap keeps the first twelve and counts the rest: {got!r}")
    at_cap = sites("b.md", list(range(1, 13)))
    ensure(at_cap.endswith("1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12"),
           f"exactly the cap prints whole, with no 'and 0 more': {at_cap!r}")


def cases() -> list[Case]:
    return [
        Case("falsy-items-dropped", _falsy_items_dropped),
        Case("all-falsy-reads-ok", _all_falsy_reads_ok),
        Case("ok-text-preferred", _ok_text_preferred),
        Case("findings-count-items", _findings_count_items_not_rules),
        Case("pad-prefixes-every-line", _pad_prefixes_every_line),
        Case("line-appends-verbatim", _line_appends_verbatim),
        Case("sites-uncapped", _sites_uncapped),
        Case("sites-capped", _sites_capped),
    ]
