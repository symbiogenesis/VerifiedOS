# SPDX-License-Identifier: Apache-2.0
"""Parse the Sail documentation bundle (`tools/generated/sail_riscv_model.json`) and supplemental source identity.

The bundle (`version == 1`, `embedding == "plain"`) records Sail declarations
(`functions`, `mappings`, `vals`, `types`, `registers`, `lets`) with `{contents, file, loc}`
slots (`loc` is `[start_line, start_bol, start_char, end_line, end_bol, end_char]` in UTF-8
byte offsets) and an incomplete MD5 map of input files.

Because the bundle omits a `git` key and omits some project sources from its MD5 map,
`tools/generated/sail_riscv_sources.json` binds the bundle SHA-256, `riscv.sail_project`,
and all project-selected `.sail` sources. `canonicalize_library` rewrites absolute switch
library paths under `share/sail/` to `LIBRARY_PREFIX`.
"""

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, override

from vos import env, rocqterm
from vos.jsonutil import unique_object

BUNDLE_NAME = "sail_riscv_model.json"
BUNDLE = f"tools/generated/{BUNDLE_NAME}"

SOURCE_IDENTITY_NAME = "sail_riscv_sources.json"
SOURCE_IDENTITY = f"tools/generated/{SOURCE_IDENTITY_NAME}"
SOURCE_IDENTITY_FORMAT = "verifiedos-sail-sources-1"

SOURCE_ROOT = "model/model"
PROJECT_FILE = f"{SOURCE_ROOT}/riscv.sail_project"

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_RESERVED = frozenset(("CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                       *(f"{prefix}{digit}" for prefix in ("COM", "LPT")
                         for digit in "123456789¹²³")))

VERSION = 1

DECLARATION_KINDS = (("functions", "function"), ("mappings", "mapping"),
                     ("vals", "val"), ("types", "type"),
                     ("registers", "register"), ("lets", "let"))
type Location = tuple[int, int, int, int, int, int]

LIBRARY_PREFIX = f"/root/.opam/{env.SAIL_SWITCH}/share/sail/"

# Files compiled into Sail itself (`files __virtual corelib.sail`) rather than read from disk.
COMPILER_FILES = frozenset({"corelib.sail"})

_TOP_LEVEL = ("version", "embedding", "hashes", "functions", "mappings", "vals",
              "types", "registers", "lets", "anchors", "spans")

OPERAND_SEP = "spc"
_QUOTED_RE = re.compile(r'^"(.*)"$', re.DOTALL)
_TEXT_LITERAL_RE = re.compile(r'"([^"]*)"')
_ENUM_RE = re.compile(r"^\s*enum\s+\w+\s*=\s*\{(.*)\}\s*$", re.DOTALL)


class BundleError(RuntimeError):
    """Raised when the Sail bundle or source identity is malformed or out of date."""


@dataclass(frozen=True)
class Source:
    """An emitted source slot; generated text has no file or location.

    Location positions are UTF-8 byte offsets, not Python character offsets.
    The six fields are start line, start line offset, start offset, end line,
    end line offset and exclusive end offset.
    """

    contents: str
    file: str | None
    loc: Location | None


@dataclass(frozen=True)
class Declaration:
    """One declaration or scattered clause, retaining its order within the entry."""

    kind: str
    name: str
    clause: int
    source: Source


@dataclass(frozen=True)
class Reference:
    """A compiler-recorded incoming link; this is not a complete call graph."""

    kind: str
    name: str
    target: str
    target_kind: str
    file: str | None
    start: int
    end: int


def _source_slot(raw: object, label: str) -> Source:
    if isinstance(raw, str):
        return Source(raw, None, None)
    if not isinstance(raw, dict):
        raise BundleError(f"{label}: missing or malformed source slot")
    contents, file, loc = raw.get("contents"), raw.get("file"), raw.get("loc")
    if (not isinstance(contents, str) or not isinstance(file, str) or not file
            or not isinstance(loc, list) or len(loc) != 6
            or any(type(value) is not int or value < 0 for value in loc)
            or loc[0] < 1 or loc[3] < loc[0]
            or not loc[1] <= loc[2] <= loc[5] or not loc[1] <= loc[4] <= loc[5]):
        raise BundleError(f"{label}: malformed source contents, file or six-field byte location")
    return Source(contents, file, (loc[0], loc[1], loc[2], loc[3], loc[4], loc[5]))


@dataclass(frozen=True)
class Site:
    """Repository-relative path and 1-based line number of a Sail definition."""

    file: str
    line: int

    @override
    def __str__(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass(frozen=True)
class Spelled:
    """One `mapping clause assembly` and the mnemonics it spells.

    When `exact` is true, `mnemonics` is the cross-product expansion of structured
    right-hand-side patterns (an over-approximation when guards restrict combinations).
    When `exact` is false, `mnemonics` concatenates the clause's literal strings in order
    (an under-approximation).
    """

    ctor: str
    site: Site
    exact: bool
    mnemonics: tuple[str, ...]


@dataclass(frozen=True)
class Decoded:
    """One constructor name reachable from an `encdec*` mapping clause."""

    ctor: str
    site: Site
    mapping: str


def _quoted(value: str) -> str | None:
    """Unquote a Sail string literal, or return `None` if `value` is not quoted."""
    found = _QUOTED_RE.match(value)
    return str(found.group(1)) if found else None


class Bundle:
    """Parsed Sail documentation bundle.

    Accessors raise `BundleError` when a requested declaration is missing or malformed.
    """

    def __init__(self, raw: dict[str, Any], path: str = BUNDLE) -> None:
        self.path = path
        missing = [key for key in _TOP_LEVEL if key not in raw]
        if missing:
            raise BundleError(
                f"{path} carries no {', '.join(missing)}, so it is not the "
                f"version {VERSION} bundle this reader was written against")
        if raw["version"] != VERSION:
            raise BundleError(
                f"{path} states version {raw['version']!r} and this reader is written "
                f"against version {VERSION}; regenerate it with `run.py model bundle` "
                f"or teach this module the newer shape")
        self.embedding: str = str(raw["embedding"])
        self._raw = raw

    def _map(self, name: str) -> dict[str, Any]:
        got = self._raw[name]
        if not isinstance(got, dict):
            raise BundleError(f"{self.path}'s {name} is a {type(got).__name__} "
                              f"and this reader expects a map")
        return got

    @property
    def hashes(self) -> dict[str, str]:
        """Map each recorded file key to its emitted MD5 digest."""
        out: dict[str, str] = {}
        for key, entry in self._map("hashes").items():
            digest = entry.get("md5") if isinstance(entry, dict) else None
            if not isinstance(digest, str):
                raise BundleError(f"{self.path} records no md5 for {key}")
            out[key] = digest
        return out

    def owners(self) -> dict[str, str]:
        """Return repository-relative paths in the emitter's MD5 map.

        Use `read_source_identity` to check freshness against all project sources.
        """
        return {f"{SOURCE_ROOT}/{key}": digest for key, digest in self.hashes.items()
                if not key.startswith("/") and key not in COMPILER_FILES}

    def compiler_owners(self) -> dict[str, str]:
        """Return virtual compiler-built files (`COMPILER_FILES`) from the MD5 map."""
        return {key: digest for key, digest in self.hashes.items() if key in COMPILER_FILES}

    def library_owners(self) -> dict[str, str]:
        """Return Sail library files keyed by their canonical `LIBRARY_PREFIX` paths."""
        out: dict[str, str] = {}
        for key, digest in self.hashes.items():
            if not key.startswith("/"):
                continue
            if not key.startswith(LIBRARY_PREFIX):
                raise BundleError(
                    f"{self.path} was emitted against {key}, which is outside "
                    f"{LIBRARY_PREFIX}: regenerate with `run.py model bundle` "
                    f"to record the selected library at its canonical location")
            out[key] = digest
        return out

    def _navigation_entries(self) -> Iterator[tuple[str, str, dict[str, Any]]]:
        if self.embedding != "plain" or type(self._raw["version"]) is not int:
            raise BundleError(f"{self.path}: navigation requires version 1 with plain embedding")
        for table, kind in DECLARATION_KINDS:
            for name, entry in self._map(table).items():
                if not isinstance(name, str) or not name or not isinstance(entry, dict):
                    raise BundleError(f"{self.path}: malformed {kind} entry")
                yield kind, name, entry

    def declarations(self) -> list[Declaration]:
        """Read every supported emitted declaration shape without parsing Sail text.

        Generated source strings remain visible as unlocated declarations. Missing
        slots and malformed locations raise instead of silently shrinking the view.
        """
        out: list[Declaration] = []
        for kind, name, entry in self._navigation_entries():
            value = entry.get(kind)
            if kind == "mapping" and not isinstance(value, list):
                raise BundleError(f"{self.path}: mapping {name} must carry a clause list")
            clauses = value if isinstance(value, list) and kind in ("function", "mapping") else [value]
            if not clauses:
                raise BundleError(f"{self.path}: {kind} {name} carries an empty clause list")
            for index, clause in enumerate(clauses):
                slot = (clause if kind == "type" else
                        clause.get("source") if isinstance(clause, dict) else None)
                out.append(Declaration(kind, name, index,
                                       _source_slot(slot, f"{self.path}: {kind} {name}")))
        return out

    def references(self) -> list[Reference]:
        """Compiler links keyed by their containing declaration, with byte locations."""
        out: list[Reference] = []
        for kind, name, entry in self._navigation_entries():
            links = entry.get("links", [])
            if not isinstance(links, list):
                raise BundleError(f"{self.path}: {kind} {name} links must be a list")
            for link in links:
                if not isinstance(link, dict):
                    raise BundleError(f"{self.path}: {kind} {name} has a malformed link")
                target, target_kind = link.get("id"), link.get("type")
                file, loc = link.get("file"), link.get("loc")
                if (not isinstance(target, str) or not target or target_kind not in ("function", "register")
                        or not isinstance(file, str)
                        or not isinstance(loc, list) or len(loc) != 2
                        or any(type(value) is not int or value < 0 for value in loc)
                        or loc[1] < loc[0]):
                    raise BundleError(f"{self.path}: {kind} {name} has malformed link fields")
                out.append(Reference(kind, name, target, target_kind, file or None, loc[0], loc[1]))
        return out

    def _site(self, slot: dict[str, Any]) -> Site:
        file, loc = slot.get("file"), slot.get("loc")
        if not isinstance(file, str) or not isinstance(loc, list) or not loc:
            raise BundleError(f"{self.path} carries a source slot with no file:line, "
                              f"which --doc-embed-with-location is what supplies")
        return Site(f"{SOURCE_ROOT}/{file}", int(loc[0]))

    def type_text(self, name: str) -> str:
        """Return a `type` declaration's source text."""
        entry = self._map("types").get(name)
        if not isinstance(entry, dict) or not isinstance(entry.get("type"), dict):
            raise BundleError(f"the model declares no type {name}")
        return str(entry["type"].get("contents", ""))

    def let_text(self, name: str) -> str:
        """Return a top-level `let` declaration's full source text."""
        entry = self._map("lets").get(name)
        source = entry.get("let", {}).get("source") if isinstance(entry, dict) else None
        if not isinstance(source, dict):
            raise BundleError(f"the model declares no let {name}")
        return str(source.get("contents", ""))

    def let_value(self, name: str) -> str:
        """Return a top-level `let` declaration's right-hand-side expression text."""
        entry = self._map("lets").get(name)
        exp = entry.get("let", {}).get("exp") if isinstance(entry, dict) else None
        if not isinstance(exp, dict):
            raise BundleError(f"the model declares no let {name}")
        return str(exp.get("contents", ""))

    def has(self, kind: str, name: str) -> bool:
        """Return whether `name` exists in map `kind`."""
        return name in self._map(kind)

    def registers(self) -> frozenset[str]:
        """Return all declared register names."""
        return frozenset(self._map("registers"))

    def enum_members(self) -> dict[str, tuple[str, int]]:
        """Map each non-scattered enum member to `(enum_name, declaration_ordinal)`."""
        out: dict[str, tuple[str, int]] = {}
        for name, entry in self._map("types").items():
            slot = entry.get("type") if isinstance(entry, dict) else None
            text = slot.get("contents", "") if isinstance(slot, dict) else ""
            found = _ENUM_RE.match(str(text))
            if not found:
                continue
            members = [part.strip() for part in found.group(1).split(",")]
            for ordinal, member in enumerate(m for m in members if m):
                out[member] = (name, ordinal)
        return out

    def constructor_bodies(self, name: str) -> dict[str, str]:
        """Map constructor names to clause body texts for an `app`-patterned function (such as `execute`)."""
        entry = self._map("functions").get(name)
        found = entry.get("function") if isinstance(entry, dict) else None
        clauses = found if isinstance(found, list) else [found]
        if not isinstance(found, (list, dict)):
            raise BundleError(f"the model declares no function {name}")
        out: dict[str, str] = {}
        for clause in clauses:
            if not isinstance(clause, dict):
                continue
            pattern, body = clause.get("pattern"), clause.get("body")
            if not isinstance(pattern, dict) or not isinstance(body, dict):
                continue
            ident = pattern.get("id")
            if pattern.get("type") == "app" and isinstance(ident, str):
                out[ident] = str(body.get("contents", ""))
        return out

    def scattered_members(self) -> frozenset[str]:
        """Return all single-identifier patterns matched by multi-clause functions (such as `hartSupports`)."""
        out: set[str] = set()
        for name in self._map("functions"):
            clauses = self.function_bodies(name)
            if len(clauses) < 2:
                continue
            out |= {names[0] for names, _body, _site in clauses if len(names) == 1}
        return frozenset(out)

    def clauses(self, name: str) -> list[dict[str, Any]]:
        """Return the raw clause dicts for mapping `name`."""
        return self._clauses(name)

    def function_clauses(self, name: str) -> list[tuple[str, str, Site]]:
        """Return `(pattern_id, body_text, site)` for each clause of function `name`."""
        return [(names[0] if len(names) == 1 else "", body, site)
                for names, body, site in self.function_bodies(name)]

    def function_bodies(self, name: str) -> list[tuple[tuple[str, ...], str, Site]]:
        """Return `(param_names, body_text, site)` for each clause of function `name`."""
        entry = self._map("functions").get(name)
        found = entry.get("function") if isinstance(entry, dict) else None
        clauses = found if isinstance(found, list) else [found]
        if not isinstance(found, (list, dict)):
            raise BundleError(f"the model declares no function {name}")
        out: list[tuple[tuple[str, ...], str, Site]] = []
        for clause in clauses:
            if not isinstance(clause, dict):
                continue
            body = clause.get("body")
            source = clause.get("source")
            names = _names(clause.get("pattern"))
            if names is None or not isinstance(body, dict):
                continue
            out.append((names, str(body.get("contents", "")),
                        self._site(source if isinstance(source, dict) else body)))
        return out

    def mapping_names(self) -> list[str]:
        return sorted(self._map("mappings"))

    def _clauses(self, name: str) -> list[dict[str, Any]]:
        entry = self._map("mappings").get(name)
        clauses = entry.get("mapping") if isinstance(entry, dict) else None
        if not isinstance(clauses, list):
            raise BundleError(f"the model declares no mapping {name}")
        return [c for c in clauses if isinstance(c, dict)]

    def mapping_literals(self, name: str) -> tuple[str, ...] | None:
        """Return the string literals produced by every arm of mapping `name`, or `None` if any arm is non-literal."""
        out: list[str] = []
        for clause in self._clauses(name):
            found = [value for side in ("left", "right")
                     if isinstance(node := clause.get(side), dict)
                     and node.get("type") == "literal"
                     and (value := _quoted(str(node.get("value", "")))) is not None]
            if not found:
                return None
            out.append(found[0])
        return tuple(out) if out else None

    def _expand(self, node: dict[str, Any]) -> tuple[str, ...] | None:
        """Expand a literal or mapping-call pattern node into its string choices, or `None`."""
        kind = node.get("type")
        if kind == "literal":
            value = _quoted(str(node.get("value", "")))
            return None if value is None else (value,)
        if kind == "app":
            ident = node.get("id")
            if isinstance(ident, str) and ident in self._map("mappings"):
                return self.mapping_literals(ident)
        return None

    def assembly(self) -> list[Spelled]:
        """Return `Spelled` records for every `mapping clause assembly`."""
        out: list[Spelled] = []
        for clause in self._clauses("assembly"):
            left = clause.get("left")
            ctor = left.get("id") if isinstance(left, dict) else None
            source = clause.get("source")
            if not isinstance(ctor, str) or not isinstance(source, dict):
                continue
            site = self._site(source)
            right = clause.get("right")
            if isinstance(right, dict):
                spelled = self._spell(right)
                if spelled is not None:
                    out.append(Spelled(ctor, site, exact=True, mnemonics=spelled))
                    continue
            out.append(Spelled(ctor, site, exact=False,
                               mnemonics=self._text_skeleton(clause)))
        return out

    def _spell(self, right: dict[str, Any]) -> tuple[str, ...] | None:
        """Expand the mnemonic patterns before `spc` on a structured `assembly` right-hand side."""
        parts = (right.get("patterns") if right.get("type") == "string_append"
                 else [right])
        if not isinstance(parts, list):
            return None
        options: list[tuple[str, ...]] = []
        for part in parts:
            if not isinstance(part, dict):
                return None
            if part.get("type") == "app" and part.get("id") == OPERAND_SEP:
                break
            expanded = self._expand(part)
            if expanded is None:
                return None
            options.append(expanded)
        if not options:
            return None
        spellings: list[str] = [""]
        for choices in options:
            spellings = [head + tail for head in spellings for tail in choices]
        return tuple(dict.fromkeys(spellings))

    def _text_skeleton(self, clause: dict[str, Any]) -> tuple[str, ...]:
        """Concatenate quoted literals before `spc()` when a clause's right-hand side is unstructured."""
        body = clause.get("body") or clause.get("source")
        text = str(body.get("contents", "")) if isinstance(body, dict) else ""
        head = text.split(f"{OPERAND_SEP}()")[0]
        joined = "".join(str(part) for part in _TEXT_LITERAL_RE.findall(head))
        out: tuple[str, ...] = (joined,) if joined else ()
        return out

    def decoded(self, prefix: str = "encdec") -> list[Decoded]:
        """Return all `app`/`id` names referenced by mappings starting with `prefix`."""
        out: list[Decoded] = []
        for name in self.mapping_names():
            if not name.startswith(prefix):
                continue
            for clause in self._clauses(name):
                source = clause.get("source")
                if not isinstance(source, dict):
                    continue
                site = self._site(source)
                for side in ("left", "right"):
                    node = clause.get(side)
                    if not isinstance(node, dict) or node.get("type") not in ("app", "id"):
                        continue
                    ident = node.get("id")
                    if isinstance(ident, str):
                        out.append(Decoded(ident, site, name))
        return out


def _names(pattern: object) -> tuple[str, ...] | None:
    """Extract parameter names from a unit `()`, `id`, or `tuple` pattern node."""
    if not isinstance(pattern, dict):
        return None
    if pattern.get("type") == "literal" and str(pattern.get("value", "")) == "()":
        return ()
    if pattern.get("type") == "id":
        ident = pattern.get("id")
        return (ident,) if isinstance(ident, str) else None
    if pattern.get("type") == "tuple":
        out: list[str] = []
        for part in pattern.get("patterns", []):
            if not isinstance(part, dict) or part.get("type") != "id":
                return None
            ident = part.get("id")
            if not isinstance(ident, str):
                return None
            out.append(ident)
        return tuple(out)
    return None


def canonicalize_library(data: bytes, library: Path) -> bytes:
    """Relocate only emitted library hash keys; retain all source and digest values."""
    try:
        raw = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"emitted bundle is not readable as JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise BundleError("emitted bundle is not a JSON object")
    bundle = Bundle(raw)
    selected = library.as_posix().rstrip("/") + "/"
    hashes: dict[str, object] = {}
    for key in bundle.hashes:
        canonical = key
        if key.startswith("/"):
            if not key.startswith(selected):
                raise BundleError(f"emitted library {key} is outside selected library {selected}")
            suffix = key.removeprefix(selected)
            if any(part in ("", ".", "..") for part in suffix.split("/")):
                raise BundleError(f"emitted library path escapes its selected root: {key}")
            canonical = LIBRARY_PREFIX + suffix
        hashes[canonical] = raw["hashes"][key]
    raw["hashes"] = hashes
    return (json.dumps(raw, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    return unique_object(pairs, duplicate_error=lambda key: BundleError(f"duplicate JSON object key {key!r}"))


def _json_constant(value: str) -> None:
    raise BundleError(f"non-JSON numeric constant {value}")


def parse(data: bytes, path: str = BUNDLE) -> Bundle:
    """Decode one byte snapshot, rejecting duplicate fields and non-JSON numbers."""
    try:
        raw = json.loads(data.decode("utf-8"), object_pairs_hook=_json_object,
                         parse_constant=_json_constant)
    except (UnicodeError, ValueError, BundleError) as exc:
        raise BundleError(f"{path} is not readable as JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise BundleError(f"{path} is a {type(raw).__name__} and not a bundle")
    return Bundle(raw, path)


def owner_parts(rel: str) -> list[str]:
    """Validate portable path spelling before any owner or source-location lookup."""
    parts = rel.split("/")
    if (not rel or any(part in ("", ".", "..") for part in parts)
            or any(char in rel for char in '\\:<>"|?*')
            or any(ord(char) < 32 or ord(char) == 127 for char in rel)
            or any(part.endswith((" ", ".")) or part.split(".", 1)[0].upper() in _RESERVED
                   for part in parts)):
        raise BundleError(f"unsafe repository-relative path {rel!r}")
    return parts


def owner_path(root: Path, rel: str) -> Path:
    """A portable regular owner path, refusing traversal and link redirection."""
    path = root
    for part in owner_parts(rel):
        path /= part
        if path.is_symlink() or path.is_junction():
            raise BundleError(f"{rel}: symbolic links and junctions are not source owners")
    if not path.resolve().is_relative_to(root.resolve()):
        raise BundleError(f"{rel}: path escapes the checkout")
    if not path.is_file():
        raise BundleError(f"{rel}: missing regular source owner")
    return path


def source_identity(root: Path, listed: list[str], bundle_bytes: bytes) -> bytes:
    """Identify the source list Sail's owning project selects, without changing its bundle.

    Membership comes only from the compiler's project listing. The list is never
    reconstructed from the incomplete MD5 map or a scan of tracked Sail files.
    """
    if not listed or len(set(listed)) != len(listed):
        raise BundleError("the Sail project's source list is empty or carries duplicate paths")
    hashes = {f"{SOURCE_ROOT}/{rel}":
              hashlib.sha256(owner_path(root, f"{SOURCE_ROOT}/{rel}").read_bytes()).hexdigest()
              for rel in listed}
    project = owner_path(root, PROJECT_FILE).read_bytes()
    raw = {
        "format": SOURCE_IDENTITY_FORMAT,
        "bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(),
        "project_file": {"path": PROJECT_FILE, "sha256": hashlib.sha256(project).hexdigest()},
        "sources": rocqterm.manifest(hashes),
    }
    return (json.dumps(raw, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_source_identity(root: Path, bundle_bytes: bytes, *, identity_bytes: bytes | None = None,
                         captured: dict[str, bytes] | None = None) -> dict[str, str]:
    """Check the complete local source identity and return its SHA-256 owners.

    The project bytes bind the source selection recorded by the guest compiler;
    the exact bundle bytes bind its emitted declarations. Host readers verify every
    listed source now, while the guest comparison regenerates the complete selection.
    Optional captured bytes let a context reader return these same checked reads.
    """
    try:
        data = (owner_path(root, SOURCE_IDENTITY).read_bytes()
                if identity_bytes is None else identity_bytes)
        raw = json.loads(data.decode("utf-8"), object_pairs_hook=_json_object,
                         parse_constant=_json_constant)
    except (OSError, UnicodeError, ValueError, BundleError) as exc:
        raise BundleError(f"{SOURCE_IDENTITY} is not readable: {exc}") from exc
    if (not isinstance(raw, dict)
            or set(raw) != {"format", "bundle_sha256", "project_file", "sources"}
            or raw.get("format") != SOURCE_IDENTITY_FORMAT):
        raise BundleError(f"{SOURCE_IDENTITY}: malformed or unsupported source identity")
    bundle_digest = raw["bundle_sha256"]
    if (not isinstance(bundle_digest, str) or not _SHA256_RE.fullmatch(bundle_digest)
            or bundle_digest != hashlib.sha256(bundle_bytes).hexdigest()):
        raise BundleError(f"{SOURCE_IDENTITY}: recorded bundle digest differs from current bytes")
    project = raw["project_file"]
    if (not isinstance(project, dict) or set(project) != {"path", "sha256"}
            or project.get("path") != PROJECT_FILE
            or not isinstance(project.get("sha256"), str)
            or not _SHA256_RE.fullmatch(project["sha256"])):
        raise BundleError(f"{SOURCE_IDENTITY}: malformed project file identity")
    if hashlib.sha256(owner_path(root, PROJECT_FILE).read_bytes()).hexdigest() != project["sha256"]:
        raise BundleError(f"{PROJECT_FILE}: recorded project digest differs from current bytes; "
                          "regenerate and compare the bundle before using its context")
    manifest = raw["sources"]
    if (not isinstance(manifest, dict) or set(manifest) != {"files", "aggregate", "sha256"}
            or not isinstance(manifest.get("sha256"), dict) or not manifest["sha256"]):
        raise BundleError(f"{SOURCE_IDENTITY}: missing or malformed complete source manifest")
    hashes: dict[str, str] = {}
    for rel, digest in manifest["sha256"].items():
        if (not isinstance(rel, str) or not rel.startswith(f"{SOURCE_ROOT}/")
                or not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest)):
            raise BundleError(f"{SOURCE_IDENTITY}: malformed source path or SHA-256")
        owner_path(root, rel)
        hashes[rel] = digest
    if (type(manifest.get("files")) is not int or manifest["files"] != len(hashes)
            or manifest.get("aggregate") != rocqterm.aggregate(hashes)):
        raise BundleError(f"{SOURCE_IDENTITY}: source count or aggregate disagrees with its members")
    bundle = parse(bundle_bytes)
    local = bundle.owners()
    if missing := sorted(set(local) - set(hashes)):
        raise BundleError(f"{SOURCE_IDENTITY}: source manifest omits bundle owners: {', '.join(missing)}")
    checked: dict[str, bytes] = {}
    for rel, expected in hashes.items():
        current = owner_path(root, rel).read_bytes()
        if hashlib.sha256(current).hexdigest() != expected:
            raise BundleError(f"{rel}: recorded owner digest differs from current bytes; "
                              "regenerate and compare the bundle before using its context")
        if rel in local and hashlib.md5(current, usedforsecurity=False).hexdigest() != local[rel]:
            raise BundleError(f"{rel}: bundle MD5 differs from the complete source identity")
        checked[rel] = current
    if captured is not None:
        captured.update(checked)
    return hashes


def load(root: Path, path: str = BUNDLE) -> Bundle | None:
    """The tracked bundle, or `None` where it is not there.

    Absence is the caller's finding to word and not this module's to raise, exactly as
    the other model parses in this package treat a file that has moved. Anything else
    wrong with it raises: a bundle that is there and unreadable is a defect in the
    generated artifact, and a rule that read past it would report about nothing.
    """
    file = root / path
    if not file.is_file():
        return None
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"{path} is not readable as JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise BundleError(f"{path} is a {type(raw).__name__} and not a bundle")
    return Bundle(raw, path)
