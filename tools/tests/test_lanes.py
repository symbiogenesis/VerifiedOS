# SPDX-License-Identifier: Apache-2.0
"""The two lanes as one command surface, held to the declaration that makes it one.

[vos/cli/\\_\\_init\\_\\_.py](../vos/cli/__init__.py) says which subcommands of a guest
command answer on either lane, and `run.py` reads that `host_ok` set to decide whether
to re-launch into WSL. A declaration like that is worth having only if the command it
names answers where it says it does, and for as long as `model.py` loaded the build
environment before it dispatched, the set was true of `run.py` and false of the module
behind it: three of its members printed *the model loops run inside WSL* on the lane the
table declared them answerable on. What is held here is that claim at the seam where it
broke, for every member of every set: each declared subcommand is dispatched in this
process, on whichever lane this process is, and has to answer.

**`--help` decides nothing about this**, which is why the table below carries arguments
rather than a flag. argparse exits during parsing, before a module reaches its
environment at all, so a subcommand that would refuse still prints its usage and exits
0; reaching the handler is the only thing that decides.

The modules are imported at this module's own import rather than inside a case, because
[the runner](../vos/cli/test.py) loads modules serially from the main thread and runs
the cases in a pool, and an import raced against another module's is the one thing it
takes care to avoid.
"""

import io
import json
import tempfile
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import cast

from tests.harness import TOOLS, Case, ensure
from vos.cli import COMMANDS

_ROOT = TOOLS.parent
_README = TOOLS / "README.md"

# Every command carrying a `host_ok` set, imported once here. The dispatch a case makes
# is this module's `main(argv)`, which is exactly what `run.py` calls once it has
# declined to hop.
_MODULES: dict[str, ModuleType] = {
    command.name: import_module(command.module)
    for command in COMMANDS if command.host_ok
}

# What one declared subcommand has to be handed to reach its handler. A scratch
# directory is passed in because three of them write something, and a run that wrote
# into the checkout would be a test with a side effect on the tree every other case
# reads.
type Argv = Callable[[Path], list[str]]


def _trivial_schema(scratch: Path) -> list[str]:
    """A schema and a config that agree, authored here rather than taken from the tree.

    The shipped configurations are validated against the *generated* schema, which is a
    build artifact and so absent on a lane that has never built. What this case decides
    is that the subcommand answers at all, and a two-key pair decides that without
    making the case depend on a tree the host cannot produce.
    """
    schema = scratch / "schema.json"
    config = scratch / "config.json"
    schema.write_text(
        json.dumps({"type": "object", "properties": {"a": {"type": "integer"}}}),
        encoding="utf-8", newline="")
    config.write_text(json.dumps({"a": 1}), encoding="utf-8", newline="")
    return [str(schema), str(config)]


_RUNS: dict[tuple[str, str], Argv] = {
    ("model", "config-keys"): lambda _: [
        str(_ROOT / "model" / "config" / "verifiedos.json"),
        str(_ROOT / "model" / "config" / "verifiedos-v.json")],
    ("model", "validate-config"): _trivial_schema,
    # `cmd_asm` and `cmd_config_keys` take the paths as the caller spells them, so
    # these are absolute: a case's working directory is the runner's, not the root's.
    ("model", "asm"): lambda scratch: [
        str(_ROOT / "corpus" / "atomics.s"), str(scratch / "atomics.elf")],
    ("model", "freeze-emit"): lambda scratch: [
        "base-integer", "--out", str(scratch / "freeze")],
    ("rtl", "provenance"): lambda _: [],
    ("oracle", "list"): lambda _: [],
    ("oracle", "emit"): lambda _: ["--spec", "capformat"],
    # `seed list` resolves its file against the root it finds for itself, so this one
    # is repository-relative by the subcommand's own contract.
    ("seed", "list"): lambda _: ["--file", "model/model/core/cap_common.sail"],
    ("testrig", "protocol"): lambda _: [],
}


def _declared() -> set[tuple[str, str]]:
    return {(command.name, sub) for command in COMMANDS for sub in command.host_ok}


def _every_declaration_has_a_run() -> None:
    # The table is the case's subject and not its fixture: a subcommand declared
    # answerable on either lane and given no run here would be a declaration this
    # module reports green about and never exercises.
    declared, covered = _declared(), set(_RUNS)
    ensure(declared == covered,
           f"every declared subcommand needs a run and every run a declaration; "
           f"declared and unrun: {sorted(declared - covered)}, "
           f"run and undeclared: {sorted(covered - declared)}")


def _declared_subcommands_answer_on_this_lane() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        scratch = Path(td).resolve()
        for (name, sub), argv in sorted(_RUNS.items()):
            out, err = io.StringIO(), io.StringIO()
            try:
                with redirect_stdout(out), redirect_stderr(err):
                    # cast because `main` crosses a dynamic import and answers `Any`;
                    # the convention it is being held to is that it returns an exit code
                    code = cast("int", _MODULES[name].main([sub, *argv(scratch)]))
            except SystemExit as exc:
                raise AssertionError(
                    f"`run.py {name} {sub}` is declared answerable on either lane and "
                    f"refused this one: {exc}") from exc
            said = out.getvalue() + err.getvalue()
            ensure("runs inside WSL" not in said and "run inside WSL" not in said,
                   f"`run.py {name} {sub}` answered with the guest refusal: {said!r}")
            ensure(code == 0,
                   f"`run.py {name} {sub}` exited {code}: {said[-400:]!r}")


def _run_py_hops_on_exactly_the_rest() -> None:
    for command in COMMANDS:
        for sub in sorted(command.host_ok):
            ensure(not command.guest_only([sub]),
                   f"`run.py {command.name} {sub}` is declared answerable here and "
                   f"must not be re-launched into the guest")
        ensure(command.guest_only([]) == (command.lane == "guest"),
               f"a bare `run.py {command.name}` hops exactly when its lane is the "
               f"guest's, and this one does not")
    ensure(next(c for c in COMMANDS if c.name == "model").guest_only(["build"]),
           "a guest subcommand outside the set still hops")


def _readme_names_every_declaration() -> None:
    """The sentence a person reads, against the set the tool acts on.

    Not tidiness: the sentence is where a reader learns that a command they were told
    runs in WSL will answer here, so one that names fewer than the table does sends
    them into the guest for an answer the host already had.
    """
    text = _README.read_text(encoding="utf-8")
    missing = sorted(f"{name} {sub}" for name, sub in _declared()
                     if f"`{name} {sub}`" not in text)
    ensure(not missing,
           f"tools/README.md must name every subcommand declared answerable on either "
           f"lane; it does not name: {missing}")


def cases() -> list[Case]:
    return [
        Case("every-declaration-has-a-run", _every_declaration_has_a_run),
        Case("declared-subcommands-answer", _declared_subcommands_answer_on_this_lane),
        Case("hops-on-exactly-the-rest", _run_py_hops_on_exactly_the_rest),
        Case("readme-names-every-declaration", _readme_names_every_declaration),
    ]
