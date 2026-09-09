# SPDX-License-Identifier: Apache-2.0
"""Generate the RTL adapter's capability exception section from its Sail owners.

The complete named enum and mapping determine the generated declarations. The
small packing functions are translated only in their reviewed shapes; an owner
with unsupported syntax, missing definitions or duplicate rows refuses emission.
"""

import json
import re
from pathlib import Path

from vos import jsonc

CAUSES = "model/model/core/cap_causes.sail"
EXCEPTIONS = "model/model/core/types_ext.sail"
TYPES = "model/model/core/types.sail"
XLEN = "model/model/core/xlen.sail"
CONFIG = "model/config/verifiedos.json"
COMMON_TYPES = "model/model/core/types_common.sail"
OWNERS = (CAUSES, EXCEPTIONS, TYPES, XLEN, CONFIG, COMMON_TYPES)
ADAPTER = "rtl/vos_cva6_cheri_pkg.sv"
BEGIN = "  // BEGIN GENERATED CAPABILITY EXCEPTIONS"
END = "  // END GENERATED CAPABILITY EXCEPTIONS"


class CauseError(ValueError):
    """An owner or the generated region no longer has a supported shape."""


def _bare(text: str) -> str:
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.DOTALL)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _one(text: str, pattern: str, label: str) -> str:
    matches = list(re.finditer(pattern, text, re.DOTALL | re.MULTILINE))
    if len(matches) != 1:
        raise CauseError(f"{label}: expected one readable definition, found {len(matches)}")
    return matches[0].group(1)


def _named(text: str, kind: str, name: str) -> None:
    count = len(re.findall(rf"(?m)^\s*{kind}\s+{name}\b", text))
    if count != 1:
        raise CauseError(f"Sail {name}: expected one declaration, found {count}")


def _body(text: str, name: str, signature: str) -> str:
    _named(text, "function", name)
    return _one(text, rf"^\s*function\s+{name}{signature}\s*=\s*(.*?)"
                r"(?=^\s*(?:function|type|newtype|enum|let|mapping|val)\b|\Z)",
                f"Sail {name} body")


def _rows(body: str, pattern: str, label: str) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for row in body.strip().removesuffix(",").split(","):
        match = re.fullmatch(pattern, row.strip())
        if match is None:
            raise CauseError(f"{label}: unreadable or empty row {row.strip()!r}")
        rows.append(match.groups())
    names = [row[0] for row in rows]
    if len(names) != len(set(names)):
        raise CauseError(f"{label}: duplicate cause name")
    return rows


def _shape(text: str, pattern: str, expected: str, label: str) -> None:
    found = _one(text, pattern, label)
    if _compact(found) != _compact(expected):
        raise CauseError(f"{label}: unsupported shape {found.strip()!r}")


def render(causes: str, exceptions: str, types: str, xlen: str, config: str,
           common_types: str) -> str:
    """Emit the delimited region; all numeric values come from Sail definitions."""
    causes, exceptions, types, xlen, common_types = map(
        _bare, (causes, exceptions, types, xlen, common_types))
    for source, kind, name in (
        (xlen, "type", "xlen"), (types, "type", "base_E_enabled"),
        (types, "newtype", "regidx"), (types, "type", "regidx_bit_width"),
        (causes, "type", "capreg_idx"), (causes, "enum", "CapEx"),
        (causes, "let", "PCC_IDX"), (exceptions, "mapping", "ext_exc_type_bits"),
        (common_types, "type", "exc_code"), (xlen, "type", "xlenbits"),
    ):
        _named(source, kind, name)
    xlen_width = int(_one(xlen, r"\btype\s+xlen\s*:\s*Int\s*=\s*(\d+)[ \t]*$", "Sail xlen"))
    _shape(xlen, r"\btype\s+xlenbits\s*=\s*([^\n]+)", "bits(xlen)", "Sail xlenbits")
    exception_width = int(_one(common_types, r"\btype\s+exc_code\s*=\s*bits\((\d+)\)[ \t]*$",
                               "Sail exc_code"))
    if exception_width < 1 or exception_width > xlen_width:
        raise CauseError("Sail exc_code width does not fit xlen")
    _shape(types, r"\btype\s+base_E_enabled\s*:\s*Bool\s*=\s*([^\n]+)",
           "config base.E", "Sail register-file selection")
    _shape(types, r"\bnewtype\s+regidx\s*=\s*Regidx\s*:\s*([^\n]+)",
           "bits(regidx_bit_width)", "Sail regidx")
    widths = _one(types, r"\btype\s+regidx_bit_width\s*=\s*([^\n]+)", "Sail regidx width")
    widths_match = re.fullmatch(r"if\s+base_E_enabled\s+then\s+(\d+)\s+else\s+(\d+)",
                               widths.strip())
    if widths_match is None:
        raise CauseError("Sail regidx width selection has unsupported syntax")
    try:
        base_e = json.loads(jsonc.strip_comments(config))["base"]["E"]
    except (ValueError, KeyError, TypeError) as exc:
        raise CauseError(f"{CONFIG}: cannot read base.E") from exc
    if not isinstance(base_e, bool):
        raise CauseError(f"{CONFIG}: base.E must be boolean")
    file_width = int(widths_match.group(1 if base_e else 2))
    reg_width = int(_one(causes, r"\btype\s+capreg_idx\s*=\s*bits\((\d+)\)[ \t]*$",
                         "Sail capreg_idx"))
    code_width = int(_one(causes,
                         r"\bfunction\s+CapExCode\([^)]*\)\s*->\s*bits\((\d+)\)",
                         "Sail CapExCode width"))
    if file_width < 1 or reg_width < file_width or code_width < 1:
        raise CauseError("Sail exception widths do not admit the register-index conversion")
    if reg_width + code_width > xlen_width:
        raise CauseError("Sail exception payload does not fit xlen")
    enum_body = _one(causes, r"\benum\s+CapEx\s*=\s*\{([^}]+)\}[ \t]*$", "Sail CapEx")
    enum = _rows(enum_body, r"(CapEx_\w+)", "Sail CapEx")
    table_body = _body(causes, "CapExCode", r"\(ex\s*:\s*CapEx\)\s*->\s*bits\(\d+\)")
    table_match = re.fullmatch(r"\s*match\s+ex\s*\{([^}]+)\}\s*", table_body, re.DOTALL)
    if table_match is None:
        raise CauseError("Sail CapExCode table has unsupported syntax")
    table = table_match.group(1)
    rows = _rows(table, r"(CapEx_\w+)\s*=>\s*0b([01]+)", "Sail CapExCode")
    codes = dict(rows)
    if {row[0] for row in enum} != set(codes):
        raise CauseError("Sail CapExCode does not cover exactly the CapEx enumeration")
    if any(len(bits) != code_width for bits in codes.values()):
        raise CauseError("Sail CapExCode literal width disagrees with its result type")
    if len(set(codes.values())) != len(codes):
        raise CauseError("Sail CapExCode repeats a cause encoding")
    pcc = _one(causes, r"\blet\s+PCC_IDX\s*:\s*capreg_idx\s*=\s*0b([01]+)[ \t]*$",
               "Sail PCC_IDX")
    if len(pcc) != reg_width:
        raise CauseError("Sail PCC_IDX literal width disagrees with capreg_idx")
    mapping = _one(exceptions, r"\bmapping\s+ext_exc_type_bits\s*:\s*ext_exc_type\s*<->"
                   r"\s*exc_code\s*=\s*\{([^}]+)\}[ \t]*$", "Sail exception mapping")
    mapping_match = re.fullmatch(r"\s*EXC_CHERI\s*<->\s*0b([01]+)\s*,?\s*", mapping)
    if mapping_match is None:
        raise CauseError("Sail EXC_CHERI mapping has unsupported or duplicate rows")
    if len(mapping_match.group(1)) != exception_width:
        raise CauseError("Sail EXC_CHERI literal width disagrees with exc_code")
    cause = int(mapping_match.group(1), 2)
    # These are translations of the owner's packing and zero-extension, rather
    # than arbitrary expressions the emitter claims to understand as Sail.
    register_body = _body(causes, "capreg_idx_of_regidx",
                          r"\(Regidx\(r\)\s*:\s*regidx\)\s*->\s*capreg_idx")
    packing_body = _body(causes, "capex_tval",
                         r"\(capEx\s*:\s*CapEx,\s*regnum\s*:\s*capreg_idx\)\s*->\s*xlenbits")
    if _compact(register_body) != "zero_extend(r)":
        raise CauseError("Sail register index conversion has unsupported syntax")
    if _compact(packing_body) != "zero_extend(regnum@CapExCode(capEx))":
        raise CauseError("Sail capex_tval packing has unsupported syntax")
    padding = max(len(name) for (name,) in enum)
    members = ",\n".join(f"    {name:<{padding}} = {code_width}'b{codes[name]}"
                          for (name,) in enum)
    return f"""{BEGIN}
  // Generated from {CAUSES} and
  // {EXCEPTIONS}, with its mapped width from
  // {COMMON_TYPES} and register widths from
  // {TYPES}, {XLEN} and
  // {CONFIG}; repair with tools/run.py check --fix.
  localparam int unsigned CapExCodeWidth = {code_width};
  localparam int unsigned CapRegIdxWidth = {reg_width};
  localparam int unsigned CapRegFileIdxWidth = {file_width};

  typedef logic [CapExCodeWidth-1:0] cap_ex_code_t;
  typedef logic [CapRegIdxWidth-1:0] capreg_idx_t;

  typedef enum logic [CapExCodeWidth-1:0] {{
{members}
  }} cap_ex_t;

  function automatic cap_ex_code_t CapExCode(cap_ex_t ex);
    return cap_ex_code_t'(ex);
  endfunction

  localparam capreg_idx_t PCC_IDX = {reg_width}'b{pcc};

  function automatic capreg_idx_t capreg_idx_of_regidx(logic [CapRegFileIdxWidth-1:0] r);
    return {{{{(CapRegIdxWidth - CapRegFileIdxWidth){{1'b0}}}}, r}};
  endfunction

  typedef struct packed {{
    capreg_idx_t  regnum;
    cap_ex_code_t code;
  }} cap_tval_t;

  function automatic logic [XLEN-1:0] capex_tval(cap_ex_t ex, capreg_idx_t regnum);
    cap_tval_t t;
    t.regnum = regnum;
    t.code   = CapExCode(ex);
    return {{{{(XLEN - $bits(cap_tval_t)){{1'b0}}}}, t}};
  endfunction

  localparam logic [XLEN-1:0] CAP_EXCEPTION = {cause};
{END}
"""


def emit(root: Path) -> str:
    sources: list[str] = []
    for name in OWNERS:
        try:
            sources.append((root / name).read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            raise CauseError(f"{name}: cannot read exception owner: {exc}") from exc
    return render(*sources)


def replace(text: str, region: str) -> str:
    """Replace exactly one complete region; malformed delimiters never guess a span."""
    if text.count(BEGIN.strip()) != 1 or text.count(END.strip()) != 1:
        raise CauseError("the adapter must carry exactly one pair of exception delimiters")
    pattern = rf"(?m)^{re.escape(BEGIN)}\r?\n.*?^{re.escape(END)}\r?\n"
    matches = list(re.finditer(pattern, text, re.DOTALL))
    if len(matches) != 1:
        raise CauseError("the adapter's exception delimiters are reversed or malformed")
    match = matches[0]
    return text[:match.start()] + region + text[match.end():]
