# SPDX-License-Identifier: Apache-2.0
"""meta: the rule registry against the checks this package carries, both directions.

tools/check-rules.md enumerates what the checker checks, one row per rule, each
stating what passing means and on what ground, so the review gate can price the
tool's reach by reading a table instead of this source. The closure is the same shape
as every conferral the register uses: registry and code are two artifacts, and their
agreement is held mechanically in both directions, a K- id here with no registry row
and a registry row no check carries.

The scan is static, over the sources of `vos.checks` alone, so a check a repair branch
or an early return skips at runtime still counts as carried. It is deliberately not
the whole of `tools/`: the mutation selftest names every rule too, and scanning it
would make this agreement trivially true and stop deciding anything. What no scan
decides is whether a registered claim is the right claim, which is the same residue
every conferral declares.
"""

import re
from pathlib import Path

HEADING = "=== meta: the rule registry against the checks carried ==="

RULES = "tools/check-rules.md"
RULE_ID_RE = re.compile(r"\bK-\d\d\b")
REGISTRY_ROW_RE = re.compile(r"^\| (K-\d\d) \|")


def carried_rules() -> set[str]:
    """Every rule id the checks package names."""
    found: set[str] = set()
    for source in sorted(Path(__file__).parent.glob("*.py")):
        found.update(RULE_ID_RE.findall(source.read_text(encoding="utf-8")))
    return found


def run(ctx) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    doc = ctx.corpus.get(RULES)
    if doc is None:
        rep.report("K-00", "missing artifact:", [f"{RULES} is not in the repository"])
        rep.line()
        return

    in_code = carried_rules()

    registered: list[str] = []
    for line in doc.lines:
        m = REGISTRY_ROW_RE.match(line)
        if m:
            registered.append(m.group(1))

    seen: set[str] = set()
    findings: list[str] = []
    for rule in registered:
        if rule in seen:
            findings.append(f"{rule} has more than one registry row")
        seen.add(rule)
    findings += [f"{r} is registered and no check here carries it"
                 for r in registered if r not in in_code]
    findings += [f"{r} is carried here and has no registry row"
                 for r in sorted(in_code) if r not in seen]

    rep.report("K-00", "rule id(s) the registry and the checks disagree on:", findings,
               f"the registry's {len(seen)} rules and the checks agree, both directions")
    rep.line()
