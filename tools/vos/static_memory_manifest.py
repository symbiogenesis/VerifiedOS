# SPDX-License-Identifier: Apache-2.0
"""Computed inventory of the static-memory research artifact, and its completeness.

Every part is globbed from the tree or read from the command's own registration, so a
module, document, test or proof a later experiment adds is inventoried with no edit
here. The verdict is completeness alone: a green manifest says the parts are present,
carried by the git index, registered, reachable and classified. It decides no research
claim; a replayed receipt stays bounded finite host evidence rather than a theorem, an
optimality result or a target measurement.

Three reachability conventions are stated here because none is self-evident. A document
is reachable through a Markdown link and not through a mention of its name, so a
basename inside a fenced command line or in a sentence a reader cannot follow leaves the
document a finding. The artifact document is the index of this artifact, so it is the
root of the link graph and a subject of no reachability rule, and it is a source of
none either: it is written beside these rules and names the artifact's own parts, so its
classification table would otherwise satisfy the document rule over anything and one
sentence of its prose would satisfy the module rule for a module nobody registered. And
a test module's topic is answered by a module on either side of the package split,
`vos/static_memory_<topic>.py` or `vos/<topic>/static_memory.py`, which is what keeps the
command's own test out of the rule as a special case nobody wrote down.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, TypedDict

from vos import corpus, memplan

VERSION = "static-memory-manifest-v1"
ACTION = "manifest"
GENERATOR = "tools/vos/static_memory_manifest.py"

AGENDA = "docs/background/static-memory-research.md"
ARTIFACT_DOC = "docs/implementation/static-memory-artifact.md"
COMMAND_MODULE = "tools/vos/cli/static_memory.py"
# Written by `run.py check --fix` from the register and what the shipped proofs cite;
# rule K-106 holds its bytes against that generator.
PROOF_LEDGER = "tools/generated/proof-ledger.md"
GENERATED = (memplan.ARTIFACT, PROOF_LEDGER)

# The heading the classification table sits under, named once so a finding and the
# document cannot come to disagree about where the table is.
CLASSIFICATION_HEADING = "## Result classes and where each carries them"

# The four classes the research agenda names, and two this table adds. "bounded
# executable evidence" separates a replayed finite check from a measurement and from a
# proof; "elementary argument in prose" is what the baseline's laminar theorem is, and
# without it a hand proof would have to borrow the name of a class it is not.
CLASSES = (
    "peer-reviewed result cited",
    "preprint cited",
    "new conjecture",
    "measured outcome",
    "bounded executable evidence",
    "elementary argument in prose",
)

# The smallest budgets the command's own tests use, so that a replay decides whether an
# action still runs and refuses to stand in for the research run a receipt quotes.
REPLAY_SETTINGS: dict[str, tuple[str, ...]] = {
    "compare": ("--max-nodes", "1"),
    "scale": ("--sizes", "4", "--max-nodes", "100", "--q5-max-leaves", "1"),
}

# A Markdown link target ending in .md, with the optional heading fragment a reader
# writes, which is how a classification row names its document and how one document
# links another. Reachability is decided on this and not on a bare mention, so a
# document named inside a fenced block or in a sentence carrying no link stays a
# finding until somebody gives a reader a way to arrive at it.
LINK_RE = re.compile(r"\(([^()\s#]+\.md)(?:#[^()\s]*)?\)")


class Kind(TypedDict):
    """One globbed kind: where it lives, what its files are called, and its topic split."""

    kind: str
    directory: str
    pattern: str
    prefix: str
    suffix: str


MODULE_KIND: Kind = {"kind": "module", "directory": "tools/vos",
                     "pattern": "static_memory*.py", "prefix": "static_memory", "suffix": ".py"}
TEST_KIND: Kind = {"kind": "test", "directory": "tools/tests",
                   "pattern": "test_static_memory*.py", "prefix": "test_static_memory",
                   "suffix": ".py"}
DOCUMENT_KIND: Kind = {"kind": "document", "directory": "docs/implementation",
                       "pattern": "static-memory-*.md", "prefix": "static-memory-",
                       "suffix": ".md"}
PROOF_KIND: Kind = {"kind": "proof", "directory": "proofs", "pattern": "StaticMemory*.v",
                    "prefix": "StaticMemory", "suffix": ".v"}
GENERATED_KIND = "generated input"
SOURCE_KIND = "declared source"

KINDS: tuple[Kind, ...] = (MODULE_KIND, TEST_KIND, DOCUMENT_KIND, PROOF_KIND)


class FileEntry(TypedDict):
    """One inventoried file: what it is, its bytes, and whether the index carries it."""

    kind: str
    path: str
    sha256: str | None
    present: bool
    tracked: bool


class ActionEntry(TypedDict):
    """One accepted action, its exact replay command and the sources it binds."""

    action: str
    replay: str
    declared_sources: list[str]


class ReplayEntry(TypedDict):
    """What one replayed action answered, without repeating its receipt."""

    action: str
    argv: list[str]
    exit_code: int
    schema: str
    scope: str
    errors: list[str]
    receipt_sha256: str


class RowEntry(TypedDict):
    """One classification row: the document it names and the classes it claims."""

    document: str
    classes: list[str]


class Registration(TypedDict):
    """The command's own action set and declared sources, read rather than restated."""

    choices: tuple[str, ...]
    shared_sources: tuple[str, ...]
    per_action: dict[str, tuple[str, ...]]


class Inventory(TypedDict):
    """Every file and action the artifact is made of."""

    files: list[FileEntry]
    actions: list[ActionEntry]


def choices(parser: argparse.ArgumentParser) -> tuple[str, ...]:
    """Every action the parser accepts, read from the parser rather than restated.

    argparse publishes no reader for its own actions, so the positional's `choices` is
    reached through the parser's action list. Fail-closed: a parser this finds no choice
    set in raises, because an empty action inventory would pass every rule below over
    nothing.
    """
    for action in parser._actions:
        if not action.option_strings and action.choices:
            return tuple(str(choice) for choice in action.choices)
    raise ValueError("the static-memory parser declares no positional action choices")


def registration() -> Registration:
    """The command's actions and declared sources.

    Imported here rather than at the top of the module because the command imports this
    module: the deferred import is what keeps that one direction a cycle-free edge.
    """
    from vos.cli import static_memory as command  # noqa: PLC0415  (the command imports this module)
    return {"choices": choices(command.parser()),
            "shared_sources": tuple(command.SOURCES),
            "per_action": dict(command.EXPERIMENT_SOURCES)}


def declared(reg: Registration, action: str) -> list[str]:
    """The source set one action binds: the shared identity plus its own."""
    return sorted({*reg["shared_sources"], *reg["per_action"].get(action, ())})


def replay_command(action: str) -> str:
    """The exact command a reader runs to replay one action."""
    return " ".join(["python", "tools/run.py", "static-memory", action,
                     *REPLAY_SETTINGS.get(action, ()), "--json"])


def listing(root: Path, kind: Kind) -> list[str]:
    """Repository-relative paths of one kind, globbed rather than listed by hand."""
    base = root / kind["directory"]
    if not base.is_dir():
        return []
    return sorted(f"{kind['directory']}/{path.name}" for path in base.glob(kind["pattern"]))


def topic(rel: str, kind: Kind) -> str:
    """The `<topic>` of a `<prefix><topic><suffix>` path; empty for the bare name."""
    name = rel.rsplit("/", 1)[-1]
    if not (name.startswith(kind["prefix"]) and name.endswith(kind["suffix"])):
        raise ValueError(f"{rel} is not a {kind['prefix']}*{kind['suffix']} path")
    return name[len(kind["prefix"]):len(name) - len(kind["suffix"])].lstrip("_-")


def digests(root: Path, names: tuple[str, ...]) -> dict[str, str]:
    """Hash the inventory's bytes through the command's own `identity`.

    One hashing convention for the whole artifact: the digest a manifest entry carries
    is the digest the action receipts carry for the same file, because it is the same
    function that produced both.
    """
    from vos.cli import static_memory as command  # noqa: PLC0415  (the command imports this module)
    if not names:
        return {}
    bound = command.identity(root, names)["sources_sha256"]
    return {str(name): str(digest) for name, digest in bound.items()}


def inventory(root: Path, reg: Registration) -> Inventory:
    """Every file and action of the artifact, with its bytes and index membership."""
    indexed = corpus.load(root).indexed
    listed: dict[str, str] = {}
    for kind in KINDS:
        for rel in listing(root, kind):
            listed.setdefault(rel, kind["kind"])
    listed.setdefault(AGENDA, DOCUMENT_KIND["kind"])
    listed.setdefault(COMMAND_MODULE, MODULE_KIND["kind"])
    for rel in GENERATED:
        listed.setdefault(rel, GENERATED_KIND)
    for action in reg["choices"]:
        for rel in declared(reg, action):
            listed.setdefault(rel, SOURCE_KIND)

    present = tuple(rel for rel in sorted(listed) if (root / rel).is_file())
    bound = digests(root, present)
    files = [FileEntry(kind=listed[rel], path=rel, sha256=bound.get(rel),
                       present=rel in present, tracked=rel in indexed)
             for rel in sorted(listed)]
    actions = [ActionEntry(action=action, replay=replay_command(action),
                           declared_sources=declared(reg, action))
               for action in sorted(reg["choices"])]
    return {"files": files, "actions": actions}


def of_kind(items: Inventory, kind: str) -> list[str]:
    """Every inventoried path of one kind, in path order."""
    return [entry["path"] for entry in items["files"] if entry["kind"] == kind]


def texts(root: Path, items: Inventory) -> dict[str, str]:
    """The working-tree text of every inventoried document that is readable.

    Working-tree contents against index membership, which is how `tools/check.py` reads
    the corpus: an unstaged edit already decides, and an untracked file is a finding of
    its own rather than a document this silently trusts.
    """
    result: dict[str, str] = {}
    for rel in of_kind(items, DOCUMENT_KIND["kind"]):
        path = root / rel
        if path.is_file():
            result[rel] = path.read_text(encoding="utf-8")
    return result


def classification(root: Path) -> list[RowEntry]:
    """The artifact document's classification rows, resolved to repository paths.

    A row names its document by an ordinary Markdown link, so the table a reader follows
    and the table this parses are the same table.
    """
    path = root / ARTIFACT_DOC
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if CLASSIFICATION_HEADING not in lines:
        return []
    rows: list[RowEntry] = []
    started = False
    for line in lines[lines.index(CLASSIFICATION_HEADING) + 1:]:
        stripped = line.strip()
        if stripped.startswith("#"):
            break
        if not stripped.startswith("|"):
            if started:
                break
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(cell and set(cell) <= {"-", ":"} for cell in cells):
            started = True
            continue
        if not started or len(cells) < 2:
            continue
        found = LINK_RE.search(cells[0])
        rows.append(RowEntry(
            document=resolved(root, ARTIFACT_DOC, found.group(1)) if found else cells[0],
            classes=[part.strip() for part in cells[1].split(";") if part.strip()]))
    return rows


def resolved(root: Path, source: str, target: str) -> str:
    """One Markdown link target, as the repository-relative path its source reaches.

    A link is read from the document that writes it, so the agenda's
    `../implementation/x.md` and a sibling's bare `x.md` name the same file.
    """
    try:
        return (root / source).parent.joinpath(target).resolve().relative_to(
            root.resolve()).as_posix()
    except ValueError:
        return target


def links(root: Path, source: str, text: str) -> set[str]:
    """Every document one document links to, excluding a link back to itself."""
    return {resolved(root, source, found.group(1))
            for found in LINK_RE.finditer(text)} - {source}


def _index_findings(items: Inventory) -> list[str]:
    """Every inventoried file is on disk and carried by the index."""
    result: list[str] = []
    for entry in items["files"]:
        if not entry["present"]:
            result.append(f"{entry['path']}: the artifact's {entry['kind']} inventory names "
                          "it and the working tree does not carry it")
        elif not entry["tracked"]:
            result.append(f"{entry['path']}: the git index does not carry this "
                          f"{entry['kind']}, so nothing decided about it means anything")
    return result


def witnesses(prose: dict[str, str]) -> dict[str, str]:
    """The documents a reachability rule may be satisfied by.

    The index is excluded as a source of every reachability rule, because it is written
    beside the rules and names the artifact's own parts: a mention there is the manifest
    lane's own word that a part is reachable, not a reader's way of arriving at it.
    Without the exclusion the classification table would satisfy the document rule over
    anything, and one sentence of this document's prose would satisfy the module rule for
    a module whose action nobody registered.
    """
    return {rel: text for rel, text in prose.items() if rel != ARTIFACT_DOC}


def _module_findings(items: Inventory, reg: Registration, prose: dict[str, str]) -> list[str]:
    """Every topic module is reachable through an action or through a document."""
    result: list[str] = []
    sources = witnesses(prose)
    for rel in of_kind(items, MODULE_KIND["kind"]):
        if rel == COMMAND_MODULE:
            continue
        name = rel.rsplit("/", 1)[-1]
        subject = topic(rel, MODULE_KIND)
        if not subject or subject in reg["choices"]:
            continue
        if any(name in text for text in sources.values()):
            continue
        result.append(f"{rel}: a static-memory module carries neither a registered "
                      "action of its topic nor a document outside the index naming it")
    return result


def _document_findings(root: Path, items: Inventory, prose: dict[str, str]) -> list[str]:
    """Every document but the index is linked by another document.

    A Markdown link and not a mention, because the rule exists so that a reader can
    arrive at the document: a basename appearing in a fenced command line or in a
    sentence nobody can click decides nothing about reachability. The artifact document
    is excluded as a subject because it is the root of the link graph, and as a source
    for the reason `witnesses` states.
    """
    inbound: set[str] = set()
    for other, text in witnesses(prose).items():
        inbound |= links(root, other, text)
    return [f"{rel}: no other static-memory document and not the research agenda links "
            "to this document"
            for rel in of_kind(items, DOCUMENT_KIND["kind"])
            if rel not in (ARTIFACT_DOC, AGENDA) and rel not in inbound]


def _test_findings(root: Path, items: Inventory) -> list[str]:
    """Every test module has a module of its own topic."""
    result: list[str] = []
    modules = set(of_kind(items, MODULE_KIND["kind"]))
    for rel in of_kind(items, TEST_KIND["kind"]):
        name = topic(rel, TEST_KIND)
        candidates = [f"tools/vos/static_memory{'_' + name if name else ''}.py"]
        if name:
            candidates.append(f"tools/vos/{name}/static_memory.py")
        if any(candidate in modules or (root / candidate).is_file()
               for candidate in candidates):
            continue
        result.append(f"{rel}: no static-memory module carries this test's topic "
                      f"'{name}', so the test names a subject the artifact does not ship")
    return result


def _proof_findings(root: Path, items: Inventory) -> list[str]:
    """Every shipped static-memory proof is joined by a row of the proof ledger."""
    proofs = of_kind(items, PROOF_KIND["kind"])
    if not proofs:
        return []
    path = root / PROOF_LEDGER
    if not path.is_file():
        return [f"{PROOF_LEDGER}: the generated proof ledger is absent, so no shipped "
                "static-memory proof can be decided against it"]
    ledger = path.read_text(encoding="utf-8")
    return [f"{rel}: no row of {PROOF_LEDGER} names this proof, so it cites no live "
            "requirement or the ledger has not been regenerated by `run.py check --fix`"
            for rel in proofs if rel not in ledger]


def _classification_findings(items: Inventory, rows: list[RowEntry]) -> list[str]:
    """The classification table names every document, and only documents."""
    documents = set(of_kind(items, DOCUMENT_KIND["kind"]))
    if not rows:
        return [f"{ARTIFACT_DOC}: no classification table stands under "
                f"'{CLASSIFICATION_HEADING}', so no document's result classes are stated"]
    counted = Counter(row["document"] for row in rows)
    named = set(counted)
    result = [f"{rel}: the classification table in {ARTIFACT_DOC} carries no row for "
              "this document, so which result classes it carries is unstated"
              for rel in sorted(documents - named)]
    result += [f"{rel}: the classification table in {ARTIFACT_DOC} names a document the "
               "artifact does not carry" for rel in sorted(named - documents)]
    # Exactly one row, not at least one: two rows can name the same document with class
    # sets that contradict each other, and a set membership test reads that as complete.
    result += [f"{rel}: the classification table in {ARTIFACT_DOC} carries {count} rows "
               "for this document, so its result classes are not decided"
               for rel, count in sorted(counted.items()) if count > 1]
    for row in rows:
        if not row["classes"]:
            result.append(f"{row['document']}: its classification row names no result class")
        result += [f"{row['document']}: '{name}' is not one of the declared result classes"
                   for name in row["classes"] if name not in CLASSES]
    return sorted(result)


def _replay_findings(replays: list[ReplayEntry]) -> list[str]:
    """A replayed action that refused, or that answered with its own errors."""
    return [f"{entry['action']}: the replay of `{replay_command(entry['action'])}` "
            f"exited {entry['exit_code']} with {entry['errors']}"
            for entry in replays if entry["exit_code"] != 0 or entry["errors"]]


def _digest(value: object) -> str:
    """The canonical-JSON digest the sibling experiment receipts use."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _run(argv: list[str]) -> tuple[int, Any]:
    """Run one action in this process and return its exit status and receipt."""
    from vos.cli import static_memory as command  # noqa: PLC0415  (the command imports this module)
    stream = StringIO()
    with redirect_stdout(stream):
        code = command.main(argv)
    return code, json.loads(stream.getvalue())


def replay_action(action: str) -> ReplayEntry:
    """Replay one action at its smallest budget and record what it answered.

    A refusal is a result and never an abort: an action whose receipt cannot be read at
    all is recorded as its own finding, so one broken sibling cannot empty the sweep.
    """
    argv = [action, *REPLAY_SETTINGS.get(action, ()), "--json"]
    entry = ReplayEntry(action=action, argv=argv, exit_code=2, schema="n/a", scope="n/a",
                        errors=[], receipt_sha256="n/a")
    try:
        code, receipt = _run(argv)
    except (SystemExit, OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        entry["errors"] = [f"replay raised {type(error).__name__}: {error}"]
        return entry
    entry["exit_code"] = code
    entry["receipt_sha256"] = _digest(receipt)
    if not isinstance(receipt, dict):
        entry["errors"] = ["the receipt is not an object"]
        return entry
    experiment = receipt.get("experiment", {})
    inner = experiment if isinstance(experiment, dict) else {}
    entry["schema"] = str(receipt.get("schema", "n/a"))
    entry["scope"] = str(inner.get("scope") or receipt.get("scope") or "n/a")
    reported = inner.get("errors", [])
    entry["errors"] = [str(error) for error in reported] if isinstance(reported, list) else [
        str(reported)]
    if code != 0:
        entry["errors"].append(f"the action exited {code}")
    return entry


def replays(reg: Registration) -> list[ReplayEntry]:
    """Replay every accepted action but this one, which would replay itself."""
    return [replay_action(action) for action in sorted(reg["choices"]) if action != ACTION]


def report(root: Path, *, replay: bool = False) -> dict[str, Any]:
    """The manifest receipt: the inventory, its completeness and any replayed verdicts."""
    reg = registration()
    items = inventory(root, reg)
    prose = texts(root, items)
    rows = classification(root)
    ran = replays(reg) if replay else []
    errors = (_index_findings(items) + _module_findings(items, reg, prose)
              + _document_findings(root, items, prose) + _test_findings(root, items)
              + _proof_findings(root, items) + _classification_findings(items, rows)
              + _replay_findings(ran))
    if ACTION not in reg["choices"]:
        errors.append(f"{GENERATOR}: the command registers no '{ACTION}' action, so this "
                      "manifest is not reachable from the command it inventories")
    return {
        "schema": VERSION,
        "generator": GENERATOR,
        "scope": "a computed inventory of local research artifacts and their completeness; "
                 "no research claim, optimality result, theorem or target measurement is "
                 "decided by a green manifest",
        "settings": {
            "replay": replay,
            "replay_settings": {action: list(settings)
                                for action, settings in REPLAY_SETTINGS.items()},
            "self_excluded_from_replay": ACTION,
            "receipt_digest_scope": "the receipt bytes one replay produced; an action that "
                                    "records host elapsed time does not repeat its digest",
        },
        "result_classes": list(CLASSES),
        "inventory": items,
        "classification": rows,
        "replays": ran,
        "errors": errors,
        "open_obligations": [
            "external review and publication of the definitions, proofs and generators",
            "a mechanized theorem for each argument the documents state in prose",
            "licence review at the milestone that would incorporate any new dependency",
            "a measured comparison on the actual composed roster and product limits",
        ],
    }
