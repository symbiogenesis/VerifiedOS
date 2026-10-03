# SPDX-License-Identifier: Apache-2.0
"""`run.py model rocq`: the canonical term's emission, its refusals and its receipt.

Each case stands a checkout and a build tree up in a temporary directory and replaces
the toolchain with doubles: the build is a function that writes, or does not write,
the two files the target emits, and the configured command is a `ninja -t commands`
listing the case states. What is real is the command's own logic: what it deletes
first, what it refuses, and what its receipt says about the files that are there.
"""

import argparse
import hashlib
import io
import json
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import env, rocqterm
from vos.cli import model

TERM = ("Require Import SailStdpp.Base.\n"
        "Axiom riscv_f32Add : mword 3 -> mword 32 -> mword 32 -> (mword 5 * mword 32).\n"
        "(* Axiom not_a_declaration : nat. *)\n"
        "Definition plat_term_write (_ : mword 8) : M (unit) := returnM (tt).\n"
        "Axiom riscv_f64Eq : mword 64 -> mword 64 -> (mword 5 * bool).\n")
TYPES = "Require Import SailStdpp.Base.\nInductive regstate := .\n"
STALE = "Axiom stale_from_another_toolchain : nat.\n"

TOOLS: rocqterm.Toolchain = {
    "sail": {"path": "/opt/sail/bin/sail", "sha256": "1" * 64, "version": "Sail 0.20.3"},
    "rocq_plugin": {"path": "/opt/sail/share/libsail/plugins/sail_plugin_coq.cmxs",
                    "sha256": "2" * 64, "version": ""},
    "z3": {"path": "/opt/z3/bin/z3", "sha256": "3" * 64, "version": "Z3 version 5.1.0"},
    "library": {"files": 1, "aggregate": "4" * 64, "sha256": {"prelude.sail": "5" * 64}},
}


@dataclass
class Lane:
    """One case's checkout, environment and build tree."""

    root: Path
    e: env.Environment
    tree: Path

    @property
    def out(self) -> Path:
        return rocqterm.output_dir(self.tree)

    @property
    def profile(self) -> Path:
        return self.e.profile

    def listing(self, config: Path | None = None) -> str:
        """The `ninja -t commands` lines of the target's closure, the emission naming
        `config`, by default the frozen profile."""
        named = self.profile if config is None else config
        model_dir = (self.root / "model" / "model").as_posix()
        return (f"cd {model_dir} && /opt/sail/bin/sail riscv.sail_project --list-files\n"
                f"cd {model_dir} && /opt/sail/bin/sail --strict-var --strict-bitvector "
                f"--strict-exponentials --require-version 0.20.3 --memo-z3-path "
                f"{self.tree.as_posix()}/model/sail_smt_cache --drocq-undef-axioms --rocq "
                f"--rocq-lib riscv_extras --rocq-output-dir {self.out.as_posix()} -o rv64d "
                f"--config {named.as_posix()} --all-modules riscv.sail_project\n")

    def leave_stale(self) -> None:
        """Outputs and a receipt an earlier run left, which no dependency names."""
        self.out.mkdir(parents=True, exist_ok=True)
        for name in rocqterm.OUTPUTS:
            (self.out / name).write_text(STALE, encoding="utf-8", newline="")
        (self.out / rocqterm.RECEIPT).write_text("{}\n", encoding="utf-8", newline="")

    def emitted(self) -> list[str]:
        return sorted(path.name for path in self.out.iterdir()) if self.out.is_dir() else []


@contextmanager
def lane(*, profile: bool = True) -> Iterator[Lane]:
    with tempfile.TemporaryDirectory(prefix="vos-test-rocq-") as temporary:
        root = Path(temporary).resolve()
        model_dir = root / "model" / "model"
        (model_dir / "prelude").mkdir(parents=True)
        (model_dir / "prelude" / "prelude.sail").write_text("default Order dec\n",
                                                            encoding="utf-8", newline="")
        (model_dir / "riscv.sail_project").write_text("prelude { files prelude/prelude.sail }\n",
                                                      encoding="utf-8", newline="")
        (model_dir / "CMakeLists.txt").write_text("# the target\n", encoding="utf-8",
                                                 newline="")
        if profile:
            (root / "model" / "config").mkdir(parents=True)
            (root / "model" / "config" / "verifiedos.json").write_text(
                '{"base": {}}\n', encoding="utf-8", newline="")
        e = env.Environment(root, root / "model", root / "build", root / "logs", "",
                            4, 4096, 2, 2)
        yield Lane(root, e, e.build_dir)


def run(at: Lane, listing: str, build: Callable[[list[str]], int]) -> tuple[int, str, list[list[str]]]:
    """Run the command with the toolchain replaced, returning its exit code, what it
    printed and every build it started."""
    started: list[list[str]] = []

    def stage(name: str, argv: list[str], *_args: object, **_kwargs: object) -> int:
        ensure(name == "rocq", f"the build stage is named rocq, got {name}")
        started.append(argv)
        return build(argv)

    said = io.StringIO()
    with (patch.object(model, "_require"), patch.object(model, "_seed_tree"),
          patch.object(model, "_configure", return_value=0),
          patch.object(model, "_ninja_commands", return_value=listing),
          patch.object(env, "build_lock", return_value=None),
          patch.object(env, "git_env", return_value={}),
          patch.object(env, "stage", side_effect=stage),
          patch.object(rocqterm, "listed_sources", return_value=["prelude/prelude.sail"]),
          patch.object(rocqterm, "toolchain", return_value=TOOLS),
          patch.object(rocqterm, "revision",
                       return_value={"revision": "a" * 40, "model_dirty": False}),
          redirect_stdout(said), redirect_stderr(said)):
        code = model.cmd_rocq(at.e, argparse.Namespace())
    return code, said.getvalue(), started


def writes(at: Lane, code: int = 0, *, also: Callable[[], None] | None = None
           ) -> Callable[[list[str]], int]:
    """A build that writes the term, then runs `also`, then exits `code`."""
    def build(_argv: list[str]) -> int:
        at.out.mkdir(parents=True, exist_ok=True)
        (at.out / rocqterm.OUTPUTS[0]).write_text(TERM, encoding="utf-8", newline="")
        (at.out / rocqterm.OUTPUTS[1]).write_text(TYPES, encoding="utf-8", newline="")
        if also is not None:
            also()
        return code
    return build


def _positive_emission() -> None:
    with lane() as at:
        at.leave_stale()
        code, said, started = run(at, at.listing(), writes(at))
        ensure(code == 0, f"a clean emission must pass, said: {said}")
        ensure(started == [["cmake", "--build", str(at.tree), "-j", "1", "--target",
                            rocqterm.TARGET]], f"the model's own target is built, got {started}")
        receipt = json.loads((at.out / rocqterm.RECEIPT).read_text(encoding="utf-8"))
        for name, text in zip(rocqterm.OUTPUTS, (TERM, TYPES), strict=True):
            data = text.encode("utf-8")
            ensure(receipt["outputs"][name] == {"sha256": hashlib.sha256(data).hexdigest(),
                                                "bytes": len(data),
                                                "lines": data.count(b"\n")},
                   f"the receipt names the emitted {name}, got {receipt['outputs'][name]}")
        ensure(receipt["axioms"] == {"count": 2, "names": ["riscv_f32Add", "riscv_f64Eq"]},
               f"axioms are the lines opening with Axiom, got {receipt['axioms']}")
        ensure("stale_from_another_toolchain" not in json.dumps(receipt),
               "nothing of the stale outputs reaches the receipt")
        command = receipt["command"]
        ensure(rocqterm.option(command, "--config")
               == "<checkout>/model/config/verifiedos.json"
               and rocqterm.option(command, "--rocq-output-dir") == "<tree>/rocq",
               f"the command names the lane and checkout by placeholder, got {command}")
        profile_digest = hashlib.sha256(at.profile.read_bytes()).hexdigest()
        ensure(receipt["inputs"]["configuration"] == {
            "path": "model/config/verifiedos.json", "sha256": profile_digest},
               f"the receipt binds the frozen profile, got {receipt['inputs']['configuration']}")
        source = "model/model/prelude/prelude.sail"
        digest = hashlib.sha256(b"default Order dec\n").hexdigest()
        ensure(receipt["inputs"]["sources"]["sha256"] == {source: digest}
               and receipt["inputs"]["sources"]["aggregate"]
               == hashlib.sha256(f"{digest}  {source}\n".encode()).hexdigest(),
               f"sources aggregate as the record states, got {receipt['inputs']['sources']}")
        ensure(receipt["toolchain"] == TOOLS and receipt["format"] == rocqterm.FORMAT
               and receipt["checkout"] == {"revision": "a" * 40, "model_dirty": False},
               "the toolchain and checkout identities are recorded")
        ensure("removed stale" in said and "2 axiom(s)" in said,
               f"the run says what it removed and declared, said: {said}")


def _missing_configuration() -> None:
    with lane(profile=False) as at:
        at.leave_stale()
        code, said, started = run(at, at.listing(), writes(at))
        ensure(code == 1 and "no frozen profile" in said,
               f"a missing profile refuses, got {code}: {said}")
        ensure(not started, "nothing is built without the profile")
        ensure(at.emitted() == [], f"stale outputs go even on refusal, left {at.emitted()}")


def _stale_configuration() -> None:
    with lane() as at:
        at.leave_stale()
        generated = at.tree / "config" / "rv64d_v256_e64.json"
        code, said, started = run(at, at.listing(generated), writes(at))
        ensure(code == 1 and "stale configuration" in said,
               f"a target emitting at another configuration refuses, got {code}: {said}")
        ensure(not started and at.emitted() == [],
               f"no build and no output, built {started}, left {at.emitted()}")


def _configuration_moves_during_emission() -> None:
    with lane() as at:
        def edit() -> None:
            at.profile.write_text('{"base": {"moved": true}}\n', encoding="utf-8",
                                  newline="")

        code, said, started = run(at, at.listing(), writes(at, also=edit))
        ensure(code == 1 and "changed while the term was emitted" in said,
               f"a configuration edited mid-emission refuses, got {code}: {said}")
        ensure(len(started) == 1 and at.emitted() == [],
               f"the emitted term goes with its refusal, left {at.emitted()}")


def _stale_outputs_without_emission() -> None:
    with lane() as at:
        at.leave_stale()
        code, said, started = run(at, at.listing(), lambda _argv: 0)
        ensure(code == 1 and "wrote no" in said,
               f"a build that emits nothing refuses rather than reading old files, got "
               f"{code}: {said}")
        ensure(len(started) == 1 and at.emitted() == [],
               f"the stale outputs were deleted before the build, left {at.emitted()}")


def _failed_build() -> None:
    with lane() as at:
        code, said, _started = run(at, at.listing(), writes(at, code=2))
        ensure(code == 1 and "exited 2" in said, f"a failed build refuses, got {code}: {said}")
        ensure(at.emitted() == [], f"a failed build leaves no output, left {at.emitted()}")


def _command_parse() -> None:
    with lane() as at:
        argv = rocqterm.target_command(at.listing())
        ensure(argv[0] == "/opt/sail/bin/sail" and "--rocq" in argv,
               f"the emission's argv follows the `&&`, got {argv}")
        rocqterm.require_profile(argv, at.profile)
        for listing, why in (("cd x && sail --list-files\n", "no emission"),
                             (at.listing() * 2, "two emissions")):
            try:
                rocqterm.target_command(listing)
            except rocqterm.TermError:
                continue
            raise AssertionError(f"a listing with {why} must refuse")
        try:
            rocqterm.option([*argv, "--config", "x.json"], "--config")
        except rocqterm.TermError:
            pass
        else:
            raise AssertionError("a command naming --config twice must refuse")
        ensure(rocqterm.axioms(TERM) == ["riscv_f32Add", "riscv_f64Eq"],
               "only a line opening with Axiom declares one")


def cases() -> list[Case]:
    return [Case("positive-emission", _positive_emission),
            Case("missing-configuration", _missing_configuration),
            Case("stale-configuration", _stale_configuration),
            Case("configuration-moves-during-emission", _configuration_moves_during_emission),
            Case("stale-outputs-without-emission", _stale_outputs_without_emission),
            Case("failed-build", _failed_build),
            Case("command-parse", _command_parse)]
