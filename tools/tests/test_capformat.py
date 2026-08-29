# SPDX-License-Identifier: Apache-2.0
"""The capability-format parse, one fixture per artifact that writes a parameter.

`capformat.read` is K-79's reach past the checker's own corpus: two Sail files fix the
format, a third fixes the register width it sits inside, and six other artifacts
restate one figure or another. The live tree exercises the agreeing case on every
`check.py` run, so what only a fixture can pin is the shape of a refusal. Three edges
carry the rule's fail-closed reading and each has a case here: a declaration that has
moved out of the read form answers `None` rather than raising, a site that has moved
answers `None` rather than silently dropping out of the comparison, and a packing that
is not six fields at fixed slices is withheld whole rather than compared field by
field against a set the parse guessed at.

Nothing here restates what the values must be. The definition decides that and
`vos/checks/counts_capformat.py` computes it; a fixture asserting 36 would be a third
copy of the address width in a repository whose whole point is that there are not
three.
"""

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tests.harness import Case, ensure
from vos import capformat

# The two Sail files, at deliberately not-the-live-tree values, so that a case
# asserting agreement is asserting that the parse followed the fixture rather than
# that it happened to know the real numbers.
_CAP_FORMAT = """\
// The address space is 20 bits, so the address field is 20 bits.
type cap_size : Int = 4
type log2_cap_size : Int = 2
type cap_perms_code_width : Int = 3
type cap_otype_width : Int = 2
type cap_mantissa_width : Int = 5
type cap_E_width : Int = 4
type cap_addr_width : Int = 20

function capBitsToEncCapability(c : CapBits) -> EncCapability = struct {
  perms   = c[31 .. 29],
  otype   = c[28 .. 27],
  E       = c[26 .. 23],
  B       = c[22 .. 18],
  T       = c[17 .. 15],
  address = c[14 .. 0],
}
"""

_CAP_COMMON = """\
// The effective exponent runs to `cap_max_E` = 17, so the field is spent.
let reserved_otypes = 1
type cap_perms_width : Int = 7
"""

_XLEN = "type xlen : Int = 32\n"

_PACKAGE = """\
package vos_cheri_pkg;
  localparam int unsigned CapSize = 4;
  localparam int unsigned Log2CapSize = 2;
  localparam int unsigned CapPermsCodeWidth = 3;
  localparam int unsigned CapPermsWidth = 7;
  localparam int unsigned CapOTypeWidth = 2;
  localparam int unsigned ReservedOTypes = 1;
  localparam int unsigned CapMantissaWidth = 5;
  localparam int unsigned CapEWidth = 4;
  localparam int unsigned CapAddrWidth = 20;
  localparam int unsigned Xlen = 32;

  function automatic enc_capability_t cap_bits_to_enc(cap_bits_t c);
    ret.perms   = c[31:29];
    ret.otype   = c[28:27];
    ret.e_field = c[26:23];
    ret.b       = c[22:18];
    ret.t       = c[17:15];
    ret.address = c[14:0];
  endfunction
endpackage
"""

_CONFIG = "      XLEN: unsigned'(32),\n"

_PROFILE = """\
| Field | Width | Note | Governing |
| --- | --- | --- | --- |
| address | 20 | the whole physical address space | R-15-002a |
| object type | 2 | the sealed-capability classes | R-15-007 |
| permissions | 3 | an enumerated lattice | R-15-007b |
| exponent | 4 | as CHERI Concentrate | R-15-007 |
| base mantissa | 5 | the exactness threshold | R-15-007c |
| top mantissa | 3 | high bits derived | R-15-007c |

The profile is a 20-bit address decoded at 5- and 3-bit mantissas.
"""

_DELTA = """\
| Width, excluding the tag | 32 | 128 |
| Address field | 20, stored uncompressed | 64 |
| Permissions | one 3-bit code naming one of 8 enumerated sets, expanded to a 7-bit architectural bitmap | nine bits |
| Object type | 2 bits, sixteen classes, unsealed `0b11` | one bit |
| Exponent | 4-bit field, normalized case carried in the field | six bits |
| Base mantissa | 5 | 14 |
| Top mantissa | 3 stored, high two derived | 12 stored, high two derived |
| Maximum effective exponent | 17 | 52 |
| 36 | `CAP_RESET_EXP = 0` | literal | the reset exponent is `cap_max_E`, 17, not zero |
| 37 | `CAP_MAX_EXP = 52` | literal | 17, which is `cap_len_width - cap_mantissa_width + 1` |
| 391 | `exp > CAP_MAX_EXP ? CAP_MAX_EXP` | literal | 17 |
"""

_SPEC = """\
The frozen parameterization is a 20-bit address, a 2-bit object type, 3-bit encoded permissions, a 4-bit exponent, and 5-bit base and 3-bit top mantissas.

The field table spends all 32 bits (20+2+3+4+5+3), so a colour field would have to
come out of a mantissa.
"""

_MATRIX = """\
| **SDP bits** | 1.0 | no | It would have to come out of the permission field
itself (20+2+3+4+5+3 = 32 exactly, with nothing spare) and would be outside the
lattice. |
| **Revocation colour** | 8.0 | no | The field table has no colour field and
no spare bits (20+2+3+4+5+3 = 32), so a colour could come only from a mantissa. |
"""

_BLOCK = "and an integer register is 32 bits (R-15-002a, R-15-007i).\n"

_FILES = {
    capformat.CAP_FORMAT: _CAP_FORMAT,
    capformat.CAP_COMMON: _CAP_COMMON,
    capformat.XLEN_FILE: _XLEN,
    capformat.PACKAGE: _PACKAGE,
    capformat.CONFIG: _CONFIG,
    capformat.PROFILE: _PROFILE,
    capformat.DELTA: _DELTA,
    capformat.SPEC: _SPEC,
    capformat.MATRIX: _MATRIX,
    capformat.BLOCK: _BLOCK,
}


@contextmanager
def _tree(files: dict[str, str]) -> Iterator[Path]:
    """A throwaway root holding exactly `files`. No git: `read` opens paths and never
    the index, so the harness's tracked sandbox would buy nothing here."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
        yield root


def _definitions_read() -> None:
    with _tree(_FILES) as root:
        fmt = capformat.read(root)
    ensure(fmt.defined == {"cap_size": 4, "log2_cap_size": 2,
                           "cap_perms_code_width": 3, "cap_otype_width": 2,
                           "cap_mantissa_width": 5, "cap_E_width": 4,
                           "cap_addr_width": 20, "cap_perms_width": 7,
                           "reserved_otypes": 1, "xlen": 32},
           f"the definitions read back as {fmt.defined}")


def _every_site_read() -> None:
    with _tree(_FILES) as root:
        fmt = capformat.read(root)
    missed = sorted(label for (label, _), value in fmt.sites.items() if value is None)
    ensure(not missed, f"these sites did not match their own fixture: {missed}")
    ensure(len(fmt.sites) == len(capformat.SITES),
           f"{len(fmt.sites)} sites answered for {len(capformat.SITES)} declared")


def _moved_declaration_is_none() -> None:
    # The fail-closed edge: a declaration reworded out of the read form must answer
    # None so the caller reports it, never a value carried over from somewhere else.
    files = dict(_FILES)
    files[capformat.CAP_FORMAT] = _CAP_FORMAT.replace(
        "type cap_addr_width : Int = 20", "type cap_addr_width : Int = twenty")
    with _tree(files) as root:
        fmt = capformat.read(root)
    ensure(fmt.defined["cap_addr_width"] is None,
           "a declaration out of the read form must answer None")
    ensure(fmt.defined["cap_E_width"] == 4,
           "one moved declaration must not take its neighbours with it")


def _budgets_read() -> None:
    with _tree(_FILES) as root:
        fmt = capformat.read(root)
    ensure(len(fmt.budgets) == len(capformat.BUDGETS),
           f"{len(fmt.budgets)} budget(s) read for {len(capformat.BUDGETS)} declared")
    for label, (terms, total) in fmt.budgets.items():
        ensure(terms == (20, 2, 3, 4, 5, 3), f"{label} read terms {terms}")
        ensure(total == 32, f"{label} read a total of {total}")


def _site_matching_twice_is_none() -> None:
    # A pattern that has come to match two sites is holding whichever one a search
    # reached first, and a finding names the site, so several is the same answer as
    # none. This is the discipline `geometry.py` keeps at its own template site.
    files = dict(_FILES)
    files[capformat.PROFILE] = _PROFILE + "| address | 20 | a second table |\n"
    with _tree(files) as root:
        fmt = capformat.read(root)
    ensure(fmt.sites[("the profile's address row", "cap_addr_width")] is None,
           "a pattern matching two sites must answer None rather than the first")
    ensure(fmt.sites[("the profile's exponent row", "cap_E_width")] == 4,
           "one duplicated site must not take its neighbours with it")


def _budget_matching_twice_is_withheld() -> None:
    files = dict(_FILES)
    files[capformat.SPEC] = _SPEC + "and spends all 32 bits (20+2+3+4+5+3) again.\n"
    with _tree(files) as root:
        fmt = capformat.read(root)
    ensure("the specification's bit budget" not in fmt.budgets,
           "a budget sentence found twice must be withheld rather than read once")


def _moved_site_is_none() -> None:
    files = dict(_FILES)
    files[capformat.PACKAGE] = _PACKAGE.replace(
        "localparam int unsigned CapAddrWidth = 20;",
        "localparam int CapAddrWidth = 20;")
    with _tree(files) as root:
        fmt = capformat.read(root)
    ensure(fmt.sites[("the package's CapAddrWidth", "cap_addr_width")] is None,
           "a site whose form has moved must answer None rather than dropping out")


def _packing_withheld_when_short() -> None:
    # A packing is six fields or it is nothing: five would compare field by field
    # against a set the parse had guessed at, and the sixth field's absence is exactly
    # what a reserved field looks like.
    files = dict(_FILES)
    files[capformat.PACKAGE] = _PACKAGE.replace("    ret.otype   = c[28:27];\n", "")
    with _tree(files) as root:
        fmt = capformat.read(root)
    ensure("the package's packing" not in fmt.packings,
           "a packing short of a field must be withheld whole")
    ensure("the model's own packing" in fmt.packings,
           "one withheld packing must not take the other with it")


def _packings_read() -> None:
    with _tree(_FILES) as root:
        fmt = capformat.read(root)
    ensure(set(fmt.packings) == {"the model's own packing", "the package's packing"},
           f"the packings read back as {sorted(fmt.packings)}")
    for label, packing in fmt.packings.items():
        ensure(set(packing) == set(fmt.fields),
               f"{label} read back {sorted(packing)}")
        ensure(packing["address"] == (14, 0), f"{label} put address at "
                                              f"{packing['address']}")
        # the two spell three of the six fields differently, so the parse's own
        # mapping is what makes them comparable at all
        ensure(packing["E"] == (26, 23), f"{label} put E at {packing['E']}")


def _absent_files() -> None:
    with _tree({}) as root:
        fmt = capformat.read(root)
    ensure(all(v is None for v in fmt.defined.values()),
           "an empty root must answer None at every definition")
    ensure(all(v is None for v in fmt.sites.values()),
           "an empty root must answer None at every site")
    ensure(fmt.packings == {}, "an empty root must yield no packing to compare")
    ensure(fmt.budgets == {}, "an empty root must yield no budget to compare")


def cases() -> list[Case]:
    return [
        Case("definitions-read", _definitions_read),
        Case("every-site-read", _every_site_read),
        Case("budgets-read", _budgets_read),
        Case("site-matching-twice-is-none", _site_matching_twice_is_none),
        Case("budget-matching-twice-is-withheld", _budget_matching_twice_is_withheld),
        Case("moved-declaration-is-none", _moved_declaration_is_none),
        Case("moved-site-is-none", _moved_site_is_none),
        Case("packing-withheld-when-short", _packing_withheld_when_short),
        Case("packings-read", _packings_read),
        Case("absent-files", _absent_files),
    ]
