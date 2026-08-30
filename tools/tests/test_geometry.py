# SPDX-License-Identifier: Apache-2.0
"""The block-size parse, one fixture file per site that writes the figure.

`geometry.read` is the checker's reach past its own corpus and nothing besides: two
Sail type synonyms resolved by name out of the generated bundle, the frozen
configuration, the CMake template, the harness assert, and the authored SystemVerilog
package's localparam. What the constraining document
says about them is inside the corpus and is held as claims in
`vos/checks/counts_geometry.py`, so no fixture here carries it. The live tree
exercises the happy path on every `check.py` run; what only a fixture can pin is each
site's refusal shape, the granules-to-exponent conversion, and the template's
uniqueness rule.
"""

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tests.harness import Case, ensure
from vos import geometry, sailbundle

# The five sites and the granule they are read against, spelled the way the live
# tree spells them and agreeing on a 64-byte block over a 16-byte granule. Two of
# the five are Sail type synonyms and arrive through the bundle rather than
# through a file, which is what makes a renamed declaration a lookup that misses.
_TYPES = {"log2_cap_size": "type log2_cap_size : Int = 4",
          "log2_cap_block_size": "type log2_cap_block_size : Int = 6"}
_CONFIG = '{"platform": {"cache_block_size_exp": 6}}\n'
_TEMPLATE = ('{\n  "platform": {\n    "cache_block_size_exp": 6,\n'
             '    "clock_frequency": @CLOCK@\n  }\n}\n')
_HARNESS = "assert(caps_per_block == 4)\n"
_PACKAGE = ("package vos_cheri_pkg;\n"
            "  localparam int unsigned Log2CapBlockSize = 6;\n"
            "endpackage\n")

_FILES = {
    "model/config/verifiedos.json": _CONFIG,
    "model/config/config.json.in": _TEMPLATE,
    "model/model/unit_tests/test_cheri_insts.sail": _HARNESS,
    geometry.PACKAGE: _PACKAGE,
}


@contextmanager
def _tree(files: dict[str, str]) -> Iterator[Path]:
    """A throwaway root holding exactly `files`. No git: `read` opens paths and
    never the index, so the harness's tracked sandbox would buy nothing here."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
        yield root


def _bundle(types: dict[str, str],
            lets: dict[str, str] | None = None) -> sailbundle.Bundle:
    """A bundle carrying exactly these declarations and nothing else.

    Built here rather than emitted, because what is under test is the parse and not
    Sail: `sailbundle.Bundle` takes the mapping the tracked artifact decodes to, so a
    fixture states the declarations it wants and no toolchain runs.
    """
    where = {"file": "core/fixture.sail", "loc": [1, 0, 0, 1, 0, 0]}
    return sailbundle.Bundle({
        "version": 1,
        "embedding": "plain",
        "hashes": {},
        "functions": {},
        "mappings": {},
        "vals": {},
        "types": {name: {"type": {"contents": text, **where}}
                  for name, text in types.items()},
        "registers": {},
        "lets": {name: {"let": {"source": {"contents": text, **where}}}
                 for name, text in (lets or {}).items()},
        "anchors": {},
        "spans": {},
    }, "a fixture bundle")


def _all_sites() -> None:
    with _tree(_FILES) as root:
        geo = geometry.read(root, _bundle(_TYPES))
    ensure(geo.granule_exp == 4, f"the granule exponent read {geo.granule_exp}, not 4")
    ensure(geo.sites == {"the model's declaration": 6,
                         "the frozen profile's configuration": 6,
                         "the generated configurations": 6,
                         "the model's own harness": 6,
                         "the authored capability package": 6},
           f"the five sites must all answer 6, got {geo.sites}")


def _harness_granules_to_exponent() -> None:
    # The harness writes the group in granules; the conversion demands a power of
    # two, because a non-power has no exponent to compare against the other sites.
    for granules, want in (("4", 6), ("1", 4), ("8", 7), ("3", None), ("0", None),
                           ("6", None)):
        files = dict(_FILES)
        files["model/model/unit_tests/test_cheri_insts.sail"] = (
            f"assert(caps_per_block == {granules})\n")
        with _tree(files) as root:
            got = geometry.read(root, _bundle(_TYPES)).sites["the model's own harness"]
        ensure(got == want,
               f"{granules} granules read as exponent {got}, expected {want}")


def _harness_takes_the_first_assert() -> None:
    # Pins current behavior: HARNESS_RE searches and takes the first assert where
    # TEMPLATE_RE demands uniqueness, the two sites applying opposite policies to
    # duplication. The audit flags the asymmetry; tightening the harness site to
    # the template's rule is the deliberate change that rerecords this case.
    files = dict(_FILES)
    files["model/model/unit_tests/test_cheri_insts.sail"] = (
        "assert(caps_per_block == 4)\nassert(caps_per_block == 8)\n")
    with _tree(files) as root:
        got = geometry.read(root, _bundle(_TYPES)).sites["the model's own harness"]
    ensure(got == 6, f"a second assert must currently be ignored, got {got}")


def _template_uniqueness() -> None:
    # The template is not JSON in any dialect, so the key being unique in it is
    # what makes reading it as text safe: two occurrences answer None rather than
    # whichever one a search happened to hit.
    for template, want in ((_TEMPLATE, 6),
                           (_TEMPLATE + _TEMPLATE, None),
                           ('{"platform": {"clock_frequency": @CLOCK@}}\n', None)):
        files = dict(_FILES)
        files["model/config/config.json.in"] = template
        with _tree(files) as root:
            got = geometry.read(root, _bundle(_TYPES)).sites["the generated configurations"]
        ensure(got == want, f"the template site read {got}, expected {want}")


def _absent_files() -> None:
    # A missing artifact is a finding the caller words, never an exception: every
    # site is present in the answer and holds None. A run with no readable bundle
    # is the same shape one level up, and K-88 is what words it.
    with _tree({}) as root:
        geo = geometry.read(root, None)
    ensure(geo.sites == {"the model's declaration": None,
                         "the frozen profile's configuration": None,
                         "the generated configurations": None,
                         "the model's own harness": None,
                         "the authored capability package": None},
           f"an empty root must answer None at every site, got {geo.sites}")
    ensure(geo.granule_exp is None, "the granule must also read as absent")


def _granule_fallback() -> None:
    # Pins current behavior: with the harness present but the granule unreadable,
    # `(geo.granule_exp or 0)` fabricates an exponent against a one-byte granule
    # instead of answering None. Sound today only because the sole caller returns
    # early on a None granule before reading sites; the audit flags it, and the
    # hardening that answers None here is the change that rerecords this case.
    types = {k: v for k, v in _TYPES.items() if k != "log2_cap_size"}
    with _tree(_FILES) as root:
        geo = geometry.read(root, _bundle(types))
    harness_site = geo.sites["the model's own harness"]
    ensure(geo.granule_exp is None, "the granule site must be gone with its file")
    ensure(harness_site == 2,
           f"4 granules over a fabricated granule exponent of 0 currently reads "
           f"as 2, got {harness_site}")


def cases() -> list[Case]:
    return [
        Case("all-sites", _all_sites),
        Case("harness-granules-to-exponent", _harness_granules_to_exponent),
        Case("harness-takes-the-first-assert", _harness_takes_the_first_assert),
        Case("template-uniqueness", _template_uniqueness),
        Case("absent-files", _absent_files),
        Case("granule-fallback", _granule_fallback),
    ]
