# SPDX-License-Identifier: Apache-2.0
"""The frozen capability format's parameters, read out of every artifact that writes one.

This parse reaches past the documents into the curated model, as `geometry.py`,
`coreclass.py` and `decode.py` do, and the reach is declared rather than habitual.

**The model's half is resolved by name out of the generated bundle and the rest is
not.** The ten parameters below are Sail *definitions*, and the emitter indexes every
one of them by the name the model gives it, so a renamed or deleted declaration is a
lookup that misses and says which name missed. What is bought is exactly that and no
more: the bundle hands back the declaration's own text, `type cap_addr_width : Int =
36`, so the figure is still one `= <n>` extraction further in and the pattern that takes
it is unchanged. Under a file scan the same rename was a regex quietly matching nothing,
which reads as a moved site and is indistinguishable from a value nobody wrote down.

Everything else here stays a scan of the artifact that writes it, and two of those
artifacts are inside the model: the address-space sentence and the maximum-exponent
sentence are *comments*, which `--doc-format identity` drops, so they do not appear in
the bundle at all and a rule that dropped their patterns would stop holding two
restatements. A regex whose fact the bundle does not carry is kept.

The format is fixed in three Sail files, `model/model/core/cap_format.sail`
for the packed fields, `cap_common.sail` for the permission bitmap and the reserved
object types, and `core/xlen.sail` for the register width the address field sits
inside, and it is restated in eight other artifacts: the authored SystemVerilog
package, the curated synthesis configuration, the frozen profile, the
re-parameterization delta, the specification, the version matrix, the block-geometry
constraint, and two comments inside the model beside the declarations themselves. Every
one of those is a hand transcription, and a width that drifts in any of them is a
document describing a format the machine does not have.

**What is read here and what is not.** The block size is deliberately absent: it is a
capability-format declaration too, but four instructions share it and it is written in
two configurations and a harness besides, so it has an owner already in `geometry.py`
and K-57, and a parameter with two rules holding it is a parameter whose two rules can
disagree. The permission lattice's own table is likewise absent, being sixteen rows of
bitmap rather than a width.

**Every figure here is read as digits.** Several artifacts state the same parameters as
count-words instead, "sixteen classes" and "thirteen composition-allocatable" among
them, and those are outside this reader rather than held by it. Naming the residue is
the point: a rule that quietly reached some of the restatements would report `ok` about
a subject larger than the one it read.

**Everything here is a parse and never a decision**, as everywhere else in this package.
What the values must be, which derivations they owe, and which disagreements matter is
`vos/checks/counts_capformat.py`'s. A file that is not there, or a declaration that
has moved out of the form read below, yields `None` for its site rather than raising,
because a missing artifact is a finding the caller words and not an exception it has
to catch.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import sailbundle

CAP_FORMAT = "model/model/core/cap_format.sail"
CAP_COMMON = "model/model/core/cap_common.sail"
XLEN_FILE = "model/model/core/xlen.sail"
PACKAGE = "rtl/vos_cheri_pkg.sv"
CONFIG = "rtl/vos_c_class_config_pkg.sv"
PROFILE = "docs/isa-profile.md"
DELTA = "docs/rtl-reparameterization-delta.md"
SPEC = "docs/spec.md"
MATRIX = "docs/cheri-version-matrix.md"
BLOCK = "docs/block-geometry-constraint.md"

# The figure a Sail declaration ends in, whichever of the two forms it takes:
# `type cap_addr_width : Int = 36` and `let reserved_otypes = 3` differ in everything
# ahead of the `=` and in nothing after it, which is why the bundle resolving the name
# leaves one pattern here where the file scan needed two.
SAIL_VALUE_RE = re.compile(r"=\s*(\d+)\s*\Z")

# Which map of the bundle a definition is indexed in. `TYPE` is a Sail type synonym and
# `LET` a top-level binding, and the emitter keeps them apart, so this says which
# lookup a name is owed rather than trying both and taking whichever answered.
TYPE, LET = "type", "let"


def _sv_param(name: str) -> str:
    return rf"(?m)^\s*localparam int unsigned {re.escape(name)} = (\d+);"


# The parameters the Sail model fixes: the key this repository reads them by, which of
# the bundle's maps declares it, and the file a finding sends a reader to. The key is
# the model's own spelling, which is also the name the bundle indexes it under, so a
# reader of a finding can grep the definition for it and a rename is a miss here.
DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("cap_size", TYPE, CAP_FORMAT),
    ("log2_cap_size", TYPE, CAP_FORMAT),
    ("cap_perms_code_width", TYPE, CAP_FORMAT),
    ("cap_otype_width", TYPE, CAP_FORMAT),
    ("cap_mantissa_width", TYPE, CAP_FORMAT),
    ("cap_E_width", TYPE, CAP_FORMAT),
    ("cap_addr_width", TYPE, CAP_FORMAT),
    ("cap_perms_width", TYPE, CAP_COMMON),
    ("reserved_otypes", LET, CAP_COMMON),
    ("xlen", TYPE, XLEN_FILE),
)

# Every other site that writes one of those parameters or one of the figures they
# derive: the file, the key it states, a label a finding names it by, and the pattern
# capturing the figure alone. Each pattern holds exactly one site in its own file,
# which a site table owes because a finding names the site rather than the match.
SITES: tuple[tuple[str, str, str, str], ...] = (
    # The model's own prose, beside the declarations. Both are restatements: the
    # declaration is the fact and the sentence is a copy of it.
    (CAP_FORMAT, "cap_addr_width", "the model's own address-space sentence",
     r"The address space is (\d+) bits"),
    (CAP_COMMON, "cap_max_E", "the model's own maximum-exponent sentence",
     r"runs to `cap_max_E` = (\d+)"),

    # The authored SystemVerilog package.
    (PACKAGE, "cap_size", "the package's CapSize", _sv_param("CapSize")),
    (PACKAGE, "log2_cap_size", "the package's Log2CapSize", _sv_param("Log2CapSize")),
    (PACKAGE, "cap_perms_code_width", "the package's CapPermsCodeWidth",
     _sv_param("CapPermsCodeWidth")),
    (PACKAGE, "cap_perms_width", "the package's CapPermsWidth",
     _sv_param("CapPermsWidth")),
    (PACKAGE, "cap_otype_width", "the package's CapOTypeWidth",
     _sv_param("CapOTypeWidth")),
    (PACKAGE, "reserved_otypes", "the package's ReservedOTypes",
     _sv_param("ReservedOTypes")),
    (PACKAGE, "cap_mantissa_width", "the package's CapMantissaWidth",
     _sv_param("CapMantissaWidth")),
    (PACKAGE, "cap_E_width", "the package's CapEWidth", _sv_param("CapEWidth")),
    (PACKAGE, "cap_addr_width", "the package's CapAddrWidth",
     _sv_param("CapAddrWidth")),
    (PACKAGE, "xlen", "the package's Xlen", _sv_param("Xlen")),

    # The curated synthesis configuration, whose XLEN is the same width the format
    # spends its address field inside.
    (CONFIG, "xlen", "the configuration package's XLEN",
     r"(?m)^\s*XLEN:\s*unsigned'\((\d+)\),"),

    # The frozen profile's own field table.
    (PROFILE, "cap_addr_width", "the profile's address row",
     r"(?m)^\| address \| (\d+) \|"),
    (PROFILE, "cap_otype_width", "the profile's object-type row",
     r"(?m)^\| object type \| (\d+) \|"),
    (PROFILE, "cap_perms_code_width", "the profile's permissions row",
     r"(?m)^\| permissions \| (\d+) \|"),
    (PROFILE, "cap_E_width", "the profile's exponent row",
     r"(?m)^\| exponent \| (\d+) \|"),
    (PROFILE, "cap_mantissa_width", "the profile's base-mantissa row",
     r"(?m)^\| base mantissa \| (\d+) \|"),
    (PROFILE, "stored_mantissa_width", "the profile's top-mantissa row",
     r"(?m)^\| top mantissa \| (\d+) \|"),

    # The re-parameterization delta's statement of the frozen dialect, which is the
    # column a curator reads the imported datapath against.
    (DELTA, "cap_width", "the delta's width row",
     r"(?m)^\| Width, excluding the tag \| (\d+) \|"),
    (DELTA, "cap_addr_width", "the delta's address row",
     r"(?m)^\| Address field \| (\d+), stored uncompressed \|"),
    (DELTA, "cap_perms_code_width", "the delta's permission-code figure",
     r"one (\d+)-bit code naming one of \d+ enumerated sets"),
    (DELTA, "perms_codepoints", "the delta's permission-codepoint figure",
     r"one \d+-bit code naming one of (\d+) enumerated sets"),
    (DELTA, "cap_perms_width", "the delta's permission-bitmap figure",
     r"expanded to a (\d+)-bit architectural bitmap"),
    (DELTA, "cap_otype_width", "the delta's object-type row",
     r"(?m)^\| Object type \| (\d+) bits, sixteen classes"),
    (DELTA, "cap_E_width", "the delta's exponent row",
     r"(?m)^\| Exponent \| (\d+)-bit field"),
    (DELTA, "cap_mantissa_width", "the delta's base-mantissa row",
     r"(?m)^\| Base mantissa \| (\d+) \|"),
    (DELTA, "stored_mantissa_width", "the delta's top-mantissa row",
     r"(?m)^\| Top mantissa \| (\d+) stored, high two derived \|"),
    (DELTA, "cap_max_E", "the delta's maximum-exponent row",
     r"(?m)^\| Maximum effective exponent \| (\d+) \|"),
    (DELTA, "cap_max_E", "the delta's reset-exponent row",
     r"the reset exponent is `cap_max_E`, (\d+), not zero"),
    (DELTA, "cap_max_E", "the delta's CAP_MAX_EXP row",
     r"\| (\d+), which is `cap_len_width - cap_mantissa_width \+ 1` \|"),
    (DELTA, "cap_max_E", "the delta's exponent-clamp row",
     r"\| `exp > CAP_MAX_EXP \? CAP_MAX_EXP` \| literal \| (\d+) \|"),

    # The specification's own statement of the parameterization, which is the prose
    # R-15-007 was extracted from. Its address figure is deliberately not a site: the
    # document states that width in more than one sentence, and a pattern matching two
    # of them would be a site this rule reports as moved rather than one it holds.
    (SPEC, "cap_otype_width", "the specification's object-type figure",
     r"a (\d+)-bit object type"),
    (SPEC, "cap_perms_code_width", "the specification's permission-code figure",
     r"(\d+)-bit encoded permissions"),
    (SPEC, "cap_E_width", "the specification's exponent figure",
     r"a (\d+)-bit exponent"),
    (SPEC, "cap_mantissa_width", "the specification's base-mantissa figure",
     r"(\d+)-bit base and \d+-bit top mantissas"),
    (SPEC, "stored_mantissa_width", "the specification's top-mantissa figure",
     r"\d+-bit base and (\d+)-bit top mantissas"),

    # The profile's prose beside its own table, which states the same widths a second
    # way and is where a reader of §4.1 arrives from.
    (PROFILE, "cap_addr_width", "the profile's address figure",
     r"a (\d+)-bit address"),
    (PROFILE, "cap_mantissa_width", "the profile's base-mantissa figure",
     r"(\d+)- and \d+-bit mantissas"),
    (PROFILE, "stored_mantissa_width", "the profile's top-mantissa figure",
     r"\d+- and (\d+)-bit mantissas"),

    # The block-geometry constraint's own statement of the register width, which is
    # the operand the welded block's ceiling is taken against and which K-57 now reads
    # out of the model rather than writing down.
    (BLOCK, "xlen", "the block constraint's integer-register width",
     r"an integer register is (\d+) bits"),
)

# The budget sentences: the one claim four artifacts rest on, that the packed fields
# spend the capability exactly and leave no reserved field, written out as a sum. Each
# names the six fields in the profile's own reading order, address first, and each is
# read as seven figures rather than as a string so that the arithmetic is recomputed
# and not compared to itself.
BUDGET_FIELDS = ("cap_addr_width", "cap_otype_width", "cap_perms_code_width",
                 "cap_E_width", "cap_mantissa_width", "stored_mantissa_width")

BUDGETS: tuple[tuple[str, str, str], ...] = (
    (SPEC, "the specification's bit budget",
     r"spends all (?P<total>\d+) bits \((?P<f1>\d+)\+(?P<f2>\d+)\+(?P<f3>\d+)"
     r"\+(?P<f4>\d+)\+(?P<f5>\d+)\+(?P<f6>\d+)\)"),
    (MATRIX, "the version matrix's software-defined-permission row",
     r"itself \((?P<f1>\d+)\+(?P<f2>\d+)\+(?P<f3>\d+)\+(?P<f4>\d+)\+(?P<f5>\d+)"
     r"\+(?P<f6>\d+) = (?P<total>\d+) exactly"),
    (MATRIX, "the version matrix's revocation-colour row",
     r"no spare bits \((?P<f1>\d+)\+(?P<f2>\d+)\+(?P<f3>\d+)\+(?P<f4>\d+)"
     r"\+(?P<f5>\d+)\+(?P<f6>\d+) = (?P<total>\d+)\)"),
)

# The packed form, at both packings. The six fields sit at fixed positions and the
# positions are what a curator most easily gets wrong: a field shifted by one bit
# elaborates, decodes, and is a different capability at one exponent.
_FIELDS = ("perms", "otype", "E", "B", "T", "address")

_SAIL_SLICE_RE = re.compile(
    r"(?m)^\s*(perms|otype|E|B|T|address)\s*=\s*c\[(\d+) \.\. (\d+)\],")
# the package spells three of the six differently, so the reading names both spellings
# rather than assuming a transform between them
_SV_SLICE_RE = re.compile(
    r"(?m)^\s*ret\.(perms|otype|e_field|b|t|address)\s*=\s*c\[(\d+):(\d+)\];")
_SV_FIELD_NAMES = {"perms": "perms", "otype": "otype", "e_field": "E",
                   "b": "B", "t": "T", "address": "address"}


@dataclass
class Format:
    """Every site's answer, keyed by what the site is rather than where it is."""

    # parameter -> the value the Sail definition fixes, None where it has moved
    defined: dict[str, int | None] = field(default_factory=dict)
    # (label, key) -> the value the site writes, None where the site has moved
    sites: dict[tuple[str, str], int | None] = field(default_factory=dict)
    # packing label -> field -> its (high, low) bit positions, empty where it has moved
    packings: dict[str, dict[str, tuple[int, int]]] = field(default_factory=dict)
    # budget label -> the six field widths it writes and the total, empty where the
    # sentence has moved
    budgets: dict[str, tuple[tuple[int, ...], int]] = field(default_factory=dict)
    # the parameters the model does not declare under the name this reads them by,
    # which is a different fact from a declaration whose figure has moved out of the
    # read form and is worded differently by the rule
    undeclared: set[str] = field(default_factory=set)

    @property
    def fields(self) -> tuple[str, ...]:
        """The packed fields, most significant first, as both packings write them."""
        return _FIELDS


def _int(pattern: str, text: str) -> int | None:
    """The one figure a pattern finds, or `None` where it finds none or several.

    Several is the same answer as none on purpose, and it is the discipline
    `geometry.py` already keeps at its template site: every row of the table above
    claims to hold exactly one site in its own file, and a pattern that has come to
    match two of them is holding whichever one a search happened to reach first. A
    finding names the site, so a site that is no longer one has to be reported rather
    than read.
    """
    found = re.findall(pattern, text)
    return int(found[0]) if len(found) == 1 else None


def _declared(bundle: sailbundle.Bundle | None, key: str, kind: str) -> str | int | None:
    """One definition's figure, `None` where its declaration has moved out of the read
    form, and the key itself where the model declares no such name at all.

    Three answers rather than two, because the third is the one the bundle made
    available: a name that is not there is a rename or a deletion and says so, where a
    file scan could only report that a pattern matched nothing.
    """
    if bundle is None:
        return key
    try:
        text = (bundle.type_text(key) if kind == TYPE else bundle.let_text(key))
    except sailbundle.BundleError:
        return key
    found = SAIL_VALUE_RE.search(text.strip())
    return int(found.group(1)) if found else None


def read(root: Path, bundle: sailbundle.Bundle | None) -> Format:
    """One pass over every artifact that writes a capability-format parameter.

    The definitions come from `bundle` and everything else from the tree. A `None`
    bundle is a run with no readable generated artifact, which leaves every definition
    unresolved and is a finding K-88 has already worded; the sites are still read, so
    the rule can say which of the two halves it lost.
    """
    fmt = Format()
    cache: dict[str, str] = {}

    def text(rel: str) -> str:
        if rel not in cache:
            path = root / rel
            cache[rel] = path.read_text(encoding="utf-8") if path.is_file() else ""
        return cache[rel]

    for key, kind, _ in DEFINITIONS:
        got = _declared(bundle, key, kind)
        if isinstance(got, str):
            fmt.undeclared.add(key)
            fmt.defined[key] = None
        else:
            fmt.defined[key] = got

    for rel, key, label, pattern in SITES:
        fmt.sites[(label, key)] = _int(pattern, text(rel))

    sail = {name: (int(hi), int(lo))
            for name, hi, lo in _SAIL_SLICE_RE.findall(text(CAP_FORMAT))}
    if set(sail) == set(_FIELDS):
        fmt.packings["the model's own packing"] = sail

    package = {_SV_FIELD_NAMES[name]: (int(hi), int(lo))
               for name, hi, lo in _SV_SLICE_RE.findall(text(PACKAGE))}
    if set(package) == set(_FIELDS):
        fmt.packings["the package's packing"] = package

    for rel, label, pattern in BUDGETS:
        found = re.findall(pattern, text(rel))
        if len(found) != 1:
            continue                       # absent or no longer one site: reported
        hit = re.search(pattern, text(rel))
        if hit is None:
            continue
        fmt.budgets[label] = (tuple(int(hit.group(f"f{i}")) for i in range(1, 7)),
                              int(hit.group("total")))

    return fmt
