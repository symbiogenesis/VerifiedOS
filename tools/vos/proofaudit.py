# SPDX-License-Identifier: Apache-2.0
"""Native Rocq inventory/assumption queries, `rocqchk -o` context parsing, and lexical refusals."""

import re
from collections import defaultdict
from typing import TypedDict

from vos import proofcites
from vos.proofs import ATTRIBUTE_OPEN, CONTROL_PREFIXES, SENTENCE_END, sentences

MARKER = "VOS_PROOF_AUDIT|"
EMPTY_BLACKLIST = "Current search blacklist :  is empty."
QUALIFIED = re.compile(r"[\w']+(?:\.[\w']+)+")
_SYMBOL = re.compile(r"^([\w']+(?:\.[\w']+)+):\s*(.*)$")

SETTINGS = '''\
Remove Search Blacklist "_subterm" "_subproof" "Private_".
Unset Search Blacklist Locals.
Unset Search Output Name Only.
Set Printing All.
Set Printing Depth 1000000.
Set Printing Width 1000000.
'''


KERNEL_CONTEXT = ("CONTEXT SUMMARY", "===============")
KERNEL_THEORY = ("Set is predicative", "Rewrite rules are not allowed")
KERNEL_UNSAFE = ("Constants/Inductives relying on type-in-type",
                 "Constants/Inductives relying on unsafe (co)fixpoints",
                 "Inductives whose positivity is assumed")
# Final section of `rocqchk -o` summary (indices_matter=false in CIC checker profile).
KERNEL_INDICES = "Inductives relying on indices not mattering"

# Compiler/typing settings fixed by the proof gate that sources may not override.
PINNED_SETTINGS = ("Warnings", "Default Goal Selector", "Bullet Behavior",
                   "Nested Proofs Allowed", "Allow StrictProp", "Definitional UIP",
                   "Guard Checking", "Positivity Checking", "Universe Checking",
                   "Indices Matter", "Strict Universe Declaration", "Default Timeout",
                   "Kernel Conversion Dep Heuristic", "Default Proof Using")
_PINNED = re.compile(CONTROL_PREFIXES + r"(?:Set|Unset)\s+(?:" + "|".join(
    r"\s+".join(map(re.escape, name.split())) for name in PINNED_SETTINGS) + r")\b")
_PINNED_ATTRIBUTE = re.compile(ATTRIBUTE_OPEN + r"\b(?:warnings?|bypass_check)\b")
_TIMEOUT = re.compile(CONTROL_PREFIXES + r"(?:Timeout|AllocLimit)\s+\d")

# Match standalone refused words (`_TACTICAL`, `_COINDUCTIVE`) after quotes, underscores,
# or numerals where Rocq 9.3.0's lexer splits tokens (`do 1timeout`, `#_timeout`, etc.).
_WORD = r"A-Za-z0-9_'"
_HEXADECIMAL = r"0[xX][0-9a-fA-F][0-9a-fA-F_]*(?:\.[0-9a-fA-F_]+)?(?:[pP][+-]?[0-9][0-9_]*)?"
_DECIMAL = r"[0-9](?:(?!0[xX][0-9a-fA-F])[0-9_])*(?:\.[0-9_]+)?(?:[eE][+-]?[0-9][0-9_]*)?"
_APART = rf"(?<![{_WORD}])(?:['_]|{_HEXADECIMAL}|{_DECIMAL})*+"
_TACTICAL = re.compile(_APART + rf"(?:timeoutf?|alloc_limit)(?![{_WORD}])")
_STRING = re.compile(r'"[^"]*"')
_MODULE = re.compile(CONTROL_PREFIXES + r"(Declare\s+)?Module\s+(Type\b)?")

# Commands that load external files, plugins, or Ltac2 external primitives dynamically.
DYNAMIC_SOURCE = re.compile(
    CONTROL_PREFIXES + r"(?:Load|Cd|(?:Add|Remove)\s+(?:Rec\s+)?(?:LoadPath|ML\s+Path)"
    r"|Declare\s+ML\s+Module|Ltac2\s*@\s*external)(?![\w'])")

# Notation and Infix commands that declare custom lexer tokens before `:=`.
_DECLARES_TOKENS = re.compile(r"(?<![\w'])(?:Notation|Infix)(?![\w'])")
_TOKEN_SOURCE = re.compile(ATTRIBUTE_OPEN + r'\]|"((?:[^"]|"")*)"|:=')


class AuditError(ValueError):
    """A native response cannot support a complete audit."""


class Symbol(TypedDict):
    name: str
    type: str
    assumptions: list[str]
    claims: list[str]


def inventory_query(module: str) -> str:
    return (f"Require {module}.\n{SETTINGS}Print Table Search Blacklist.\n"
            f"Search _ inside {module}.\n")


def inventory(stdout: str, module: str) -> list[Symbol]:
    """Parse `Search _ inside <module>` output after verifying an empty search blacklist."""
    lines = stdout.splitlines()
    if not lines or lines[0].strip() != EMPTY_BLACKLIST:
        raise AuditError("Rocq did not confirm an empty search blacklist")
    found: list[Symbol] = []
    seen: set[str] = set()
    for line in lines[1:]:
        if not line.strip():
            continue
        match = _SYMBOL.fullmatch(line)
        if match:
            name, typ = match.groups()
            if not name.startswith(f"{module}.") or name in seen:
                raise AuditError(f"unexpected or repeated native symbol {name}")
            seen.add(name)
            found.append({"name": name, "type": typ, "assumptions": [], "claims": []})
        elif line[:1].isspace() and found:
            found[-1]["type"] += " " + line.strip()
        else:
            raise AuditError(f"unrecognized native inventory output: {line}")
    if any(not symbol["type"] for symbol in found):
        raise AuditError("a native symbol has no type")
    return sorted(found, key=lambda symbol: symbol["name"])


def bind_claims(text: str, symbols: list[Symbol]) -> None:
    """Resolve each discharge annotation in `text` to a unique compiled symbol in `symbols`."""
    claims, faults = proofcites.discharges(text)
    if faults:
        raise AuditError("; ".join(faults))
    if not claims:
        return
    by_name: dict[str, list[Symbol]] = defaultdict(list)
    for symbol in symbols:
        _, separator, name = symbol["name"].rpartition(".")
        if separator:
            by_name[name].append(symbol)
    for name, entries in claims:
        matches = by_name.get(name, [])
        if len(matches) != 1:
            raise AuditError(f"claim {name} resolves to {len(matches)} native symbols; "
                             "a claim must identify one compiled declaration")
        symbol = matches[0]
        if symbol["claims"]:
            raise AuditError(f"{name} carries more than one discharge annotation")
        symbol["claims"] = entries


def _assumption_block(name: str) -> list[str]:
    """Build a framed `Print Assumptions <name>` snippet preceded by `MARKER`."""
    if not QUALIFIED.fullmatch(name):
        raise AuditError(f"invalid native symbol name {name!r}")
    return [f'Goal True. Proof. idtac "{MARKER}{name}". Abort.\n',
            f"Print Assumptions {name}.\n"]


def assumption_query(module: str, symbols: list[Symbol]) -> str:
    lines = [f"Require {module}.\n", SETTINGS]
    for symbol in symbols:
        name = symbol["name"]
        lines += _assumption_block(name)
        if symbol["claims"]:
            # Verify in the kernel that every symbol carrying discharge claims has type `Prop`.
            lines.append(f"Goal True. Proof. let T := type of (@{name}) in "
                         "let K := type of T in unify K Prop. exact I. Qed.\n")
    return "".join(lines)


_ROOT = re.compile(r"[\w']+")


def sealed_field_query(roots: list[str], names: list[str]) -> str:
    """Build a framed `Print Assumptions` query for sealed-module fields `names` under `roots`."""
    for root in roots:
        if not _ROOT.fullmatch(root):
            raise AuditError(f"invalid proof module name {root!r}")
    if not names:
        raise AuditError("a sealed-field query needs at least one name")
    lines = [f"Require {root}.\n" for root in roots] + [SETTINGS]
    for name in names:
        lines += _assumption_block(name)
    return "".join(lines)


def sealed_field_assumptions(stdout: str, names: list[str]) -> dict[str, list[str]]:
    """Parse framed `Print Assumptions` responses for `names`."""
    symbols: list[Symbol] = [{"name": name, "type": "", "assumptions": [], "claims": []}
                             for name in names]
    assumptions(stdout, symbols)
    return {symbol["name"]: symbol["assumptions"] for symbol in symbols}


def assumptions(stdout: str, symbols: list[Symbol]) -> None:
    """Require one complete framed `Print Assumptions` response per symbol in `symbols`."""
    blocks: list[tuple[str, list[str]]] = []
    for line in stdout.splitlines():
        if line.startswith(MARKER):
            blocks.append((line[len(MARKER):], []))
        elif line.strip():
            if not blocks:
                raise AuditError(f"unframed assumption output: {line}")
            blocks[-1][1].append(line)
    if [name for name, _ in blocks] != [symbol["name"] for symbol in symbols]:
        raise AuditError("native assumption responses do not enumerate exactly the queries")
    for symbol, (_, lines) in zip(symbols, blocks, strict=True):
        if lines == ["Closed under the global context"]:
            continue
        if not lines or lines[0] != "Axioms:" or len(lines) < 2:
            raise AuditError(f"{symbol['name']} has an incomplete assumption response")
        entries: list[str] = []
        for line in lines[1:]:
            if line[:1].isspace() and entries:
                entries[-1] += " " + line.strip()
            elif ":" in line:
                entries.append(line.strip())
            else:
                raise AuditError(f"unrecognized assumption entry: {line}")
        if not entries:
            raise AuditError(f"{symbol['name']} has an empty Axioms block")
        symbol["assumptions"] = entries


def kernel_context(summary: str) -> list[str]:
    """Parse the `rocqchk -o` context summary, returning its `Axioms` list and rejecting unsafe flags."""
    lines = [line.rstrip() for line in summary.splitlines() if line.strip()]
    if tuple(lines[:2]) != KERNEL_CONTEXT:
        raise AuditError("rocqchk printed no context summary")
    sections: list[tuple[str, str, list[str]]] = []
    for line in lines[2:]:
        if line.startswith("* ") and ":" in line:
            key, _, value = line[2:].partition(":")
            sections.append((key, value.strip(), []))
        elif line[:1].isspace() and sections and not sections[-1][1]:
            sections[-1][2].append(line.strip())
        else:
            raise AuditError(f"unrecognized kernel context line: {line}")
    keys = [key for key, _, _ in sections]
    expected = ["Theory", "Theory", "Axioms", *KERNEL_UNSAFE]
    if keys != [*expected, KERNEL_INDICES]:
        raise AuditError("unrecognized kernel context sections: " + ", ".join(keys))
    theory = tuple(value for key, value, _ in sections[:2])
    if theory != KERNEL_THEORY:
        raise AuditError("the kernel checked a non-default theory: " + "; ".join(theory))
    for key, value, entries in sections[3:len(expected)]:
        if value != "<none>" or entries:
            raise AuditError(f"{key}: {', '.join(entries) or value}")
    _, value, axioms = sections[2]
    if (value == "<none>") == bool(axioms) or value not in ("", "<none>"):
        raise AuditError(f"malformed kernel axiom list: {value or 'empty'}")
    for _, value, inductives in sections[len(expected):]:
        if ((value == "<none>") == bool(inductives) or value not in ("", "<none>")
                or not all(QUALIFIED.fullmatch(name) for name in inductives)):
            raise AuditError(f"malformed kernel indices list: "
                             f"{', '.join(inductives) or value or 'empty'}")
    return axioms


def pinned_overrides(text: str) -> list[str]:
    """Return sentences in `text` that override `PINNED_SETTINGS` or invoke timeout/alloc limits."""
    tactical = "timeout" in text or "alloc_limit" in text
    return [sentence for sentence in sentences(text)
            if _PINNED.match(sentence) or _PINNED_ATTRIBUTE.search(sentence)
            or _TIMEOUT.match(sentence)
            or (tactical and _TACTICAL.search(_STRING.sub('""', sentence)))]


def dynamic_sources(text: str) -> list[str]:
    """Return sentences in `text` that load external files, plugins, or Ltac2 externals."""
    return [sentence for sentence in sentences(text) if DYNAMIC_SOURCE.match(sentence)]


_COINDUCTIVE = re.compile(_APART + r"(?:CoInductive|CoFixpoint|CoFix|cofix_|cofix)"
                          rf"(?![{_WORD}])")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")
_HIDING_TAIL = re.compile(rf"[A-Za-z][{_WORD}]*\Z")
_WHOLE_TERMINALS = re.compile(r"(?<![\w'])(?:Tactic|Ltac2)\s+Notation(?![\w'])")


def coinductive_forms(text: str) -> list[str]:
    """Return sentences that use coinductive/cofixpoint forms or declare hiding tokens.

    Rocq 9.3.0's cofixpoint guard checker has soundness bugs (rocq#22386, rocq#22389; see
    [opam/README.md](../opam/README.md)), so `CoInductive`, `CoFixpoint`, `CoFix`,
    `cofix_`, and `cofix` (and custom notation tokens whose trailing word characters could
    hide them from lexical scanning) are rejected.
    """
    words = "cofix" in text or "CoFix" in text or "CoInductive" in text
    declares = "Notation" in text or "Infix" in text
    if not words and not declares:
        return []
    return [sentence for sentence in sentences(text)
            if (words and _COINDUCTIVE.search(_STRING.sub('""', sentence)))
            or (declares and any(map(_hides, _declared_terminals(sentence))))]


def _declared_terminals(sentence: str) -> list[str]:
    """Extract custom lexer terminals declared by a `Notation` or `Infix` sentence."""
    emptied = _STRING.sub('""', sentence)
    if not _DECLARES_TOKENS.search(emptied):
        return []
    whole = _WHOLE_TERMINALS.search(emptied)
    found: list[str] = []
    for part in _TOKEN_SOURCE.finditer(sentence):
        if part.group() == ":=":
            break
        literal = part.group(1)
        if literal is None:
            continue
        found += [_unquote(piece) for piece in literal.split()]
        if not whole:
            break
        found.append(literal.replace(" ", ""))
    return found


def _unquote(piece: str) -> str:
    return piece[1:-1] if len(piece) > 2 and piece[0] == piece[-1] == "'" else piece


def _hides(terminal: str) -> bool:
    """Return True if non-identifier `terminal` ends with word characters containing a letter."""
    return not _IDENTIFIER.fullmatch(terminal) and bool(_HIDING_TAIL.search(terminal))


def unreadable_tokens(text: str) -> list[str]:
    """Return notation sentences declaring tokens that contain `"`, `(*`, or sentence-ending `.`."""
    found: list[str] = []
    for sentence in sentences(text):
        if not _DECLARES_TOKENS.search(_STRING.sub('""', sentence)):
            continue
        for part in _TOKEN_SOURCE.finditer(sentence):
            if part.group() == ":=":
                break
            if part.group(1) is not None and _unreadable(part.group(1)):
                found.append(sentence)
                break
    return found


def _unreadable(literal: str) -> bool:
    return ('"' in literal or "(*" in literal
            or any(SENTENCE_END.search(part.strip("'")) for part in literal.split()))


def unsupported_abstractions(text: str) -> list[str]:
    """Return module sentences that declare functors, module types, or sealed signatures."""
    found: list[str] = []
    for sentence in sentences(text):
        module = _MODULE.match(sentence)
        if module is None:
            continue
        declared, signature = module.groups()
        header = sentence[module.end():].split(":=", 1)[0]
        if declared or signature or "(" in header or ":" in header:
            found.append(sentence)
    return found
