# SPDX-License-Identifier: Apache-2.0
"""Check rule registry alignment, landing declarations, quarantine isolation, and provisioner facts (`K-00`, `K-83`, `K-84`, `K-100`).

- `K-00` checks [tools/check-registry.json](../../check-registry.json) against the
  executed check groups and verifies that the generated sections of
  [tools/check-rules.md](../../check-rules.md) match the registry (rewriting them under
  `--fix`).
- `K-84` checks that every bold rule citation (`**K-XX**`) in the Markdown corpus names
  an active, quarantined, or (in [docs/implementation/completion-log.md](../../../docs/implementation/completion-log.md))
  retired rule, and that every `Landed:` line in [PLAN.md](../../../PLAN.md) and
  [docs/implementation/completion-log.md](../../../docs/implementation/completion-log.md)
  declares `Tier A` or `Tier B` with a bold holder rule on `Tier B` landings.
- `K-83` checks that no tracked Python file under `tools/` outside `tools/quarantine/`
  imports `quarantine` or (except for `_Q_PATH_EXEMPT`: this module and
  [vos/cli/selftest.py](../cli/selftest.py)) references the `quarantine` directory path.
- `K-100` checks that every row in [`FACTS`](../cli/provision.py#FACTS) names a tracked
  owner path, that any symbol named in `path's SYMBOL` form still exists in that file,
  and that any `run.py <cmd>` reference names a command in
  [`COMMANDS`](../commands.py#COMMANDS).
"""

import re
from typing import TYPE_CHECKING

from vos import checkregistry
from vos import commands as command_table
from vos.cli import provision

if TYPE_CHECKING:
    from . import Context

HEADING = "=== meta: the rule registry against the checks carried ==="

RULES = "tools/check-rules.md"
Q_RULES = "tools/quarantine/check-rules.md"

PROVISION = "tools/vos/cli/provision.py"

PLAN = "PLAN.md"
LOG = "docs/implementation/completion-log.md"

# Bold rule citation (`**K-XX**`) claiming a rule holds a landed fact.
_HOLDER_RE = re.compile(rf"\*\*({checkregistry.ID_PATTERN})\*\*")

# Line-anchored `Landed:` declaration and its required `Tier A` / `Tier B` structure.
_LANDED_RE = re.compile(r"[^\S\r\n]*(?:\*+ )?Landed:")
_TIER_RE = re.compile(r"[^\S\r\n]*(?:\*+ )?Landed: Tier (?P<tier>[AB])\b(?P<rest>.*)")

TOOLS_TREE = "tools/"
QUARANTINE_TREE = "tools/quarantine/"
SOURCE_SUFFIX = ".py"

# Line-anchored import of `quarantine` or any submodule under it.
_Q_IMPORT_RE = re.compile(
    r"(?m)^[ \t]*(?:from[ \t]+(quarantine(?:\.[\w.]+)?)[ \t]+import\b"
    r"|import[ \t]+(quarantine(?:\.[\w.]+)?)\b)")

# Delimited path/module reference to `quarantine` (excludes prose like `"quarantine entries"`).
_Q_PATH_RE = re.compile(
    r"""[/\\]quarantine\b|quarantine[/\\]|["']quarantine["']|["']quarantine\.""")

# Only this module and the mutation selftest may spell the quarantine directory path.
_Q_PATH_EXEMPT = ("tools/vos/checks/meta.py", "tools/vos/cli/selftest.py")

# Repository path and optional `path's SYMBOL` reference in `provision.FACTS` owner cells.
_OWNER_PATH_RE = re.compile(r"((?:[\w.-]+/)*[\w.-]+\.(?:py|toml|md|txt))")
_OWNER_SYM_RE = re.compile(
    r"((?:[\w.-]+/)*[\w.-]+\.(?:py|toml|md|txt))'s "
    r"([A-Za-z_]\w*(?:\(\w*\))?(?: and [A-Za-z_]*[A-Z_]\w*)*)")

# `run.py` is checked as a command reference rather than a file path in owner/needs cells.
_ENTRY_POINT = "run.py"
_OWNER_CMD_RE = re.compile(r"run\.py ([a-z][\w-]*)")

# Symbol lookups are restricted to `tools/` and tracked corpus documents (`model/` is excluded).
_SYMBOL_TREE = "tools/"


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)
    if ctx.registry is None:
        try:
            ctx.registry = checkregistry.read(ctx.root)
        except (OSError, ValueError, TypeError) as exc:
            ctx.registry_faults.append(str(exc))
    seen = set(ctx.registry.identifiers) if ctx.registry is not None else set()
    _landings(ctx, seen | _quarantined_rules(ctx))
    _quarantine(ctx)
    _lane(ctx)
    _registry(ctx)
    rep.line()


def _registry(ctx: Context) -> None:
    """K-00: generated views and actual group verdicts share one typed owner."""
    findings = list(ctx.registry_faults)
    if checkregistry.SOURCE not in ctx.corpus.tracked:
        findings.append(f"{checkregistry.SOURCE} is not tracked")
    doc = ctx.corpus.get(RULES)
    if doc is None:
        findings.append(f"{RULES} is not in the repository")
    elif ctx.registry is not None:
        try:
            rendered = checkregistry.render(ctx.registry, doc.raw)
        except ValueError as exc:
            findings.append(str(exc))
        else:
            if rendered != doc.raw:
                if ctx.fix:
                    ctx.fixed[RULES] = rendered
                    ctx.rep.line(f"fixed: {RULES} from its rule metadata")
                else:
                    findings.append(f"{RULES} has stale generated registry or reach views")
    if ctx.registry is not None:
        # This is the final verdict in the final group. It checks all prior group
        # reports plus this group's other rules, before reporting itself.
        rules = [r for r in ctx.registry.rules if r.group == "meta" and r.ident != "K-00"]
        findings += checkregistry.verdict_faults(
            rules, ctx.rep.decisions[ctx.group_start:],
            clean=ctx.rep.findings == ctx.group_findings)
    ctx.rep.report("K-00", "invalid rule definitions, verdicts or generated views:", findings,
                   "typed rule metadata binds the executable groups, every clean group "
                   "decides its declared rules, and generated registry views agree")


def _lane(ctx: Context) -> None:
    """K-100: every row of the [WSL provision fact table](../cli/provision.py#FACTS) names tracked paths, symbols, and commands.

    Checks that `FACTS` is non-empty, each row names at least one tracked path,
    every `path's SYMBOL` token still appears in that file, and every `run.py <cmd>`
    reference names a registered command (with non-zero symbol and command count floors).
    """
    rep = ctx.rep
    findings: list[str] = []
    facts = provision.FACTS
    if not facts:
        findings.append(f"{PROVISION} declares no fact at all, so this lane is described "
                        "by nothing and there is no row to hold")

    commands = {command.name for command in command_table.COMMANDS}
    paths = symbols = named = 0
    for fact in facts:
        found = [path for path in _OWNER_PATH_RE.findall(fact.owner)
                 if path != _ENTRY_POINT]
        if not found:
            findings.append(f"the row for `{fact.name}` names no artifact this rule can "
                            f"read as a path, so what owns that fact is unresolvable")
        carried = set()
        for path in found:
            paths += 1
            if path in ctx.corpus.tracked:
                carried.add(path)
            else:
                findings.append(f"the row for `{fact.name}` names {path} as what owns it, "
                                "and the git index carries no such path")

        for path, group in _OWNER_SYM_RE.findall(fact.owner):
            if path not in carried:
                continue
            if not (path.startswith(_SYMBOL_TREE) or path in ctx.corpus):
                continue
            text = _source(ctx, path) if path.startswith(_SYMBOL_TREE) else ctx.text(path)
            for symbol in group.split(" and "):
                symbols += 1
                if symbol not in text:
                    findings.append(
                        f"the row for `{fact.name}` names `{symbol}` as {path}'s, and that "
                        "file no longer spells it, so the fact names a consumer this "
                        "tree does not have")

        for command in _OWNER_CMD_RE.findall(f"{fact.needs} {fact.owner}"):
            named += 1
            if command not in commands:
                findings.append(f"the row for `{fact.name}` names `run.py {command}` as what "
                                "wants it, and the entry point carries no such command")

    if facts and not symbols:
        findings.append("no row of the lane's fact table names a symbol as an artifact's "
                        "own, so the reading that holds a consumer's name against the "
                        "file spelling it decides nothing")
    if facts and not named:
        findings.append("no row of the lane's fact table names a `run.py` command, so "
                        "the reading that holds a row's consumer against the entry "
                        "point's table decides nothing")

    rep.report("K-100", "row(s) of the lane's fact table naming what this tree does not "
               "carry:", findings,
               f"the {paths} artifacts {PROVISION}'s {len(facts)} rows name are paths the "
               f"index carries, the {symbols} symbols they name are ones those files "
               f"still spell, and the {named} run.py commands they name are the entry "
               "point's")


def _source(ctx: Context, rel: str) -> str:
    """Read a `tools/` file from disk, returning `""` on I/O or decode failure."""
    try:
        return (ctx.root / rel).read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return ""


def _quarantined_rules(ctx: Context) -> set[str]:
    """Return rule IDs listed in the quarantine registry (`tools/quarantine/README.md`).

    Used by K-84 for holder citations, not by K-00 (which checks only rules
    executed by the main checker).
    """
    doc = ctx.corpus.get(Q_RULES)
    if doc is None:
        return set()
    return {m.group(1) for m in re.finditer(
        rf"(?m)^\|\s*({checkregistry.ID_PATTERN})\s*\|", doc.raw)}


def _landings(ctx: Context, registered: set[str]) -> None:
    """K-84: every `**K-NN**` holder citation names a registered rule, and every Tier-B landing names one.

    Retired (`~~K-NN~~`) rule IDs are valid only in [completion-log.md](../../../docs/implementation/completion-log.md).
    """
    rep = ctx.rep
    findings: list[str] = []
    registry = ctx.corpus.get(RULES)
    retired = ({m.group(1) for _, m in registry.unfenced(
        "| ~~K-", re.compile(rf"^\| ~~({checkregistry.ID_PATTERN})~~ \| retired \|"))}
        if registry is not None else set())

    if not registered:
        findings.append(f"neither {RULES} nor {Q_RULES} yields a rule this run can "
                        "read, so a holder citation would be held against nothing")

    cited = 0
    for doc in ctx.corpus.docs:
        for m in _HOLDER_RE.finditer(doc.raw):
            if doc.is_fenced(m.start()):
                continue
            cited += 1
            if m.group(1) not in registered and not (
                    doc.name == LOG and m.group(1) in retired):
                findings.append(f"{doc.name}:{doc.at(m.start())} names {m.group(1)} as "
                                f"the rule holding what it created, and {RULES} carries "
                                "no active rule for that claim (retired rules apply "
                                "only to completion-log evidence)")
    if not cited and registered:
        findings.append("no document names a rule holding what a landing created, so "
                        "this rule reads nothing; the form is the rule id in bold, which "
                        f"{PLAN}'s checklist conventions fix")

    # Landed items record their declaration in completion-log.md; open items stay in PLAN.md.
    declared = 0
    for name in (PLAN, LOG):
        doc = ctx.corpus.get(name)
        if doc is None:
            findings.append(f"{name} is not in the repository, so no landing can be "
                            "read there")
            continue
        for i, _ in doc.unfenced("Landed:", _LANDED_RE):
            declared += 1
            tier = _TIER_RE.match(doc.lines[i])
            if tier is None:
                findings.append(f"{name}:{i + 1} declares a landing in a form this rule "
                                "does not read; a declaration is 'Landed: Tier A' or "
                                "'Landed: Tier B under' the rules holding what it created")
            elif tier.group("tier") == "B" and not _HOLDER_RE.search(tier.group("rest")):
                findings.append(f"{name}:{i + 1} lands at Tier B and names no rule "
                                "holding what it created, which is the fourth of the "
                                "four conditions Tier B is admitted on")

    rep.report("K-84", "holder citation(s) and landing declaration(s) no registry "
               "answers:", findings,
               f"the corpus's {cited} holder citations name active, quarantined or "
               f"historical retired rules, and each of the {declared} landing declarations "
               "in the plan and the completion log states a tier and, at Tier B, the "
               "rule holding what it created")


def _at(text: str, offset: int) -> int:
    """Return the 1-based line number for `offset` in `text`."""
    return text.count("\n", 0, offset) + 1


def _reaches(path: str, text: str) -> list[str]:
    """Return findings for any quarantine import or path reference in `text`."""
    if "quarantine" not in text:
        return []
    found: list[str] = []
    for hit in _Q_IMPORT_RE.finditer(text):
        named = hit.group(1) or hit.group(2)
        found.append(f"{path}:{_at(text, hit.start())} imports `{named}`, and the "
                     "quarantine is what the landing loop does not depend on")
    launch = None if path in _Q_PATH_EXEMPT else _Q_PATH_RE.search(text)
    if launch is not None:
        found.append(f"{path}:{_at(text, launch.start())} names the quarantine as a "
                     "path, which couples it to an instrument whose decision is "
                     "deferred exactly as an import would")
    return found


def _quarantine(ctx: Context) -> None:
    """K-83: no Python file under `tools/` outside `tools/quarantine/` imports or references `tools/quarantine/`."""
    rep = ctx.rep
    findings: list[str] = []

    roster = [path for path in ctx.corpus.tracked
              if path.startswith(QUARANTINE_TREE) and path.endswith(SOURCE_SUFFIX)]
    window = [path for path in ctx.corpus.tracked
              if path.startswith(TOOLS_TREE) and path.endswith(SOURCE_SUFFIX)
              and not path.startswith(QUARANTINE_TREE)]
    if not roster:
        findings.append(f"the index carries no {SOURCE_SUFFIX} file under "
                        f"{QUARANTINE_TREE}, so there is no quarantine for this rule to "
                        "hold anything out of")
    if not window:
        findings.append(f"the index carries no {SOURCE_SUFFIX} file under {TOOLS_TREE} "
                        "outside the quarantine, so this rule reads no site at all")

    if roster and window:
        for path in window:
            if not (ctx.root / path).is_file():
                findings.append(f"{path} is in the index and not on disk, so whether it "
                                "reaches into the quarantine is undecided")
                continue
            findings += _reaches(path, _source(ctx, path))

    rep.report("K-83", "site(s) outside the quarantine that reach into it:", findings,
               f"none of the {len(window)} sources under {TOOLS_TREE} outside the "
               f"quarantine imports or launches one of the {len(roster)} it carries")
