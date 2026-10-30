# SPDX-License-Identifier: Apache-2.0
"""Authored licence-review identities and their generated development-tool view."""

import codecs
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, cast

from jsonschema.exceptions import SchemaError
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

from vos import yamlutil
from vos.jsonutil import unique_object
from vos.pyversion import supported_minor
from vos.report import apart
from vos.schema import strict_integer_validator

DATA = "tools/development-tools.json"
SCHEMA = "tools/development-tools.schema.json"
RECORD = "THIRD-PARTY.md"
HEADING = "### Development tools, contained by use"
BEGIN = "<!-- generated:development-tools -->"
END = "<!-- /generated:development-tools -->"
SNAPSHOTS = "tools/opam/"
HOOK_CONFIG = "model/.pre-commit-config.yaml"
HOOK_CONSTRAINTS = "tools/ci/model-hooks-constraints.txt"
HOOK_BUILD_CONSTRAINTS = "tools/ci/model-hooks-build-constraints.txt"
TABLE = "development_tools_table"
WORKFLOWS = ".github/workflows/"
_USES_RE = re.compile(r"^[ \t]*(?:-[ \t]+)?(?P<key>uses):[ \t]*(.*?)[ \t]*$")
_ACTION_REF_RE = re.compile(
    r"(?P<reference>(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:/[^@\s]+)?@"
    r"(?P<commit>[0-9a-f]{40})) # (?P<release>v\d+\.\d+\.\d+)")


@dataclass(frozen=True)
class Review:
    """An authored edition whose licence evidence remains in the source template."""

    id: str
    tool: str
    subject: str
    reviewed: tuple[str, ...]
    owners: tuple[Owner, ...]


@dataclass(frozen=True)
class Row:
    """A reviewed component's cells, or an explicit decision owned elsewhere."""

    id: str
    tool: str
    license: str
    standing: str
    reviews: tuple[str, ...]
    disposition: str


@dataclass(frozen=True)
class Document:
    reviews: tuple[Review, ...]
    rows: tuple[Row, ...]
    template: Template
    actions: tuple[Action, ...]


@dataclass(frozen=True)
class Action:
    """One reviewed identity generates both the action's row and its licence URLs."""

    repository: str
    release: str
    commit: str
    license: str
    licence_paths: tuple[str, ...]
    description: str
    attribution: str
    notice: str

    def row(self) -> str:
        links = ", ".join(f"[{self.license} {path.rsplit('/', 1)[-1]}]"
                          f"(https://github.com/{self.repository}/blob/{self.commit}/{path})"
                          for path in self.licence_paths)
        attribution = f", {self.attribution}" if self.attribution else ""
        return (f"| {self.repository} | `{self.license}` | {self.description} The reviewed "
                f"{self.release} revision `{self.commit}` has an {links}{attribution}. "
                f"{self.notice} |")


def read(root: Path, indexed: frozenset[str]) -> Document:
    """Read explicit review identities; no value is inferred from installed editions."""
    if not {DATA, SCHEMA} <= indexed:
        raise ValueError("the development-tool review input and schema must both be tracked")
    data = json.loads((root / DATA).read_text(encoding="utf-8"),
                      object_pairs_hook=unique_object)
    schema = json.loads((root / SCHEMA).read_text(encoding="utf-8"),
                        object_pairs_hook=unique_object)
    validator = strict_integer_validator(schema, check_schema=True)
    errors = sorted(validator.iter_errors(data), key=lambda error: error.json_path)
    if errors:
        raise ValueError("; ".join(f"{error.json_path}: {error.message}" for error in errors))
    decoded = cast("dict[str, Any]", data)
    reviews = tuple(Review(row["id"], row["tool"], row["subject"], tuple(row["reviewed"]),
                           tuple(Owner(**owner) for owner in row["owners"]))
                    for row in decoded["reviews"])
    names = [review.id for review in reviews]
    if len(names) != len(set(names)):
        raise ValueError("review identities must be unique")
    rows = tuple(Row(row["id"], row["tool"], row["license"], row["standing"],
                     tuple(row.get("reviews", [])), row.get("disposition", ""))
                 for row in decoded["rows"])
    if len({row.id for row in rows}) != len(rows):
        raise ValueError("development-tool row identities must be unique")
    lines = decoded["template"]
    template = Template("\n".join(lines))
    table_uses = sum(1 for match in Template.pattern.finditer(template.template)
                     if (match.group("named") or match.group("braced")) == TABLE)
    if lines.count("${" + TABLE + "}") != 1 or table_uses != 1:
        raise ValueError("the template needs one standalone development-tool table placeholder")
    if any(line.lstrip().startswith("|") for line in lines):
        raise ValueError("literal table rows are forbidden; declare each tool in rows")
    wanted = {f"{review.id}_{index}" for review in reviews
              for index, _ in enumerate(review.reviewed)}
    keys = {f"{review.id}_{index}": review.id for review in reviews
            for index, _ in enumerate(review.reviewed)}
    used = _identifiers(template.template)
    for row in rows:
        row_keys = set().union(*(_identifiers(cell) for cell in (
            row.tool, row.license, row.standing)))
        referenced = {keys[key] for key in row_keys if key in keys}
        if row_keys - keys.keys() or referenced != set(row.reviews):
            raise ValueError(f"{row.id}'s declared reviews must cover exactly its cell placeholders")
        used.update(row_keys)
    wanted.add(TABLE)
    if wanted != used:
        raise ValueError(f"template/review identities differ: missing {sorted(wanted - used)}, "
                         f"unknown {sorted(used - wanted)}")
    actions = tuple(Action(action["repository"], action["release"], action["commit"],
                           action["license"], tuple(action["licence_paths"]),
                           action["description"], action["attribution"], action["notice"])
                    for action in decoded["actions"])
    repositories = [action.repository for action in actions]
    if len(repositories) != len(set(repositories)):
        raise ValueError("action repository identities must be unique")
    if set(repositories) & {row.tool for row in rows}:
        raise ValueError("action repositories must use structured actions, never separate rows")
    return Document(reviews, rows, template, actions)


def _identifiers(text: str) -> set[str]:
    template = Template(text)
    if not template.is_valid():
        raise ValueError("the development-tool template has an invalid placeholder")
    return set(template.get_identifiers())


def render(document: Document) -> str:
    """Render only authored reviewed values, never the dependency owner's new value."""
    values = {f"{review.id}_{index}": value for review in document.reviews
              for index, value in enumerate(review.reviewed)}
    table = ["| Tool | License | Standing |", "| --- | --- | --- |"]
    table.extend("| " + " | ".join(Template(cell).substitute(values) for cell in (
        row.tool, row.license, row.standing)) + " |" for row in document.rows)
    table.extend(action.row() for action in document.actions)
    values[TABLE] = "\n".join(table)
    return document.template.substitute(values)


def view(text: str, body: str) -> str:
    """Replace one marked generated body without changing any surrounding bytes."""
    opening, closing = BEGIN + "\n", END + "\n"
    if text.count(opening) != 1 or text.count(closing) != 1:
        raise ValueError("the development-tool view needs one opening and closing marker")
    before, remainder = text.split(opening)
    _old, after = remainder.split(closing)
    if not before.endswith(HEADING + "\n"):
        raise ValueError("the development-tool view must immediately follow its heading")
    return before + opening + body + closing + after


def inspect(root: Path, indexed: frozenset[str], text: str) -> tuple[str | None, list[str]]:
    """Bind every authored reviewed edition to its owners and compute the current view."""
    try:
        document = read(root, indexed)
        expected = view(text, render(document))
    except (OSError, ValueError, TypeError, KeyError, SchemaError) as error:
        return None, [f"development-tool review input is unreadable: {error}"]
    findings: list[str] = []
    owners = Owners(root, indexed)
    for review in document.reviews:
        fixed: set[str] = set()
        try:
            for owner in review.owners:
                fixed.update(owners.releases(owner))
        except OwnerError:
            continue
        if fixed != set(review.reviewed):
            findings.append(f"{review.tool}'s {review.subject}: reviewed "
                            f"{', '.join(review.reviewed)}, owners fix {', '.join(sorted(fixed))}; "
                            "a changed edition needs a licence reading, never an automatic update")
    _hook_census(owners, document.reviews, findings)
    _pip_census(owners, document.reviews, findings)
    _action_census(owners, document.actions, findings)
    findings.extend(owners.faults.values())
    return expected, findings


def _action_census(owners: Owners, actions: tuple[Action, ...], findings: list[str]) -> None:
    """Every real workflow reference matches a review, and every review is used."""
    reviewed = {action.repository: action for action in actions}
    files = sorted(path for path in owners.indexed
                   if path.startswith(WORKFLOWS) and path.endswith((".yml", ".yaml")))
    if not files:
        findings.append(f"the index carries no workflow under {WORKFLOWS}")
        return
    used: set[str] = set()
    references = 0
    unread = False
    for path in files:
        try:
            source = owners._text(path)
        except OwnerError:
            unread = True
            continue
        try:
            tree = yamlutil.read(source)
        except ValueError as error:
            findings.append(f"{path}: cannot read action references: {error}")
            unread = True
            continue
        source_lines = yamlutil.lines(source)
        for mapping in yamlutil.mappings(tree):
            for key, value in mapping.value:
                if key.value != "uses":
                    continue
                references += 1
                mark = yamlutil.start(key)
                where = f"{path}:{mark.line + 1}"
                line = _USES_RE.fullmatch(source_lines[mark.line])
                if line is None or line.start("key") != mark.column:
                    findings.append(f"{where}: action reference needs a bare block `uses:` key")
                    unread = True
                    continue
                pin = _ACTION_REF_RE.fullmatch(line.group(2))
                if pin is None:
                    findings.append(f"{where}: action reference must be "
                                    "owner/repo[/path]@<full commit> # vX.Y.Z")
                    unread = True
                    continue
                if (not isinstance(value, ScalarNode) or value.value != pin.group("reference")
                        or yamlutil.start(value).line != mark.line or value.end_mark is None
                        or value.end_mark.line != mark.line):
                    findings.append(f"{where}: parsed action reference must equal its single-line pin")
                    unread = True
                    continue
                repository, commit, release = pin.group("repository", "commit", "release")
                used.add(repository)
                if repository not in reviewed:
                    findings.append(f"{where}: runs {repository} with no structured action review")
                    continue
                action = reviewed[repository]
                if (commit, release) != (action.commit, action.release):
                    ran, wanted = apart(commit, action.commit)
                    findings.append(f"{where}: runs {repository} at {ran} ({release}); "
                                    f"reviewed {wanted} ({action.release}); "
                                    "a changed identity needs a licence reading")
    if not references and not unread:
        findings.append(f"no workflow under {WORKFLOWS} states an action reference")
    if references and not unread:
        findings.extend(f"{repository} has a review but no workflow runs it"
                        for repository in reviewed if repository not in used)


@dataclass(frozen=True)
class Owner:
    """An artifact here that fixes a release, and which entry of it does.

    `uv` is a package of a uv lock, `uv-required` the uv release a project requires,
    `opam` a package of one exported snapshot, `opam-pin` the commit one exported
    snapshot pins a package's source to, `opam-every` a package every snapshot
    under a directory installs and `opam-any` one some of them do, `assign` a quoted
    top-level assignment, `shell` an unquoted shell variable, `pre-commit` and
    `pre-commit-rev` the release a hook configuration's repository entry names after
    `# frozen:` (its rev when there is no such comment) and that entry's rev itself, and
    `pip` the release a pip requirements or constraints file, read as pip reads it, pins
    a project to with `==`.
    """

    kind: str
    path: str
    key: str

    def label(self) -> str:
        if self.kind == "opam-pin":
            return f"the commit {self.path} pins {self.key} to"
        if self.kind == "opam-every":
            return f"the {self.key} every snapshot under {self.path} installs"
        if self.kind == "opam-any":
            return f"the {self.key} the snapshots under {self.path} install"
        return f"{self.path}'s {self.key}"


_PIP_COMMENT_RE = re.compile(r"(^|\s+)#.*$")


_PIP_CODING_RE = re.compile(r"coding[:=]\s*([-\w.]+)", re.ASCII)


_PIP_NAME = r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"


_PIP_NAME_RE = re.compile(_PIP_NAME)


_PIP_PIN_RE = re.compile(
    rf"(?P<name>{_PIP_NAME})[ \t]*==[ \t]*"
    r"(?P<version>[A-Za-z0-9](?:[A-Za-z0-9._+!-]*[A-Za-z0-9])?)"
    r"(?:[ \t]+--hash=sha256:[0-9a-f]{64})*[ \t]*")


def _project(name: str) -> str:
    """A project's name as pip compares it, in PEP 503's normalized form."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _pip_lines(text: str) -> list[tuple[int, str]]:
    """A pip requirements or constraints file's logical lines as pip reads them, each
    with the number pip gives its first line.

    The text is split at every break `str.splitlines` takes, a form feed, a vertical tab,
    a file, group or record separator and a next-line, line or paragraph separator among
    them. A line ending in `\\` that the comment pattern does not open is joined with the
    next, its backslashes at either end stripped; a comment line ends a join and carries
    its comment into the joined line; the comment is then stripped, and a line left empty
    is no line.
    """
    joined: list[tuple[int, str]] = []
    parts: list[str] = []
    first = 0
    for number, line in enumerate(text.splitlines(), start=1):
        comment = _PIP_COMMENT_RE.match(line) is not None
        if line.endswith("\\") and not comment:
            if not parts:
                first = number
            parts.append(line.strip("\\"))
            continue
        spelled = f" {line}" if comment else line
        if parts:
            joined.append((first, "".join([*parts, spelled])))
            parts = []
        else:
            joined.append((number, spelled))
    if parts:
        joined.append((first, "".join(parts)))
    return [(number, logical) for number, line in joined
            if (logical := _PIP_COMMENT_RE.sub("", line).strip())]


def _utf8(encoding: str) -> bool:
    """Whether an encoding's name names UTF-8, as Python's codec registry resolves it."""
    try:
        return codecs.lookup(encoding).name == "utf-8"
    except LookupError:
        return False


_HOOK_REPO_RE = re.compile(r"^[ \t]*-[ \t]+(?P<key>repo):[ \t]*(?P<url>.*?)[ \t]*$")


_HOOK_REV_LINE_RE = re.compile(
    r"""(?P<indent>[ \t]+)(?P<key>rev):[ \t]*(?P<q>["']?)"""
    r"""(?P<rev>[^\s"'#\\&*!|>%@`{}\[\],?:-][^\s"'#\\]*)(?P=q)"""
    r"""(?:[ \t]+#[ \t]*frozen:[ \t]*(?P<frozen>\S+))?[ \t]*""")


_FULL_COMMIT_RE = re.compile(r"[0-9a-f]{40}")


_HOOK_META = "meta"


def _hook_entries(text: str) -> list[tuple[str, MappingNode]]:
    """Actual hook entries, with canonical repository source lines retained as policy."""
    root = yamlutil.read(text)
    repos = yamlutil.fields(root).get("repos") if isinstance(root, MappingNode) else None
    if not isinstance(repos, SequenceNode):
        raise TypeError("the hook configuration needs a repos sequence")
    lines = yamlutil.lines(text)
    entries: list[tuple[str, MappingNode]] = []
    for entry in repos.value:
        if not isinstance(entry, MappingNode):
            raise TypeError("each hook repository must be a mapping")
        repo = yamlutil.fields(entry).get("repo")
        if not isinstance(repo, ScalarNode) or not repo.value:
            raise ValueError("each hook repository needs a nonempty repo string")
        source = _HOOK_REPO_RE.fullmatch(lines[yamlutil.start(repo).line])
        if source is None or source.group("url").strip("\"'") != repo.value:
            raise ValueError(f"line {yamlutil.start(repo).line + 1}: write the repository "
                             "as a block `- repo:` line")
        entries.append((repo.value, entry))
    return entries


class OwnerError(Exception):
    """An owner K-118 cannot read; its message is already among the reader's faults."""


def _lock_packages(packages: object) -> dict[str, list[str]]:
    """A uv lock's `[[package]]` array as each name's releases, or a TypeError."""
    if not isinstance(packages, list):
        raise TypeError("its package key is not an array of tables")
    table: dict[str, list[str]] = {}
    for package in cast("list[object]", packages):
        entry = cast("dict[str, object]", package) if isinstance(package, dict) else {}
        name, version = entry.get("name"), entry.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise TypeError("a package entry states no name and version")
        table.setdefault(name, []).append(version)
    return table


class Owners:
    """Each owner's releases, every file read once and every fault reported once.

    A fault is keyed by what failed, a file or one entry of it, so an unreadable lock
    is one finding however many rows it owns rather than one per row.
    """

    def __init__(self, root: Path, indexed: frozenset[str]) -> None:
        self.root = root
        self.indexed = indexed
        self.faults: dict[str, str] = {}
        self._texts: dict[str, str | None] = {}
        self._uv: dict[str, dict[str, list[str]]] = {}
        self._opam: dict[str, dict[str, list[str]]] = {}
        self._pips: dict[str, list[tuple[int, str, re.Match[str] | None]]] = {}
        self._pins: dict[str, dict[str, list[str]]] = {}
        self._hook_configs: dict[str, list[tuple[str, MappingNode]]] = {}

    def _fault(self, key: str, message: str) -> OwnerError:
        self.faults.setdefault(key, message)
        return OwnerError(message)

    def _text(self, path: str) -> str:
        if path not in self._texts:
            text: str | None = None
            if path in self.indexed:
                try:
                    text = (self.root / path).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    text = None
            self._texts[path] = text
        text = self._texts[path]
        if text is None:
            raise self._fault(path, f"{path} is not in the repository or does not read as "
                              "text, so the releases it fixes are unread")
        return text

    def _uv_lock(self, path: str) -> dict[str, list[str]]:
        if path not in self._uv:
            text = self._text(path)
            try:
                self._uv[path] = _lock_packages(tomllib.loads(text)["package"])
            except (ValueError, TypeError, KeyError) as err:
                raise self._fault(path, f"{path} cannot supply its resolved releases: "
                                  f"{err}") from None
        return self._uv[path]

    def _snapshot(self, path: str) -> dict[str, list[str]]:
        if path not in self._opam:
            block = re.search(r"^installed:\s*\[(.*?)\]", self._text(path),
                              re.MULTILINE | re.DOTALL)
            if block is None:
                raise self._fault(path, f"{path} carries no installed closure, so the "
                                  "releases it fixes are unread")
            table: dict[str, list[str]] = {}
            for entry in re.findall(r'"([^"\r\n]*)"', block.group(1)):
                name, dot, version = entry.partition(".")
                if not (name and dot and version):
                    raise self._fault(path, f"{path} installs {entry!r}, which is not "
                                      "name.version")
                table.setdefault(name, []).append(version)
            self._opam[path] = table
        return self._opam[path]

    def _pip(self, path: str) -> list[tuple[int, str, re.Match[str] | None]]:
        """A pip constraints file's logical lines as `_pip_lines` reads them, each with its
        line's number and its reading as one pin, or None where it is no pin.

        pip decodes the file by its byte-order mark, which it strips, or failing one by a
        coding declaration among its first two lines; the text here is read as UTF-8, so
        a declaration naming another encoding leaves the file unread.
        """
        if path not in self._pips:
            text = self._text(path)
            if text.startswith("\ufeff"):
                text = text[1:]
            else:
                for line in text.split("\n")[:2]:
                    declared = _PIP_CODING_RE.search(line) if line.startswith("#") else None
                    if declared is not None and not _utf8(declared.group(1)):
                        raise self._fault(path, f"{path} declares the {declared.group(1)} "
                                          "encoding, which pip decodes it by, so the pins "
                                          "read here as UTF-8 are not the ones pip reads")
            self._pips[path] = [(number, logical, _PIP_PIN_RE.fullmatch(logical))
                                for number, logical in _pip_lines(text)]
        return self._pips[path]

    def _snapshot_pins(self, path: str) -> dict[str, list[str]]:
        """Each package an exported snapshot carries a definition of, with the commits
        its `url` block's `src` pins it to: `git+URL#commit`, the commit whole."""
        if path not in self._pins:
            table: dict[str, list[str]] = {}
            for block in re.finditer(r'^package "([^"\r\n]+)" \{(.*?)^\}', self._text(path),
                                     re.MULTILINE | re.DOTALL):
                table[block.group(1)] = re.findall(
                    r'\bsrc:\s*"git\+[^"#\s]+#([0-9a-f]{40})"', block.group(2))
            self._pins[path] = table
        return self._pins[path]

    def _snapshots(self) -> list[str]:
        found = sorted(rel for rel in self.indexed
                       if rel.startswith(SNAPSHOTS) and rel.endswith(".lock"))
        if not found:
            raise self._fault(SNAPSHOTS, f"the index carries no exported snapshot under "
                              f"{SNAPSHOTS}, so no switch's release can be read")
        return found

    def _one(self, owner: Owner, versions: list[str]) -> frozenset[str]:
        if len(versions) != 1:
            raise self._fault(owner.label(), f"{owner.label()} is stated {len(versions)} "
                              "times, so it fixes no one release")
        return frozenset(versions)

    def releases(self, owner: Owner) -> frozenset[str]:
        """What the owner fixes, or `OwnerError` once its fault is recorded."""
        if owner.kind == "python":
            if owner.path != "tools/pyproject.toml" or owner.key != "project.requires-python":
                raise self._fault(owner.label(), "the Python minor must use project.requires-python")
            self._text(owner.path)
            try:
                return frozenset({supported_minor(self.root)})
            except (OSError, ValueError) as error:
                raise self._fault(owner.label(), str(error)) from None
        if owner.kind == "uv":
            return self._one(owner, self._uv_lock(owner.path).get(owner.key, []))
        if owner.kind == "opam":
            return self._one(owner, self._snapshot(owner.path).get(owner.key, []))
        if owner.kind == "opam-pin":
            return self._one(owner, self._snapshot_pins(owner.path).get(owner.key, []))
        if owner.kind in ("opam-every", "opam-any"):
            if owner.path != SNAPSHOTS:
                raise self._fault(owner.label(), f"snapshot inventories must use {SNAPSHOTS}")
            found: set[str] = set()
            for path in self._snapshots():
                versions = self._snapshot(path).get(owner.key, [])
                if versions or owner.kind == "opam-every":
                    found |= self._one(Owner("opam", path, owner.key), versions)
            if not found:
                raise self._fault(owner.label(), f"no snapshot under {owner.path} installs "
                                  f"{owner.key}")
            return frozenset(found)
        if owner.kind == "uv-required":
            if owner.key != "tool.uv.required-version":
                raise self._fault(owner.label(), "uv release owners must use tool.uv.required-version")
            try:
                required: object = tomllib.loads(self._text(owner.path))["tool"]["uv"][
                    "required-version"]
            except (ValueError, TypeError, KeyError) as err:
                raise self._fault(owner.label(), f"{owner.label()} cannot be read: "
                                  f"{err}") from None
            spelled = required if isinstance(required, str) else ""
            exact = re.fullmatch(r"==\s*([^,\s]+)", spelled)
            if exact is None:
                raise self._fault(owner.label(), f"{owner.label()} is {required!r}, which "
                                  "requires no one exact release")
            return frozenset({str(exact.group(1))})
        if owner.kind in ("assign", "shell"):
            key = re.escape(owner.key)
            spelled = (rf'(?m)^{key} = "([^"\r\n]*)"' if owner.kind == "assign"
                       else rf"(?m)^{key}=([^\s'\"#;]+)[ \t]*$")
            return self._one(owner, re.findall(spelled, self._text(owner.path)))
        if owner.kind == "pip":
            # Every logical line opening with the project's name, however it is spelled,
            # is read, so a second pin or a line constraining it other than to one release
            # is a fault rather than a release read loosely.
            versions: list[str] = []
            for _, logical, pin in self._pip(owner.path):
                lead = _PIP_NAME_RE.match(logical)
                if lead is None or _project(lead.group()) != _project(owner.key):
                    continue
                if pin is None:
                    raise self._fault(owner.label(), f"{owner.label()} is constrained other "
                                      "than to one `==` release, so it fixes no one release")
                versions.append(str(pin.group("version")))
            return self._one(owner, versions)
        if owner.kind in ("pre-commit", "pre-commit-rev"):
            rev, frozen = self._hook_rev(owner)
            if owner.kind == "pre-commit-rev":
                return frozenset({rev})
            return frozenset({(frozen or rev).removeprefix("v")})
        raise self._fault(owner.label(), f"{owner.label()} is of the unknown kind "
                          f"{owner.kind!r}")

    def _hooks(self, path: str) -> list[tuple[str, MappingNode]]:
        if path not in self._hook_configs:
            try:
                self._hook_configs[path] = _hook_entries(self._text(path))
            except (TypeError, ValueError) as error:
                raise self._fault(path, f"{path} cannot supply its hook repositories: "
                                  f"{error}") from None
        return self._hook_configs[path]

    def _hook_rev(self, owner: Owner) -> tuple[str, str]:
        """Read the actual entry's revision, preserving the frozen source-line policy."""
        named = [entry for repo, entry in self._hooks(owner.path) if repo == owner.key]
        if len(named) != 1:
            raise self._fault(owner.label(), f"{owner.label()}'s repository is stated "
                              f"{len(named)} times, so it fixes no one revision")
        values = yamlutil.fields(named[0])
        repo, rev = values["repo"], values.get("rev")
        lines = yamlutil.lines(self._text(owner.path))
        repo_line = _HOOK_REPO_RE.fullmatch(lines[yamlutil.start(repo).line])
        read = (_HOOK_REV_LINE_RE.fullmatch(lines[yamlutil.start(rev).line])
                if isinstance(rev, ScalarNode) else None)
        if (read is None or repo_line is None or read.start("key") != repo_line.start("key")
                or not isinstance(rev, ScalarNode) or read.group("rev") != rev.value):
            raise self._fault(owner.label(), f"{owner.label()} needs one `rev: <value>` line "
                              "at its repo key's column, carrying at most its `# frozen:` tag")
        return str(read.group("rev")), str(read.group("frozen") or "")


def _hook_census(owners: Owners, reviews: tuple[Review, ...], findings: list[str]) -> int:
    """Every parsed repository is meta or a reviewed remote; local hooks refuse."""
    try:
        entries = owners._hooks(HOOK_CONFIG)
    except OwnerError:
        return 0
    named = {owner.key for review in reviews for owner in review.owners
             if owner.kind in ("pre-commit", "pre-commit-rev") and owner.path == HOOK_CONFIG}
    for url, entry in entries:
        where = f"{HOOK_CONFIG}:{yamlutil.start(entry).line + 1}"
        if url == _HOOK_META or url in named:
            continue
        if url == "local":
            findings.append(f"{where} is a local hook repository, whose hooks run an entry on "
                            "PATH or in this repository and install their additional "
                            "dependencies from a registry, which no row reviews and no rev pins")
            continue
        try:
            rev, frozen = owners._hook_rev(Owner("pre-commit-rev", HOOK_CONFIG, url))
        except OwnerError:
            continue
        unpinned = ("" if _FULL_COMMIT_RE.fullmatch(rev) and frozen else
                    f", at `{rev}`, which is not a full commit with the `# frozen:` tag it "
                    "was read at either")
        findings.append(f"{where} runs hooks from {url}, which no development-tools row K-118 "
                        f"holds names, so nobody read the terms of the code it installs"
                        f"{unpinned}")
    return len(entries)


def _pip_census(owners: Owners, reviews: tuple[Review, ...], findings: list[str]) -> int:
    """K-118's census of the hook step's pip constraint files, returning how many pins it
    read: each file is read as pip reads it, and each of its logical lines is one pin of a
    project a held row's site reads in that file.

    A row holds the releases it read against these pins, so a pin added for a package a
    hook gained installs a release whose terms nobody read while every row agrees, and a
    line in any other form, an option such as `-c`, `-r` or `--index-url`, a marker,
    extras, a URL or a looser constraint, changes what pip installs while no reading
    here takes it; each is a finding at its first line. Both files are read whether or
    not any row holds a pin in them.
    """
    held: dict[str, set[str]] = {HOOK_CONSTRAINTS: set(), HOOK_BUILD_CONSTRAINTS: set()}
    for review in reviews:
        for owner in review.owners:
            if owner.kind == "pip" and owner.path in held:
                held[owner.path].add(_project(owner.key))
    pinned = 0
    for path, projects in held.items():
        try:
            lines = owners._pip(path)
        except OwnerError:
            continue
        for number, logical, pin in lines:
            where = f"{path}:{number}"
            if pin is None:
                findings.append(f"{where} states `{logical}`, which K-118 does not read as "
                                "one pin; write each line as `<name>==<release>` with at "
                                "most its `--hash=sha256:` digests, since an option, a "
                                "marker, extras, a URL or a looser constraint changes what "
                                "pip installs unread")
                continue
            pinned += 1
            if _project(pin.group("name")) not in projects:
                findings.append(f"{where} pins {pin.group('name')}, which no "
                                "development-tools row K-118 holds reads there, so nobody "
                                "read the terms of the release pip installs")
    return pinned
