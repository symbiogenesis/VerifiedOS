# SPDX-License-Identifier: Apache-2.0
"""The synthesis-provenance parse, held to what K-76 and the RTL lane rely on.

`vos/provenance.py` is the one parse of rtl/synthesis-provenance.md, and its contract
has four load-bearing edges. A binding cell yields settings or it is `n/a`, and a cell
that is neither must read as unbound rather than as an empty list of settings, because
those two are the same value and opposite verdicts. A table is found by its heading and
ends at the next one, so prose between the two tables cannot be read as rows. The header
row is dropped by the separator that follows it rather than by counting, so a table that
grows a column keeps its first data row. And a field's value is read out of the
configuration package as the integer literals on its line, with a field the package does
not state told apart from one it states differently.
"""

from tests.harness import Case, ensure, sandbox_tree
from vos import provenance

_RECORD = """\
# The Synthesis-Configuration Provenance Record

## 1. How to read this

Prose that mentions `Thing = 3` and must not be read as a row.

## 2. The absences the contract enumerates

| Absence | Structure | Binding | Elaborated result |
| --- | --- | --- | --- |
| A-01 | Something | n/a: the core never had one | none elaborates |
| A-04 | A predictor | `BHTEntries = 0` | `bht` absent |
| A-14 | A walker | `MmuPresent = 0`, `RVS = 0` | four modules absent |
| A-99 | Bound to nothing | it just is not there | none |

Prose after the table, with a stray | pipe that is not a row.

## 3. The profile's ISA-visible removals, and the parameters that take them

| Removal | Binding | Elaborated result |
| --- | --- | --- |
| The `C` extension | `RVC = 0` | `compressed_decoder` absent |

## 4. What no parameter reaches

More prose.
"""

_CONFIG = """\
package cva6_config_pkg;
  localparam config_pkg::cva6_user_cfg_t cva6_cfg = '{
      BHTEntries: unsigned'(0),
      MmuPresent: bit'(0),
      RVS: bit'(1),
      RVC: bit'(0)
  };
endpackage
"""


def _tables_found() -> None:
    with sandbox_tree({provenance.RECORD: _RECORD}) as root:
        record = provenance.read(root)
    ensure(record.present, "a record that is on disk must read as present")
    ensure([r.subject for r in record.absences] == ["A-01", "A-04", "A-14", "A-99"],
           f"the absence table read back as {[r.subject for r in record.absences]}")
    ensure([r.subject for r in record.removals] == ["The `C` extension"],
           f"the removal table read back as {[r.subject for r in record.removals]}")


def _binding_forms_told_apart() -> None:
    with sandbox_tree({provenance.RECORD: _RECORD}) as root:
        record = provenance.read(root)
    by_id = {row.subject: row for row in record.absences}
    ensure(by_id["A-01"].is_na and by_id["A-01"].is_bound,
           "an `n/a` cell with a ground is bound and carries no setting")
    ensure(by_id["A-04"].settings == (("BHTEntries", "0"),),
           f"one setting read back as {by_id['A-04'].settings!r}")
    ensure(by_id["A-14"].settings == (("MmuPresent", "0"), ("RVS", "0")),
           f"two settings read back as {by_id['A-14'].settings!r}")
    # The edge the whole grammar exists for: a cell that binds nothing and states no
    # ground must be unbound, not an empty list of settings that reads as satisfied.
    ensure(not by_id["A-99"].is_bound,
           "a cell that is neither a setting nor `n/a` must read as unbound")


def _identifiers_selected() -> None:
    with sandbox_tree({provenance.RECORD: _RECORD}) as root:
        record = provenance.read(root)
    ensure(provenance.stated_ids(record) == ("A-01", "A-04", "A-14", "A-99"),
           f"the identifiers read back as {provenance.stated_ids(record)!r}")
    # A removal row's subject is prose rather than an identifier, so it must not join
    # the set K-76 holds against the contract's own enumeration.
    ensure(all(not s.startswith("The") for s in provenance.stated_ids(record)),
           "a removal row's subject is not an absence identifier")


def _config_values_read() -> None:
    ensure(provenance.config_values(_CONFIG, "BHTEntries") == (0,),
           "a field set to zero reads back as one zero literal")
    ensure(provenance.config_values(_CONFIG, "RVS") == (1,),
           "a field set to one reads back as one literal, not as the record's value")
    ensure(provenance.config_values(_CONFIG, "NoSuchField") is None,
           "a field the package does not state must be told apart from a mismatch")


def _absent_record_reported() -> None:
    with sandbox_tree({"README.md": "nothing here\n"}) as root:
        record = provenance.read(root)
    ensure(not record.present, "a record that is not on disk must read as absent")
    ensure(record.rows == (), "an absent record carries no rows to pass over")


def cases() -> list[Case]:
    return [
        Case("tables-found-by-heading", _tables_found),
        Case("binding-forms-told-apart", _binding_forms_told_apart),
        Case("identifiers-selected", _identifiers_selected),
        Case("config-values-read", _config_values_read),
        Case("absent-record-reported", _absent_record_reported),
    ]
