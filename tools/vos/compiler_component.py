# SPDX-License-Identifier: Apache-2.0
"""Ordered observations for the reference Gallina/authored-C comparison."""

import hashlib
import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    values: tuple[bool, ...]
    first_failure: int


def families(source: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Read the closed cons/app vocabulary of the actual Gallina check owner."""
    source = re.sub(r"\(\*.*?\*\)", "", source, flags=re.DOTALL)
    rows = re.findall(r"Definition\s+(\w+_checks)\s*:\s*list bool\s*:=\s*(.*?)\.", source, re.DOTALL)
    definitions = dict(rows)
    if len(definitions) != len(rows):
        raise ValueError("duplicate check-family definition")
    if "ipc_checks" not in definitions:
        raise ValueError("missing IPC population owner")
    groups = re.findall(r"\b\w+_checks\b", definitions["ipc_checks"])
    if len(groups) != len(set(groups)) or set(groups) != set(definitions) - {"ipc_checks"}:
        raise ValueError("missing or duplicate check family")
    if re.sub(r"\b(?:app|\w+_checks)\b|[()\s]", "", definitions["ipc_checks"]):
        raise ValueError("unsupported IPC population expression")
    result: list[tuple[str, tuple[str, ...]]] = []
    for group in groups:
        body = definitions[group]
        checks = re.findall(r"\bc_\w+\b", body)
        if not checks or re.sub(r"\b(?:cons|nil|c_\w+)\b|[()\s]", "", body):
            raise ValueError(f"unsupported check family: {group}")
        result.append((group, tuple(checks)))
    identities = [name for _, checks in result for name in checks]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicated check identity")
    return tuple(result)


def population(source: str) -> tuple[str, ...]:
    return tuple(name for _, checks in families(source) for name in checks)


def encode(ids: tuple[str, ...], values: tuple[bool, ...], first: int) -> str:
    if len(ids) != len(values):
        raise ValueError("observation population length differs")
    return json.dumps({"schema": "vos-component-vector/1",
                       "checks": [[name, value] for name, value in zip(ids, values, strict=True)],
                       "first_failure": first}, separators=(",", ":"))


def decode(text: str, ids: tuple[str, ...]) -> Observation:
    """Reject malformed, incomplete and reordered records before comparison."""
    raw = json.loads(text)
    if (not isinstance(raw, dict) or set(raw) != {"schema", "checks", "first_failure"}
            or raw["schema"] != "vos-component-vector/1"):
        raise ValueError("unsupported component observation")
    checks = raw["checks"]
    if not isinstance(checks, list) or len(checks) != len(ids) or not ids:
        raise ValueError("component population length differs")
    values: list[bool] = []
    for i, (row, name) in enumerate(zip(checks, ids, strict=True), 1):
        if not isinstance(row, list) or len(row) != 2 or row[0] != name:
            raise ValueError(f"component identity/order differs at {i}")
        if type(row[1]) is not bool:
            raise ValueError(f"non-Boolean observation at {i}")
        values.append(row[1])
    first = next((i for i, value in enumerate(values, 1) if not value), 0)
    if type(raw["first_failure"]) is not int or raw["first_failure"] != first:
        raise ValueError("first failure disagrees with complete vector")
    return Observation(tuple(values), first)


def installed(export: str) -> tuple[str, ...]:
    """The packages an opam switch export's `installed:` list names, sorted.

    A switch imported from a snapshot re-exports without the snapshot's `compiler:`
    section until its invariant is set (F-496), so the installed list, which both keep,
    is what a switch and a snapshot are compared by."""
    listed = re.search(r"^installed:\s*\[(.*?)^\]", export, re.MULTILINE | re.DOTALL)
    if listed is None:
        raise ValueError("the switch export has no installed list")
    names = [str(found) for found in re.findall(r'"([^"]+)"', listed.group(1))]
    if not names or len(names) != len(set(names)):
        raise ValueError("the switch export's installed list is empty or repeats a package")
    return tuple(sorted(names))


_OPAM_TOKEN = re.compile(
    r'(?P<space>\s+)|(?P<comment>\#[^\r\n]*)'
    r'|(?P<string>"""(?:\\[\s\S]|(?!""")[\s\S])*"""|"(?:\\[\s\S]|[^"\\])*")'
    r'|(?P<token>[\[\]{}():]|[^\s"#\[\]{}():]+)')


def package_recipe(export: str, package: str) -> tuple[str, ...]:
    """Read one complete frozen package recipe, ignoring only comments and spacing.

    Full opam exports retain source URLs, checksums, extra sources and patch/build
    commands even when installed package versions alone cannot distinguish a backport.
    Keep every string byte and token so a changed recipe cannot gain that identity.
    """
    tokens: list[str] = []
    position = 0
    while position < len(export):
        found = _OPAM_TOKEN.match(export, position)
        if found is None:
            raise ValueError("malformed frozen opam package metadata")
        if found.lastgroup not in ("space", "comment"):
            tokens.append(found.group())
        position = found.end()
    stack: list[str] = []
    recipes: list[tuple[str, ...]] = []
    start: int | None = None
    for index, word in enumerate(tokens):
        if not stack and word == "package":
            if index + 2 >= len(tokens) or tokens[index + 2] != "{":
                raise ValueError("malformed frozen opam package declaration")
            if tokens[index + 1] == f'"{package}"':
                start = index
        if word in ("[", "{", "("):
            stack.append(word)
        elif word in ("]", "}", ")"):
            if not stack or stack.pop() != {"]": "[", "}": "{", ")": "("}[word]:
                raise ValueError("unbalanced frozen opam package metadata")
            if not stack and start is not None:
                recipes.append(tuple(tokens[start:index + 1]))
                start = None
    if stack or len(recipes) != 1:
        raise ValueError(f"the export must contain exactly one frozen {package} recipe")
    return recipes[0]


def legacy_oracle_snapshot(snapshot: str) -> bool:
    """Recognize only the qualified version-only snapshot preceding the backport.

    Its historical recognition checks installed versions. Every other snapshot
    must carry a full frozen recipe; deleting metadata cannot select this exception.
    """
    return hashlib.sha256(snapshot.encode("utf-8")).hexdigest() == (
        "8437b97944f4dcc666d2df1f2ed4db67221bf23be3efbc3ce1b483b70c04f3b1")


def matches_oracle_snapshot(export: str, snapshot: str) -> bool:
    """Check versions and frozen provenance, retaining the exact legacy snapshot."""
    return (installed(export) == installed(snapshot)
            and (legacy_oracle_snapshot(snapshot)
                 or package_recipe(export, "rocq-certirocq")
                 == package_recipe(snapshot, "rocq-certirocq")))


def _recipe_without_identity(recipe: tuple[str, ...], package: str, version: str, *,
                             exported: bool) -> tuple[str, ...]:
    """Check optional installed name/version fields and omit export-added identity."""
    body = recipe[3:-1]
    result: list[str] = []
    seen: set[str] = set()
    depth = 0
    index = 0
    while index < len(body):
        word = body[index]
        if depth == 0 and word in ("name", "version"):
            value = package if word == "name" else version
            if (word in seen or body[index + 1:index + 3] != (":", f'"{value}"')):
                raise ValueError(f"conflicting or repeated installed package {word}")
            seen.add(word)
            index += 3
            continue
        if word in ("[", "{", "("):
            depth += 1
        elif word in ("]", "}", ")"):
            depth -= 1
        result.append(word)
        index += 1
    if exported and "version" not in seen:
        raise ValueError("the frozen oracle recipe has no expected package version")
    return tuple(result)


def matches_installed_oracle(metadata: str, snapshot: str, version: str) -> bool:
    """Check last-installed metadata, which a changed pin overlay cannot replace.

    An export reads pinned packages from their current overlay even before a
    rebuild. The installed record instead belongs to the completed installation.
    Its directory supplies the known version; opam may also retain name/version
    fields there, while full exports always add the package version.
    """
    package = "rocq-certirocq"
    actual = package_recipe(f'package "{package}" {{\n{metadata}\n}}\n', package)
    body = _recipe_without_identity(actual, package, version, exported=False)
    if legacy_oracle_snapshot(snapshot):
        return bool(body) and f"{package}.{version}" in installed(snapshot)
    expected = package_recipe(snapshot, package)
    return body == _recipe_without_identity(expected, package, version, exported=True)


def reports_release(version: str, release: str) -> bool:
    """Whether a prover's `--version` output reports exactly that release, not a later
    one it prefixes or a development build of it."""
    return re.search(rf"\bversion {re.escape(release)}(?![\w+~-]|\.\w)", version) is not None


def compare(left: Observation, right: Observation) -> None:
    if len(left.values) != len(right.values):
        raise ValueError("component vector lengths differ")
    for i, (a, b) in enumerate(zip(left.values, right.values, strict=True), 1):
        if a != b:
            raise ValueError(f"component value differs at {i}")
    if left.first_failure != right.first_failure:
        raise ValueError("component first failures differ")


def wrappers(gallina: str, c_source: str) -> tuple[str, str, tuple[str, ...]]:
    """Expose existing outputs without replacing a check or its implementation."""
    grouped = families(gallina)
    ids = tuple(name for _, checks in grouped for name in checks)
    old = "CertiRocq Compile Wasm ipc_oracle."
    if gallina.count(old) != 1:
        raise ValueError("missing or ambiguous Wasm observation boundary")
    observed_gallina = gallina.replace(old, "CertiRocq Compile Wasm ipc_checks.")
    if c_source.count("int main(void)") != 1:
        raise ValueError("missing or ambiguous C observation boundary")
    main = c_source.split("int main(void)", 1)[1]
    calls = re.findall(r"n\s*=\s*n\s*\+\s*(\w+_checks)\(checks\s*\+\s*n\);", main)
    if calls != [group for group, _ in grouped]:
        raise ValueError("C family order differs from Gallina population")
    bodies = dict(re.findall(r"static long (\w+_checks)\(long \*c\)\s*\{(.*?)(?=\nstatic long |\nint main|\Z)",
                             c_source, re.DOTALL))
    if set(bodies) != set(calls) or any(len(re.findall(r"\bn\s*\+\+", bodies[group])) != len(checks)
                                      for group, checks in grouped):
        raise ValueError("C family population differs from Gallina owner")
    count = re.findall(r"(?m)^#define CHECKS (\d+)\s*$", c_source)
    if count != [str(len(ids))]:
        raise ValueError("C population differs from Gallina owner")
    boundary = "    if (n != CHECKS)\n        return 255;\n"
    if c_source.count(boundary) != 1:
        raise ValueError("missing or ambiguous complete C population check")
    observed_c = c_source.replace("int main(void)", "int main(long *observed)")
    observed_c = observed_c.replace(boundary, boundary +
        "    for (k = 0; k < n; k++)\n        observed[k] = checks[k];\n"
        "    observed[n] = n;\n")
    return observed_gallina, observed_c, ids
