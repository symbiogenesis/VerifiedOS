# SPDX-License-Identifier: Apache-2.0
"""The oracle spec's parse and its Sail emission, which are the half that has no
toolchain behind it.

What only a fixture can pin is the refusal shape of a malformed spec and the exact
Sail a domain description produces: the live specs exercise the happy path on every
`run.py oracle vectors` run, and that run needs Sail, a C compiler and two minutes. Both
halves matter for the same reason: an emission that is wrong in a way Sail accepts is
a harness that prints the wrong question's answers, and the vectors then agree about
nothing.
"""

import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import oracle

_MINIMAL: oracle.SpecRow = {
    "name": "probe",
    "what": "a probe",
    "answers": "M0.12",
    "sources": ["model/model/prelude/prelude.sail"],
    "probes": [{
        "kind": "pn",
        "what": "an exhaustive walk",
        "params": [{"name": "want", "width": 12, "over": "all", "show": "h3"}],
        "body": ["let code = narrow(want)"],
        "shows": [{"expr": "code", "show": "h2"}],
    }],
}


def _spec(**over: object) -> oracle.SpecRow:
    """The minimal spec with one field replaced, so a case states its own difference
    and nothing else."""
    row = dict(_MINIMAL)
    row.update(over)
    return oracle.SpecRow(**row)


def _refuses(row: oracle.SpecRow, wanted: str, name: str = "probe") -> None:
    try:
        oracle.parse(name, row)
    except oracle.SpecError as err:
        ensure(wanted in str(err),
               f"the refusal said {err!r}, which does not carry {wanted!r}")
        return
    raise AssertionError(f"the spec was admitted and should have been refused: {wanted}")


def _parses() -> None:
    spec = oracle.parse("probe", _MINIMAL)
    ensure(spec.vectors == 4096, f"an exhaustive 12-bit walk is 4096, not {spec.vectors}")
    ensure(spec.probes[0].params[0].over == "all", "the domain did not survive the parse")


def _counts_a_mixed_domain() -> None:
    """The arithmetic a spec states about itself: the loops multiply and the draws do
    not, which is what lets a person read a sweep's size before compiling it."""
    row = _spec(probes=[{
        "kind": "dec",
        "params": [{"name": "e", "width": 5, "over": "all"},
                   {"name": "b", "width": 8, "over": "all"},
                   {"name": "a", "width": 36, "over": "draw"}],
        "body": [],
        "shows": [{"expr": "e", "show": "h2"}],
    }])
    spec = oracle.parse("probe", row)
    ensure(spec.vectors == 32 * 256,
           f"two exhaustive fields and a drawn one is 8192, not {spec.vectors}")


def _refuses_a_renamed_file() -> None:
    _refuses(_MINIMAL, "the file name and the declared name", name="other")


def _refuses_a_sourceless_spec() -> None:
    _refuses(_spec(sources=[]), "nothing to be an oracle about")


def _refuses_a_probeless_spec() -> None:
    _refuses(_spec(probes=[]), "would print nothing")


def _refuses_two_probes_of_one_kind() -> None:
    probe = _MINIMAL["probes"][0]
    _refuses(_spec(probes=[probe, probe]), "share a kind")


def _refuses_an_unprintable_answer() -> None:
    _refuses(_spec(probes=[{
        "kind": "pn",
        "params": [{"name": "w", "width": 4, "over": "all"}],
        "body": [],
        "shows": [{"expr": "w", "show": "hex"}],
    }]), "is not a show token")


def _refuses_a_show_narrower_than_its_parameter() -> None:
    """The one width mistake a zero-extension cannot hide: a field printed in fewer
    digits than it holds is a line that does not carry the input its answer came
    from, and the two implementations then agree over a domain neither of them saw."""
    _refuses(_spec(probes=[{
        "kind": "pn",
        "params": [{"name": "w", "width": 12, "over": "all", "show": "h1"}],
        "body": [],
        "shows": [{"expr": "w", "show": "h3"}],
    }]), "is narrower than the parameter")


def _refuses_a_statement_carrying_its_own_separator() -> None:
    _refuses(_spec(probes=[{
        "kind": "pn",
        "params": [{"name": "w", "width": 4, "over": "all"}],
        "body": ["let x = f(w);"],
        "shows": [{"expr": "x", "show": "h1"}],
    }]), "the generator supplies the separator")


def _refuses_a_probe_that_writes_one_line() -> None:
    _refuses(_spec(probes=[{
        "kind": "pn",
        "params": [{"name": "w", "width": 4, "over": "draw"}],
        "body": [],
        "shows": [{"expr": "w", "show": "h1"}],
    }]), "state a repeat")


def _refuses_a_reserved_parameter_name() -> None:
    """`inc` is Sail's bitvector-order keyword and an entirely natural name for a step,
    and a parameter called it is a syntax error several hundred lines from the spec
    that caused it, in a file the reader did not write."""
    _refuses(_spec(probes=[{
        "kind": "mv",
        "params": [{"name": "inc", "width": 4, "over": "all"}],
        "body": [],
        "shows": [{"expr": "inc", "show": "h1"}],
    }]), "is a Sail keyword")


def _refuses_a_draw_wider_than_two() -> None:
    _refuses(_spec(probes=[{
        "kind": "pn",
        "params": [{"name": "w", "width": 96, "over": "draw"}],
        "repeat": 4,
        "body": [],
        "shows": [{"expr": "w", "show": "h24"}],
    }]), "wider than the 72")


def _emits_an_exhaustive_nest() -> None:
    text = oracle.harness(oracle.parse("probe", _MINIMAL), "t")
    ensure("foreach (i_want from 0 to 4095)" in text,
           "the exhaustive loop is not over the parameter's own width")
    ensure("to_bits_truncate(12, i_want)" in text, "the loop index is not narrowed")
    ensure("var seed" not in text,
           "a probe with no drawn parameter carries a shift register it never reads")


def _emits_two_draws_for_a_wide_parameter() -> None:
    row = _spec(probes=[{
        "kind": "kf",
        "params": [{"name": "a", "width": 64, "over": "draw"}],
        "repeat": 8,
        "body": [],
        "shows": [{"expr": "a", "show": "h16"}],
    }])
    text = oracle.harness(oracle.parse("probe", row), "t")
    ensure(text.count("seed = lfsr36(seed)") == 2,
           "a 64-bit parameter is two draws of a 36-bit register")
    ensure("let a : bits(64) = a_hi @ seed" in text,
           "the two draws are not composed into the parameter")


def _emits_a_table_as_a_match() -> None:
    row = _spec(probes=[{
        "kind": "sbe",
        "params": [{"name": "base", "width": 8, "over": "table",
                    "rows": ["0x00", "0x01", "0xff"], "show": "h2"}],
        "body": [],
        "shows": [{"expr": "base", "show": "h2"}],
    }])
    spec = oracle.parse("probe", row)
    text = oracle.harness(spec, "t")
    ensure(spec.vectors == 3, f"a three-row table is three vectors, not {spec.vectors}")
    ensure("match i { 0 => 0x00, 1 => 0x01, _ => 0xff }" in text,
           "the table is not a match with its last row as the wildcard")


def _emits_the_formatters_it_spends() -> None:
    """The ladder is emitted to the width used and no further: an unused formatter is
    dead Sail in a generated file, and a missing one is a call to nothing."""
    text = oracle.harness(oracle.parse("probe", _MINIMAL), "t")
    ensure("function hex_3(" in text, "the widest field's formatter is absent")
    ensure("function hex_4(" not in text, "a formatter wider than any field was emitted")


def _emission_is_deterministic() -> None:
    """A seeded defect is killed by the vectors moving, so a harness that varied
    between two emissions would move every line for a reason that is not the defect."""
    spec = oracle.parse("probe", _MINIMAL)
    ensure(oracle.harness(spec, "t") == oracle.harness(spec, "t"),
           "two emissions of one spec differ")


def _the_repositorys_own_specs_parse() -> None:
    """Every spec in the tree, held to the same parse the toolchain runs behind. A
    spec that stopped parsing would otherwise be found by a two-minute compile."""
    root = Path(__file__).resolve().parents[2]
    found = oracle.names(root)
    ensure(bool(found), "the repository carries no oracle spec at all")
    for name in found:
        spec = oracle.load(root, name)
        ensure(spec.vectors > 0, f"{name} states a domain of no vectors")
        ensure(bool(oracle.harness(spec, "t")), f"{name} emits nothing")


def _load_refuses_an_absent_spec() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        try:
            oracle.load(Path(td), "nowhere")
        except oracle.SpecError as err:
            ensure("there is no spec at" in str(err), f"the refusal said {err!r}")
            return
    raise AssertionError("an absent spec was loaded")


def cases() -> list[Case]:
    return [
        Case("a spec parses and states its own size", _parses),
        Case("a mixed domain multiplies its loops alone", _counts_a_mixed_domain),
        Case("a renamed spec file is refused", _refuses_a_renamed_file),
        Case("a spec with no sources is refused", _refuses_a_sourceless_spec),
        Case("a spec with no probes is refused", _refuses_a_probeless_spec),
        Case("two probes of one kind are refused", _refuses_two_probes_of_one_kind),
        Case("an unknown show token is refused", _refuses_an_unprintable_answer),
        Case("a show narrower than its parameter is refused",
             _refuses_a_show_narrower_than_its_parameter),
        Case("a body statement carrying `;` is refused",
             _refuses_a_statement_carrying_its_own_separator),
        Case("a one-line sampled probe is refused",
             _refuses_a_probe_that_writes_one_line),
        Case("a reserved parameter name is refused", _refuses_a_reserved_parameter_name),
        Case("a draw wider than two registers is refused", _refuses_a_draw_wider_than_two),
        Case("an exhaustive parameter emits its own nest", _emits_an_exhaustive_nest),
        Case("a wide drawn parameter emits two draws",
             _emits_two_draws_for_a_wide_parameter),
        Case("a table parameter emits a match", _emits_a_table_as_a_match),
        Case("the formatter ladder is emitted to the width spent",
             _emits_the_formatters_it_spends),
        Case("two emissions of one spec are identical", _emission_is_deterministic),
        Case("every spec in the tree parses and emits", _the_repositorys_own_specs_parse),
        Case("an absent spec is refused by name", _load_refuses_an_absent_spec),
    ]
