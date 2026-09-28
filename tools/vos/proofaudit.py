# SPDX-License-Identifier: Apache-2.0
"""Native Rocq inventory queries and their strictly framed responses.

Search runs in a fresh process with both search filters disabled. It includes local
constants and generated Program obligations, which source declaration scans miss.
Every returned symbol receives its own Print Assumptions query. No source-authored
query contributes to this inventory or to the verdict. The kernel checker's own
context summary is parsed here too, as a second enumeration that does not share the
compiler's Print Assumptions.
"""

import re
from collections import defaultdict
from typing import TypedDict

from vos import proofcites
from vos.proofs import sentences

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

# Settings the compiler command line fixes, or whose default the audit relies on. A
# source that sets one overrides that choice for itself, so the gate refuses it.
PINNED_SETTINGS = ("Warnings", "Default Goal Selector", "Bullet Behavior",
                   "Nested Proofs Allowed", "Allow StrictProp", "Definitional UIP",
                   "Guard Checking", "Positivity Checking", "Universe Checking",
                   "Strict Universe Declaration", "Default Timeout")
_PREFIXES = (r'(?:#\[[^\]]*\]\s*|(?:Local|Global|Export|Time|Fail|Succeed)\s+'
             r'|Redirect\s+"[^"]*"\s+)*')
_PINNED = re.compile(_PREFIXES + r"(?:Set|Unset)\s+(?:" + "|".join(
    r"\s+".join(map(re.escape, name.split())) for name in PINNED_SETTINGS) + r")\b")
# Attributes that relax the same settings for one declaration. A wall-clock Timeout
# makes a verdict depend on the machine that ran it.
_PINNED_ATTRIBUTE = re.compile(r"#\[[^\]]*\b(?:warnings?|bypass_check)\b")
_TIMEOUT = re.compile(_PREFIXES + r"Timeout\s+\d")


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
    """Every native symbol, refusing diagnostics and an active search filter."""
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
    """Resolve each annotation to exactly one compiled constant in this artifact."""
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


def assumption_query(module: str, symbols: list[Symbol]) -> str:
    lines = [f"Require {module}.\n", SETTINGS]
    for symbol in symbols:
        name = symbol["name"]
        if not QUALIFIED.fullmatch(name):
            raise AuditError(f"invalid native symbol name {name!r}")
        lines += [f'Goal True. idtac "{MARKER}{name}". Abort.\n',
                  f"Print Assumptions {name}.\n"]
        if symbol["claims"]:
            # The source keyword Theorem can introduce a term of type nat. The
            # kernel, rather than that keyword, must decide that a claim is a Prop.
            lines.append(f"Goal True. let T := type of (@{name}) in "
                         "let K := type of T in unify K Prop. exact I. Qed.\n")
    return "".join(lines)


def assumptions(stdout: str, symbols: list[Symbol]) -> None:
    """Require one complete native answer for every queried symbol, in order."""
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
    """The axioms `rocqchk -o` names, refusing every other assumption it reports.

    The summary covers the whole environment the checker loaded, admitted and `-norec`
    modules included, so an axiom that is loaded but never used is named as well. Rocq
    9.2's Print Assumptions misses an axiom that a definition reaches only through its
    type; this enumeration does not. It does not report definitional UIP, which the
    Print Assumptions audit does. rocqchk writes the summary to stderr, and nothing
    else may appear there: an unrecognized line refuses the run.
    """
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
    if [key for key, _, _ in sections] != ["Theory", "Theory", "Axioms", *KERNEL_UNSAFE]:
        raise AuditError("unrecognized kernel context sections: "
                         + ", ".join(key for key, _, _ in sections))
    theory = tuple(value for key, value, _ in sections[:2])
    if theory != KERNEL_THEORY:
        raise AuditError("the kernel checked a non-default theory: " + "; ".join(theory))
    for key, value, entries in sections[3:]:
        if value != "<none>" or entries:
            raise AuditError(f"{key}: {', '.join(entries) or value}")
    _, value, axioms = sections[2]
    if (value == "<none>") == bool(axioms) or value not in ("", "<none>"):
        raise AuditError(f"malformed kernel axiom list: {value or 'empty'}")
    return axioms


def pinned_overrides(text: str) -> list[str]:
    """Sentences that would change a gate-pinned setting for their own source."""
    return [sentence for sentence in sentences(text)
            if _PINNED.match(sentence) or _PINNED_ATTRIBUTE.search(sentence)
            or _TIMEOUT.match(sentence)]


def unsupported_abstractions(text: str) -> list[str]:
    """Reject inaccessible module bodies instead of claiming a partial inventory.

    Ordinary nested modules and generated obligations are supported. Functors and
    sealed signatures need a module-body audit, since Search cannot enumerate their
    inaccessible constants. They are not present in the shipped proof tree.
    """
    found: list[str] = []
    for sentence in sentences(text):
        if re.match(r"^(?:Declare\s+)?Module\s+Type\b", sentence):
            found.append(sentence)
        elif re.match(r"^(?:Declare\s+)?Module\s+", sentence):
            header = sentence.split(":=", 1)[0]
            if "(" in header or ":" in header or sentence.startswith("Declare "):
                found.append(sentence)
    return found
