# SPDX-License-Identifier: Apache-2.0
"""Native Rocq inventory queries and their strictly framed responses.

Search runs in a fresh process with both search filters disabled. It includes local
constants and generated Program obligations, which source declaration scans miss.
Every returned symbol receives its own Print Assumptions query. No source-authored
query contributes to this inventory or to the verdict.
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
