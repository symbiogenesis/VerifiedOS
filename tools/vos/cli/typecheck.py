#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the locked Python linters over every indexed tool source.

Both ty platform passes and Ruff receive explicit filenames. Authored JSON
Schemas hold the reviewed configuration policy; the wrapper retains bounded
execution, diagnostic summaries, suppression and platform-import checks.
"""

import argparse
import ast
import importlib.util
import io
import os
import re
import subprocess
import sys
import sysconfig
import tokenize
import tomllib
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NamedTuple

from vos import corpus as corpus_mod
from vos import pyversion, toolenv
from vos.report import Reporter
from vos.schema import validate

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PINS = toolenv.checker_pins(_PROJECT_ROOT)
PYTHON_VERSION = pyversion.supported_minor(_PROJECT_ROOT)
TY_VERSION = _PINS["ty"]
RUFF_VERSION = _PINS["ruff"]

# Both platforms must be typed: each can make different branches unreachable.
TY_PLATFORMS = ("linux", "win32")

# Limit printed examples per rule while retaining the total finding count.
PER_RULE = 8

# Bound every subprocess, including version probes, so a stalled checker is reported.
TIMEOUT = 120

# Stay below CreateProcess's 32,767 UTF-16-code-unit limit, executable and quotes
# included. The same modest command bound is safe on the supported Linux hosts.
COMMAND_LIMIT = 30_000
TY_UNSET = frozenset({"TY_LOG", "TY_LOG_PROFILE"})

# Both checkers must cover every indexed Python source and stub under this prefix.
TOOLS = "tools/"
MODULE_SUFFIXES = (".py", ".pyi")

# Path in `ruff.toml` listing modules banned at module level by TID253.
BANNED = ("lint", "flake8-tidy-imports", "banned-module-level-imports")

# File-level `ruff`/`flake8` `noqa` suppression pattern.
FILE_NOQA = re.compile(r"#\s*(?:ruff|flake8)\s*:\s*(?i:noqa)")
# Rules permitted in a file-level `noqa` (N999 applies to the filename, not individual lines).
FILE_SCOPED = frozenset({"N999"})
# Multi-line or file-wide suppression directives (`ruff: disable/enable/file-ignore`, `isort: skip_file/off/on`).
FILE_RANGE = re.compile(r"#\s*(?:ruff\s*:\s*(?:disable|enable|file-ignore)\b"
                        r"|(?:ruff\s*:\s*)?isort\s*:\s*(?:skip_file|off|on)\b)")


def _tool(name: str) -> str | None:
    """Return the path to `name` in the running interpreter's scripts directory, or `None`."""
    suffix = ".exe" if sys.platform == "win32" else ""
    candidate = Path(sysconfig.get_path("scripts")) / (name + suffix)
    return str(candidate) if candidate.is_file() else None


def _version(exe: str) -> str:
    """Return the version number reported by `exe --version`."""
    done = subprocess.run([exe, "--version"], capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=TIMEOUT)
    parts = (done.stdout.strip() or done.stderr.strip()).split()
    return parts[1] if len(parts) > 1 else "unknown"


def _pinned(rep: Reporter, name: str, pin: str) -> str | None:
    """Verify `name` is installed at version `pin` and return its executable path, or report and return `None`."""
    exe = _tool(name)
    if exe is None:
        rep.report(name, "not installed:",
                   [f"{name} {pin} is not in {sysconfig.get_path('scripts')}: "
                    "rerun python tools/run.py typecheck to synchronize tools/uv.lock"])
        return None
    try:
        found = _version(exe)
    except subprocess.TimeoutExpired:
        rep.report(name, "checker error(s):",
                   [f"{exe} answered no --version within {TIMEOUT}s"])
        return None
    except OSError as err:
        rep.report(name, "checker error(s):", [f"{exe} could not be run: {err}"])
        return None
    if found != pin:
        rep.report(name, "version(s) other than the pinned one:",
                   [f"{name} {found} is installed and this tree pins {pin}: "
                    "rerun python tools/run.py typecheck to synchronize tools/uv.lock"])
        return None
    return exe


def _summarize(rep: Reporter, rule: str, label: str, findings: list[tuple[str, str]],
               ok: str) -> None:
    """Report checker findings grouped by rule code, sampling up to `PER_RULE` sites per rule."""
    if not findings:
        rep.report(rule, label, [], ok)
        return

    by_rule: dict[str, list[str]] = defaultdict(list)
    for code, text in findings:
        by_rule[code].append(text)

    lines = []
    for code in sorted(by_rule, key=lambda c: (-len(by_rule[c]), c)):
        hits = by_rule[code]
        lines.append(f"{code}: {len(hits)}")
        lines.extend(f"  {h}" for h in hits[:PER_RULE])
        if len(hits) > PER_RULE:
            lines.append(f"  ... and {len(hits) - PER_RULE} more")
    rep.report(rule, label, lines, ok, count=len(findings))


def _parse_ty(text: str) -> list[tuple[str, str]]:
    """Parse `ty` concise diagnostic lines (`path:line:col: error[rule-name] message`)."""
    findings: list[tuple[str, str]] = []
    for line in text.splitlines():
        if "] " not in line or (": error[" not in line and ": warning[" not in line):
            continue
        where, _, rest = line.partition(": ")
        code = rest.partition("[")[2].partition("]")[0]
        findings.append((code, f"{where} {rest.partition('] ')[2]}"))
    return findings


def _parse_ruff(text: str) -> list[tuple[str, str]]:
    """Parse `ruff` concise diagnostic lines (`path:line:col: CODE message` or `invalid-syntax:`)."""
    findings: list[tuple[str, str]] = []
    for line in text.splitlines():
        head, _, rest = line.partition(": ")
        code, _, message = rest.partition(" ")
        if code == "invalid-syntax:":
            code = "invalid-syntax"
        elif not code or not code[0].isalpha() or not code[-1].isdigit():
            continue
        if not head:
            continue
        findings.append((code, f"{head} {message}"))
    return findings


class Pass(NamedTuple):
    """A pinned checker invocation, its explicit target files, and its report labels."""
    args: list[str]
    who: str
    label: str
    ok: str
    targets: frozenset[str] | None = None
    unset: frozenset[str] = frozenset[str]()


def _target_commands(exe: str, args: list[str], targets: frozenset[str]) -> Iterator[list[str]]:
    """Batch explicit filenames within `COMMAND_LIMIT` UTF-16 code units."""
    if not targets:
        raise ValueError("the index supplies no Python modules to check")
    base: list[str] = [exe, *args, "--"]
    command: list[str] = base.copy()
    for target in sorted(targets):
        candidate: list[str] = [*command, target]
        if len(subprocess.list2cmdline(candidate).encode("utf-16-le")) > 2 * COMMAND_LIMIT:
            if command == base:
                raise ValueError(f"checker arguments exceed the command limit at {target!r}")
            yield command
            command = base.copy()
            candidate = [*command, target]
            if len(subprocess.list2cmdline(candidate).encode("utf-16-le")) > 2 * COMMAND_LIMIT:
                raise ValueError(f"checker arguments exceed the command limit at {target!r}")
        command = candidate
    yield command


def _run_checker(rep: Reporter, name: str, pin: str, passes: list[Pass], cwd: Path,
                 with_stderr: bool, parse: Callable[[str], list[tuple[str, str]]]) -> None:
    """Verify `name` is at `pin`, then execute and report each `Pass`."""
    exe = _pinned(rep, name, pin)
    if exe is None:
        return
    for run in passes:
        _run_pass(rep, name, exe, run, cwd, with_stderr, parse)


def _run_pass(rep: Reporter, name: str, exe: str, run: Pass, cwd: Path,
              with_stderr: bool, parse: Callable[[str], list[tuple[str, str]]]) -> None:
    """Run all filename batches, preserving findings and refusing every failed batch."""
    if run.targets is not None:
        missing = sorted(target for target in run.targets if not (cwd / target).is_file())
        if missing:
            rep.report(name, "checker input error(s):",
                       [f"{run.who}: {target} is not a regular source file" for target in missing])
            return
    env = None if not run.unset else {
        key: value for key, value in os.environ.items() if key not in run.unset}
    try:
        commands = (list(_target_commands(exe, run.args, run.targets))
                    if run.targets is not None else [[exe, *run.args]])
    except ValueError as err:
        rep.report(name, "checker input error(s):", [f"{run.who}: {err}"])
        return
    findings: list[tuple[str, str]] = []
    failed = False
    for command in commands:
        try:
            done = subprocess.run(command, capture_output=True, encoding="utf-8",
                                  errors="replace", cwd=cwd, env=env, check=False,
                                  timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            rep.report(name, "checker error(s):",
                       [f"{run.who} gave no verdict within {TIMEOUT}s"])
            failed = True
            continue
        except OSError as err:
            rep.report(name, "checker error(s):", [f"{exe} could not be run: {err}"])
            failed = True
            continue
        parsed = parse(done.stdout + done.stderr if with_stderr else done.stdout)
        findings.extend(parsed)
        if done.returncode == 1 and not parsed:
            rep.report(name, "checker error(s):",
                       [f"{run.who} exited 1 but no diagnostic was recognized: "
                        f"{(done.stdout + done.stderr).strip()[:400] or '(no output)'}"])
            failed = True
        elif done.returncode not in (0, 1):
            rep.report(name, "checker error(s):",
                       [f"{run.who} exited {done.returncode}: "
                        f"{(done.stderr or done.stdout).strip()[:400]}"])
            failed = True
    if findings or not failed:
        _summarize(rep, name, run.label, findings, run.ok)


def _settings(config: Path) -> list[str]:
    """Decode TOML and apply its authored policy, retaining refusal beside linting."""
    try:
        settings = tomllib.loads(config.read_text(encoding="utf-8"))
        validate(_PROJECT_ROOT / "tools" / f"{config.stem}-config.schema.json", settings)
    except (OSError, ValueError) as error:
        return [f"tools/{config.name} cannot be read under its policy: {error}"]
    return []


def _user_config() -> Path | None:
    """Return the user-level `ty/ty.toml` path if one exists in `%APPDATA%` or `$XDG_CONFIG_HOME`."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", "")
        fallback = ("AppData", "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", "")
        base = base if Path(base).is_absolute() else ""
        fallback = (".config",)
    if base:
        directory = Path(base)
    else:
        try:
            directory = Path.home().joinpath(*fallback)
        except RuntimeError:
            return None
    candidate = directory / "ty" / "ty.toml"
    return candidate if candidate.is_file() else None


def _tracked(root: Path) -> frozenset[str]:
    """Return existing Git-indexed `.py`/`.pyi` paths under `tools/`, relative to `tools/`."""
    return frozenset(path.removeprefix(TOOLS) for path in corpus_mod.read_index(root).files
                     if path.startswith(TOOLS) and path.endswith(MODULE_SUFFIXES)
                     and (root / path).is_file())


def _run_ty(rep: Reporter, root: Path, tracked: frozenset[str] | None) -> None:
    """Run `ty` across `TY_PLATFORMS` and enforce config, user-config, and `PYTHONPATH` rules."""
    tools = root / "tools"
    held = ", all rules at error"
    if refused := _settings(tools / "ty.toml"):
        rep.report("ty", "ty.toml setting(s) the gate refuses:", refused)
        held = " under the settings refused above"
    if (user := _user_config()) is not None:
        rep.report("ty", "user-level configuration(s) the gate refuses:",
                   [f"a user-level ty configuration at {user} merges into the gate's run"])
        held = " under the settings refused above"
    if (search := os.environ.get("PYTHONPATH")) is not None:
        rep.report("ty", "environment variable(s) the gate refuses:",
                   [f"PYTHONPATH is set to {search!r}, and ty searches each directory it "
                    "names ahead of the standard library in the gate's run"])
        held = " under the settings refused above"
    _run_checker(
        rep, "ty", TY_VERSION,
        [Pass(["check", "--config-file", str(tools / "ty.toml"), "--error", "all",
               "--python", sys.executable, "--python-version", PYTHON_VERSION,
               "--python-platform", platform,
               "--output-format", "concise", "--color", "never"],
              f"ty under python-platform {platform}",
              f"type error(s) under python-platform {platform}:",
              f"every expression reachable under python-platform {platform} typechecks "
              f"under ty {TY_VERSION}{held}", tracked, TY_UNSET)
         for platform in TY_PLATFORMS],
        tools, with_stderr=True, parse=_parse_ty)


def _file_suppressions(tools: Path, tracked: frozenset[str]) -> list[str]:
    """Find file-level or range suppression comments outside `FILE_SCOPED` in `tracked` modules."""
    findings: list[str] = []
    for module in sorted(tracked):
        try:
            text = (tools / module).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            findings.append(f"{module} cannot be read: {err}")
            continue
        if not (FILE_NOQA.search(text) or FILE_RANGE.search(text)):
            continue
        try:
            comments = [(token.start[0], token.string)
                        for token in tokenize.generate_tokens(io.StringIO(text).readline)
                        if token.type == tokenize.COMMENT]
        except (tokenize.TokenError, SyntaxError) as err:
            findings.append(f"{module} cannot be tokenized: {err}")
            continue
        findings.extend(f"{module}:{line} {comment}" for line, comment in comments
                        if FILE_RANGE.search(comment)
                        or any(not _names_file_scoped(comment[found.end():])
                               for found in FILE_NOQA.finditer(comment)))
    return findings


def _names_file_scoped(rest: str) -> bool:
    """Return whether the text after `noqa` names only rules in `FILE_SCOPED`."""
    named = re.match(r"\s*:([A-Z0-9,\s]*)", rest)
    codes = set(re.findall(r"[A-Z]+[0-9]+", named.group(1))) if named else set()
    return bool(codes) and codes <= FILE_SCOPED


def _run_ruff(rep: Reporter, root: Path, tracked: frozenset[str] | None) -> None:
    """Lint explicit indexed filenames, retaining configuration and suppression policy."""
    tools = root / "tools"
    held = ""
    if refused := _settings(tools / "ruff.toml"):
        rep.report("ruff", "ruff.toml setting(s) the gate refuses:", refused)
        held = " under the suppressions refused above"
    if tracked is not None and (suppressed := _file_suppressions(tools, tracked)):
        rep.report("ruff", "file-level or range suppression(s) the gate refuses:",
                   suppressed)
        held = " under the suppressions refused above"
    _run_checker(
        rep, "ruff", RUFF_VERSION,
        [Pass(["check", "--config", str(tools / "ruff.toml"), "--no-cache",
               "--no-respect-gitignore", "--no-force-exclude",
               "--target-version", "py" + PYTHON_VERSION.replace(".", ""),
               "--output-format", "concise", "--no-fix"],
              "ruff", "lint finding(s):",
              f"every function is annotated and ruff {RUFF_VERSION} is clean{held}",
              tracked)],
        tools, with_stderr=False, parse=_parse_ruff)


def _banned(config: Path) -> tuple[frozenset[str], list[str]]:
    """Read `BANNED` module-level imports from `ruff.toml`, failing closed on invalid config."""
    name = f"tools/{config.name}"
    none = frozenset[str]()
    try:
        settings = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as err:
        return none, [f"{name} cannot be read: {err}"]
    listed: object = settings
    for key in BANNED:
        listed = listed.get(key) if isinstance(listed, dict) else None
    modules = [module for module in listed if isinstance(module, str) and module] \
        if isinstance(listed, list) else []
    if not modules or not isinstance(listed, list) or len(modules) != len(listed):
        return none, [f"{name} sets {'.'.join(BANNED)} to {listed!r}; the gate holds "
                      "imports to a non-empty list of module names"]
    return frozenset(modules), []


def _banned_names(node: ast.Import | ast.ImportFrom, banned: frozenset[str]) -> list[str]:
    """Return any module names imported by `node` that match or sit under `banned`."""
    def listed(module: str) -> bool:
        return any(module == ban or module.startswith(ban + ".") for ban in banned)

    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names if listed(alias.name)]
    if node.level or node.module is None:
        return []
    if listed(node.module):
        return [node.module]
    return [member for alias in node.names
            if alias.name != "*" and listed(member := f"{node.module}.{alias.name}")]


def _is_platform(node: ast.AST) -> bool:
    """Return whether `node` is the attribute expression `sys.platform`."""
    return (isinstance(node, ast.Attribute) and node.attr == "platform"
            and isinstance(node.value, ast.Name) and node.value.id == "sys")


def _reads_platform(test: ast.expr) -> bool:
    """Return whether `test` contains `sys.platform`."""
    return any(_is_platform(node) for node in ast.walk(test))


def _literal(node: ast.expr) -> str | None:
    """Return `node`'s value if it is a string literal, else `None`."""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) \
        else None


def _literals(node: ast.expr, kinds: tuple[type[ast.Tuple | ast.List | ast.Set], ...]
              ) -> list[str] | None:
    """Return the string literals in a container literal of `kinds`, or `None`."""
    if not isinstance(node, kinds):
        return None
    values = [element.value for element in node.elts
              if isinstance(element, ast.Constant) and isinstance(element.value, str)]
    return values if len(values) == len(node.elts) else None


def _platform_value(test: ast.expr, platform: str) -> bool | None:
    """Evaluate `test` when `sys.platform == platform`, or return `None` if not statically decidable."""
    match test:
        case ast.UnaryOp(op=ast.Not(), operand=operand):
            value = _platform_value(operand, platform)
            return None if value is None else not value
        case ast.BoolOp(op=op, values=operands):
            values = [_platform_value(operand, platform) for operand in operands]
            if None in values:
                return None
            return all(values) if isinstance(op, ast.And) else any(values)
        case ast.Compare(left=left, ops=[ast.Eq() | ast.NotEq() as op],
                         comparators=[right]) if _is_platform(left):
            literal = _literal(right)
            return None if literal is None else (platform == literal) == isinstance(op, ast.Eq)
        case ast.Compare(left=left, ops=[ast.In() | ast.NotIn() as op],
                         comparators=[right]) if _is_platform(left):
            listed = _literals(right, (ast.Tuple, ast.List, ast.Set))
            return None if listed is None else (platform in listed) == isinstance(op, ast.In)
        case ast.Call(func=ast.Attribute(value=value, attr="startswith"), args=[prefix],
                      keywords=[]) if _is_platform(value):
            literal = _literal(prefix)
            prefixes = [literal] if literal is not None else _literals(prefix, (ast.Tuple,))
            return None if prefixes is None else platform.startswith(tuple(prefixes))
    return None


class Site(NamedTuple):
    """A non-function-scoped import of a banned module and its platform reachability."""
    line: int
    names: list[str]
    reach: frozenset[str]
    test: ast.expr | None


def _platform_imports(tree: ast.Module, banned: frozenset[str]) -> list[Site]:
    """Find imports of `banned` modules outside function bodies, tracking reachable `TY_PLATFORMS`."""
    found: list[Site] = []
    stack: list[tuple[ast.AST, frozenset[str], ast.expr | None]] = [
        (tree, frozenset(TY_PLATFORMS), None)]
    while stack:
        node, reach, nearest = stack.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(child, ast.If) and _reads_platform(child.test):
                values = {platform: _platform_value(child.test, platform)
                          for platform in reach}
                if None in values.values():
                    stack.append((child, reach, child.test))
                    continue
                taken = frozenset(platform for platform, value in values.items() if bool(value))
                for branch, platforms in ((child.body, taken), (child.orelse, reach - taken)):
                    if platforms:
                        stack.append((ast.Module(body=branch, type_ignores=[]), platforms,
                                      child.test))
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                if names := _banned_names(child, banned):
                    found.append(Site(child.lineno, names, reach, nearest))
            else:
                stack.append((child, reach, nearest))
    return sorted(found, key=lambda site: (site.line, site.names))


def _unfound(names: list[str]) -> list[str]:
    """Return entries in `names` whose top-level module cannot be found by `find_spec`."""
    unfound: list[str] = []
    for name in names:
        try:
            found = importlib.util.find_spec(name.partition(".")[0]) is not None
        except ImportError, ValueError:
            found = False
        if not found:
            unfound.append(name)
    return unfound


def _run_imports(rep: Reporter, root: Path, tracked: frozenset[str]) -> None:
    """Check `tracked` modules for banned imports outside function bodies not guarded by `sys.platform`."""
    tools = root / "tools"
    banned, unread = _banned(tools / "ruff.toml")
    if unread:
        rep.report("imports", "ruff.toml list(s) the gate cannot read:", unread)
        return
    spelled = re.compile(r"\b(?:" + "|".join(sorted(re.escape(ban.rpartition(".")[2])
                                                    for ban in banned)) + r")\b")
    every, running = frozenset(TY_PLATFORMS), sys.platform
    findings: list[str] = []
    for module in sorted(tracked):
        try:
            text = (tools / module).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            findings.append(f"{module} cannot be read: {err}")
            continue
        if not spelled.search(unicodedata.normalize("NFKC", text)):
            continue
        try:
            tree = ast.parse(text, module)
        except (SyntaxError, ValueError) as err:
            findings.append(f"{module} cannot be parsed: {err}")
            continue
        for site in _platform_imports(tree, banned):
            behind = "no sys.platform check" if site.test is None else \
                f"`{ast.unparse(site.test)}`"
            if site.reach == every:
                findings.append(
                    f"{module}:{site.line} imports {', '.join(site.names)} outside a function "
                    f"body, behind {behind}"
                    + ("" if site.test is None else ", a sys.platform test the scan does not "
                       "admit as separating platforms"))
            elif running in site.reach and (unfound := _unfound(site.names)):
                findings.append(
                    f"{module}:{site.line} imports {', '.join(unfound)} outside a function "
                    f"body, behind {behind}, on a branch {running} takes, where this "
                    "interpreter cannot find it")
    rep.report("imports", "import(s) of a module ruff.toml bans at module level outside a "
               "function body:", findings,
               "every import of a module ruff.toml bans at module level sits in a function "
               "body or where a sys.platform check keeps a platform from it")


def run(root: Path) -> Reporter:
    """Run `ty`, `ruff`, and the platform-import scan concurrently and return their merged `Reporter`."""
    rep = Reporter()
    rep.line("=== tools ===")

    tracked: frozenset[str] | None = None
    try:
        tracked = _tracked(root)
    except (RuntimeError, OSError, ValueError) as err:
        rep.report("coverage", "tracked module listing error(s):",
                   [f"the index cannot be read, so no run is held to the modules it "
                    f"tracks: {err}"])

    ty_rep, ruff_rep, imports_rep = Reporter(), Reporter(), Reporter()
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks = [pool.submit(_run_ty, ty_rep, root, tracked),
                 pool.submit(_run_ruff, ruff_rep, root, tracked)]
        if tracked is not None:
            tasks.append(pool.submit(_run_imports, imports_rep, root, tracked))
        for done in tasks:
            done.result()
    for part in (ty_rep, ruff_rep, imports_rep):
        rep.out.extend(part.out)
        rep.findings += part.findings

    if rep.findings:
        rep.line(f"{rep.findings} finding(s).")
    else:
        rep.line("the tools hold to their own discipline.")
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        suggest_on_error=True, description="Typecheck and lint this repository's own tools.")
    parser.parse_args(argv)

    report = run(corpus_mod.find_root())
    print("\n".join(report.out))
    return 1 if report.findings else 0
