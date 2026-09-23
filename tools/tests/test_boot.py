# SPDX-License-Identifier: Apache-2.0
"""M7.1's boot harness: the roster reading, composition refusals, staleness and digests."""

import hashlib
import io
import json
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import cast

from tests.harness import TOOLS, Case, ensure
from vos import asm, boot, env, toolenv, trace
from vos.cli import boot as cli

ROOT = TOOLS.parent
FIXTURE = "tools/boot/fixture-recipe.json"
SOURCES = ("fixture-firmware.s", "fixture-kernel.s", "fixture-service.s")


def _refused[T](kind: type[Exception], fn: Callable[[], T], needle: str) -> None:
    try:
        fn()
    except kind as exc:
        ensure(needle in str(exc), f"refused for the wrong reason: {exc}")
    else:
        raise AssertionError(f"not refused; expected {kind.__name__} naming {needle!r}")


@contextmanager
def _scratch() -> Iterator[Path]:
    """A throwaway root holding the configuration and the fixture's files."""
    parent = toolenv.environment(ROOT, sys.platform).parent / "boot-tests"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as temporary:
        root = Path(temporary)
        (root / "model" / "config").mkdir(parents=True)
        shutil.copyfile(ROOT / "model" / "config" / "verifiedos.json",
                        root / "model" / "config" / "verifiedos.json")
        (root / "tools" / "boot").mkdir(parents=True)
        for leaf in (*SOURCES, "fixture-roster.json", "fixture-recipe.json"):
            shutil.copyfile(ROOT / "tools" / "boot" / leaf, root / "tools" / "boot" / leaf)
        yield root


def _recipe_raw(root: Path) -> dict[str, object]:
    return cast("dict[str, object]", json.loads((root / FIXTURE).read_text(encoding="utf-8")))


def _members(raw: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", raw["members"])


def _write(root: Path, name: str, raw: dict[str, object]) -> str:
    relative = f"tools/boot/{name}.json"
    (root / relative).write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8",
                                 newline="\n")
    return relative


def _compose(root: Path, relative: str) -> dict[str, object]:
    return boot.compose(root, boot.load_recipe(root, relative), root / "out")


# --- the roster ---------------------------------------------------------------------


def _contract_roster_reads() -> None:
    roster = boot.load_roster(ROOT, boot.CONTRACT)
    ids = [m.id for m in roster.members]
    ensure(ids[:2] == ["rot-firmware", "mmode-firmware"],
           f"the chain opens with the RoT and the M-mode firmware (R-09-002): {ids}")
    images = roster.image_members()
    ensure([m.rank for m in images] == list(range(1, len(images) + 1)),
           "image ranks run from one without a gap")
    ensure([m.id for m in images][:3] == ["mmode-firmware", "kernel", "supervisor"],
           "firmware, kernel and the supervision tree are entered first")
    by_id = roster.by_id()
    for member in ("supervisor", "admission", "composer", "copy-service"):
        ensure(by_id[member].owner == "M7.1",
               f"{member} is statement-only and M7.1 is its executable owner")
    ensure({m.kind for m in roster.members} <= set(boot.KINDS), "kinds are the closed set")
    ensure(bool(roster.blocking()),
           "no roster member has an executable product at this revision, so the roster blocks")


def _roster_refusals() -> None:
    text = (ROOT / boot.CONTRACT).read_text(encoding="utf-8")
    row = "| `kernel` | `image` | 2 |"
    ensure(row in text, "the refusal cases below edit a row the contract still carries")
    for edited, needle in (
            (text.replace("| Member | Kind |", "| Member | Class |"), "header"),
            (text.replace(row, "| `kernel` | `daemon` | 2 |"), "kind"),
            (text.replace(row, "| `kernel` | `linked` | 2 |"), "carries a rank"),
            (text.replace(row, "| `kernel` | `image` | 1 |"), "rank 1"),
            (text.replace("| `storage` |", "| `kernel` |"), "declared twice"),
            (text.replace(row, "| `kernel` | `image` | two |"), "neither"),
            (text.replace(row, "| `kernel` | `image` | 2 | extra |"), "cells"),
            (text.replace(boot.ROSTER_HEADING, "## 2. Roster"), "heading")):
        ensure(edited != text, f"the edit for {needle!r} applied")
        _refused(boot.RecipeError, lambda edited=edited: boot.parse_contract_roster(edited),
                 needle)
    fixture = json.loads((ROOT / "tools/boot/fixture-roster.json").read_text(encoding="utf-8"))
    fixture["members"][0]["status"] = "executable"
    _refused(boot.RecipeError,
             lambda: boot.parse_json_roster(json.dumps(fixture).encode(), "fixture"),
             "fixture roster")
    _refused(boot.RecipeError,
             lambda: boot.parse_json_roster(b'{"schema_version": 1, "name": "a", "name": "b",'
                                            b' "members": []}', "doubled"), "duplicate")


# --- the recipe ---------------------------------------------------------------------


def _recipe_refusals() -> None:
    base = _recipe_raw(ROOT)

    def parse(edit: Callable[[dict[str, object]], None]) -> None:
        raw = json.loads(json.dumps(base))
        edit(raw)
        boot.parse_recipe(json.dumps(raw).encode(), "edited")

    def admission(raw: dict[str, object]) -> None:
        raw["admission"] = "record.json"

    def producer(raw: dict[str, object]) -> None:
        _members(raw)[0]["producer"] = "ccomp"

    def address(raw: dict[str, object]) -> None:
        _members(raw)[0]["text_base"] = 2147483648

    def unknown(raw: dict[str, object]) -> None:
        raw["linker_script"] = "none"

    def missing(raw: dict[str, object]) -> None:
        del raw["tohost"]

    def digest(raw: dict[str, object]) -> None:
        cast("dict[str, object]", raw["expected"])["event_sha256"] = "A" * 64

    def zero_limit(raw: dict[str, object]) -> None:
        raw["inst_limit"] = 0

    for edit, needle in ((admission, "admission"), (producer, "producer"),
                         (address, "hexadecimal"), (unknown, "unknown linker_script"),
                         (missing, "missing tohost"), (digest, "event_sha256"),
                         (zero_limit, "inst_limit")):
        _refused(boot.RecipeError, lambda edit=edit: parse(edit), needle)
    parse(lambda raw: None)


def _fixture_composes_to_the_measured_image() -> None:
    recipe = boot.load_recipe(ROOT, FIXTURE)
    ensure(recipe.expected is not None, "the fixture recipe carries its reference digests")
    expected = cast("boot.Expected", recipe.expected)
    parent = toolenv.environment(ROOT, sys.platform).parent / "boot-tests"
    parent.mkdir(parents=True, exist_ok=True)
    images = []
    with tempfile.TemporaryDirectory(dir=parent) as temporary:
        for attempt in ("first", "second"):
            record = boot.compose(ROOT, recipe, Path(temporary) / attempt)
            images.append(cast("dict[str, str]", record["image"])["sha256"])
            ensure(record["accepted"] is False, "a fixture composition is never accepted")
            joins = " ".join(cast("list[str]", record["open"]))
            ensure("fixture members stand in" in joins and "admission record" in joins,
                   f"the record names what keeps it open: {joins}")
    ensure(images[0] == images[1], "composition is deterministic")
    ensure(images[0] == expected.image_sha256,
           f"the host composes the image the golden emulator was measured on: {images[0]}")


def _membership_refusals() -> None:
    contract = boot.load_roster(ROOT, boot.CONTRACT)
    fixture = boot.load_roster(ROOT, "tools/boot/fixture-roster.json")
    recipe = boot.load_recipe(ROOT, FIXTURE)

    def with_members(ids: list[str]) -> boot.Recipe:
        members = {m.id: m for m in recipe.members}
        template = recipe.members[0]
        chosen = tuple(members.get(i, boot.RecipeMember(i, "asm", template.source,
                                                         template.text_base,
                                                         template.data_base, {}))
                       for i in ids)
        return boot.Recipe(recipe.path, recipe.name, recipe.roster, recipe.configuration,
                           recipe.inst_limit, recipe.tohost, chosen, recipe.expected)

    boot.check_membership(recipe, fixture)
    ids = [m.id for m in recipe.members]
    cases = ((with_members([ids[0], ids[0], ids[1], ids[2]]), fixture, "composed twice"),
             (with_members([*ids, "stranger"]), fixture, "not a member"),
             (with_members(ids[:2]), fixture, "missing member fixture-service"),
             (with_members([ids[1], ids[0], ids[2]]), fixture, "contradicts"),
             (with_members(["kernel"]), contract, "statement-only"),
             (with_members(["rot-firmware"]), contract, "`rot` member"),
             (with_members(["admission"]), contract, "`offline` member"))
    for candidate, roster, needle in cases:
        _refused(boot.RefusalError, lambda c=candidate, r=roster: boot.check_membership(c, r),
                 needle)
    _refused(boot.RefusalError, lambda: boot.check_membership(with_members(["kernel"]), contract),
             "executable owner M4.4")


def _placement_refusals() -> None:
    def refused(edit: Callable[[Path, dict[str, object]], None], needle: str) -> None:
        with _scratch() as root:
            raw = _recipe_raw(root)
            edit(root, raw)
            relative = _write(root, "edited", raw)
            _refused(boot.RefusalError, lambda: _compose(root, relative), needle)
            ensure(not (root / "out" / "record.json").exists(),
                   "a refused composition leaves no record")

    def overlap(_: Path, raw: dict[str, object]) -> None:
        _members(raw)[1]["text_base"] = "0x80000010"

    def outside(_: Path, raw: dict[str, object]) -> None:
        # The firmware is the member with data, and an empty extent places nothing.
        _members(raw)[0]["data_base"] = "0x10000"

    def io_text(_: Path, raw: dict[str, object]) -> None:
        _members(raw)[2]["text_base"] = "0x2000000"

    def tohost_misaligned(_: Path, raw: dict[str, object]) -> None:
        raw["tohost"] = "0x8000f004"

    def tohost_on_data(_: Path, raw: dict[str, object]) -> None:
        raw["tohost"] = "0x80008000"

    def import_absent(_: Path, raw: dict[str, object]) -> None:
        _members(raw)[0]["imports"] = {"kernel_entry": "nobody"}

    def import_tohost(_: Path, raw: dict[str, object]) -> None:
        _members(raw)[2]["imports"] = {"tohost": "fixture-firmware"}

    def import_self(_: Path, raw: dict[str, object]) -> None:
        _members(raw)[2]["imports"] = {"me": "fixture-service"}

    def defines_import(root: Path, _: dict[str, object]) -> None:
        path = root / "tools/boot/fixture-firmware.s"
        path.write_text(path.read_text(encoding="utf-8") + "kernel_entry:\n        nop\n",
                        encoding="utf-8", newline="\n")

    def late_start(root: Path, _: dict[str, object]) -> None:
        path = root / "tools/boot/fixture-service.s"
        text = path.read_text(encoding="utf-8").replace(
            "_start:\n", "        nop\n_start:\n", 1)
        path.write_text(text, encoding="utf-8", newline="\n")

    for edit, needle in ((overlap, "overlap"), (outside, "no MainMemory region"),
                         (io_text, "no MainMemory region"), (tohost_misaligned, "aligned"),
                         (tohost_on_data, "overlap"), (import_absent, "does not compose"),
                         (import_tohost, "the recipe owns it"), (import_self, "from itself"),
                         (defines_import, "imported from another unit"),
                         (late_start, "first byte of its text")):
        refused(edit, needle)


def _staleness() -> None:
    with _scratch() as root:
        recipe = boot.load_recipe(root, FIXTURE)
        out = root / "out"
        record = boot.compose(root, recipe, out)
        ensure(boot.stale(root, record, out) == [], "a fresh composition is not stale")
        ensure(boot.load_record(out) == json.loads(json.dumps(record)),
               "the record read back is the record written")
        # Refreshing the measured block moves nothing a composition reads.
        raw = _recipe_raw(root)
        cast("dict[str, object]", raw["expected"])["retired"] = 52
        _write(root, "fixture-recipe", raw)
        ensure(boot.stale(root, record, out) == [],
               "a changed expected block does not stale the composition it measured")
        raw["inst_limit"] = 99
        _write(root, "fixture-recipe", raw)
        found = boot.stale(root, record, out)
        ensure(len(found) == 1 and "stale recipe" in found[0], f"declaration change: {found}")
        raw["inst_limit"] = 100000
        _write(root, "fixture-recipe", raw)
        service = root / "tools/boot/fixture-service.s"
        service.write_text(service.read_text(encoding="utf-8") + "\n", encoding="utf-8",
                           newline="\n")
        found = boot.stale(root, record, out)
        ensure(found == [f"stale component fixture-service: {service} changed since "
                         f"composition"], f"one stale component, named: {found}")
        (out / "image.elf").write_bytes(b"not the image")
        roster = root / "tools/boot/fixture-roster.json"
        roster.write_text(roster.read_text(encoding="utf-8") + "\n", encoding="utf-8",
                          newline="\n")
        found = boot.stale(root, record, out)
        ensure(any("stale roster" in f for f in found) and any("stale image" in f for f in found),
               f"roster and image changes are both named: {found}")
        _refused(boot.RecipeError, lambda: boot.load_record(root / "nowhere"), "compose")


# --- the run ------------------------------------------------------------------------

TOHOST = 0x8000F000
ENTRIES = {0x80000000: "a", 0x80001000: "b"}


def _w(address: int, value: int, width: int = 8) -> str:
    return f"W {address:X} {width} 0 {value:0{2 * width}X}"


def _trace_lines(exit_value: int = 1, verdict: str = "SUCCESS") -> list[str]:
    return ["Entry point: 0x80000000",
            "I 0 0000000080000000 00000013",
            f"{_w(TOHOST, 0x0101 << 48 | ord('A'))}",
            "I 1 0000000080000004 00000073",
            "T 0 11",
            "I 2 0000000080001000 00000013",
            "X 5 0 0000000000000001",
            f"{_w(TOHOST, 0x0101 << 48 | ord('B'))}",
            f"{_w(TOHOST + 4, 0x12345678, 4)}",
            "I 3 0000000080001004 00000013",
            _w(TOHOST, exit_value),
            verdict]


def _projection() -> None:
    lines = _trace_lines()
    projection = boot.project(iter(lines), ENTRIES, TOHOST)
    ensure(projection.events == ["ENTER a", "HTIF 0 8 0101000000000041", "TRAP", "ENTER b",
                                 "HTIF 0 8 0101000000000042", "HTIF 4 4 12345678",
                                 "HTIF 0 8 0000000000000001", "EXIT 0"],
           f"events: {projection.events}")
    ensure(projection.retired == 4 and projection.records == 10,
           f"{projection.retired} retired over {projection.records} records")
    ensure(projection.trace_digest == trace.digest(trace.normalize_commit(lines)),
           "the fingerprint is the corpus's own digest over the same records")
    ensure(projection.console == b"AB" and projection.htif_exit == 0
           and projection.verdict == "SUCCESS", "the HTIF reading and the verdict")
    ensure(projection.event_log() == "".join(f"{e}\n" for e in projection.events).encode(),
           "the log is one LF-terminated line per event")
    ensure(projection.event_sha256 == hashlib.sha256(projection.event_log()).hexdigest(),
           "the event digest is the SHA-256 of the log's bytes")
    failed = boot.project(iter(_trace_lines(0x2B, "FAILURE: 21 (0x00000015)")), ENTRIES, TOHOST)
    ensure(failed.htif_exit == 21 and boot.verdict_code(failed.verdict) == 21,
           "the exit code is the payload shifted right by one, and the verdict agrees")
    ensure(boot.verdict_code("FAILURE: possible trap loop detected with MEPC=0x0") is None
           and boot.verdict_code(None) is None, "a verdict without a code states none")
    silent = boot.project(iter(_trace_lines()[:4]), ENTRIES, TOHOST)
    ensure(silent.events[-1] == "EXIT none" and silent.htif_exit is None,
           "no exit write is EXIT none")


def _observation(lines: list[str], console: bytes, *, returncode: int = 0,
                 timed_out: bool = False) -> boot.Observation:
    return boot.Observation(boot.project(iter(lines), ENTRIES, TOHOST), console, returncode,
                            timed_out, 0.01)


RECORD: dict[str, object] = {"members": [{"id": "a", "entry": "0x80000000"},
                                         {"id": "b", "entry": "0x80001000"}]}


def _run_findings() -> None:
    clean = _observation(_trace_lines(), b"AB")
    ensure(boot.run_findings(clean, RECORD) == [], "a clean run has no finding")
    ensure(boot.entries_of(RECORD) == ENTRIES, "entries come from the record")
    for observation, needle in (
            (_observation(_trace_lines(), b"AX"), "console file"),
            (_observation(_trace_lines(verdict="FAILURE: 3 (0x3)"), b"AB"), "disagrees"),
            (_observation(_trace_lines(exit_value=7, verdict="FAILURE: 3 (0x3)"), b"AB"),
             "HTIF exit 3"),
            (_observation(_trace_lines()[:4], b"A"), "no HTIF exit"),
            (_observation(_trace_lines(), b"AB", timed_out=True), "timeout")):
        found = boot.run_findings(observation, RECORD)
        ensure(any(needle in f for f in found), f"{needle!r} not among {found}")
    order: dict[str, object] = {"members": [{"id": "b", "entry": "0x80001000"},
                                            {"id": "a", "entry": "0x80000000"}]}
    ensure(boot.boot_order(clean.projection.events, order)
           == ["first entries a, b do not follow the composed order b, a"], "boot order")
    absent: dict[str, object] = {"members": [*cast("list[object]", RECORD["members"]),
                                             {"id": "c", "entry": "0x80002000"}]}
    ensure(boot.boot_order(clean.projection.events, absent) == ["member c was never entered"],
           "a member never entered is named")


def _against_expected() -> None:
    clean = _observation(_trace_lines(), b"AB")
    expected = boot.Expected("e" * 64, clean.console_sha256, clean.projection.event_sha256,
                             len(clean.projection.events), clean.projection.trace_digest,
                             clean.projection.retired)
    ensure(boot.expected_block(clean, "e" * 64) == vars(expected),
           "the refreshed block carries exactly the expectation's fields")
    ensure(boot.against_expected(clean, "e" * 64, expected) == [], "a matching run")
    ensure(boot.against_expected(clean, "e" * 64, None)
           == ["the recipe records no expected digests"], "no expectation is a finding")
    moved = boot.against_expected(clean, "f" * 64, expected)
    ensure(len(moved) == 1 and "measured on image" in moved[0],
           f"a changed image is an expectation to refresh, not a mismatch: {moved}")
    for observation, needle in ((_observation(_trace_lines(), b"AC"), "console digest"),
                                (_observation(_trace_lines(verdict="SUCCESS!"), b"AB"), None),
                                (_observation(_trace_lines(exit_value=3), b"AB"),
                                 "event digest")):
        found = boot.against_expected(observation, "e" * 64, expected)
        if needle is None:
            ensure(found == [], f"the verdict line is not part of any digest: {found}")
        else:
            ensure(any(needle in f for f in found), f"{needle!r} not among {found}")
    shifted = _trace_lines()
    shifted.insert(6, "X 6 0 0000000000000002")
    found = boot.against_expected(_observation(shifted, b"AB"), "e" * 64, expected)
    ensure(len(found) == 1 and "commit trace" in found[0],
           f"a record the event log does not read still moves the fingerprint: {found}")


_FAKE = '''
import json, sys, time
plan = json.load(open(sys.argv[1], encoding="utf-8"))
args = sys.argv[2:]
with open(args[args.index("--terminal-log") + 1], "wb") as console:
    console.write(plan["console"].encode())
time.sleep(plan.get("sleep", 0))
for line in plan["lines"]:
    print(line, flush=True)
'''


def _fake_emulator() -> None:
    parent = toolenv.environment(ROOT, sys.platform).parent / "boot-tests"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as temporary:
        here = Path(temporary)
        fake = here / "fake.py"
        fake.write_text(_FAKE, encoding="utf-8", newline="\n")
        plan = here / "plan.json"
        plan.write_text(json.dumps({"console": "AB", "lines": _trace_lines()}),
                        encoding="utf-8")
        console = here / "console.log"
        argv = [sys.executable, str(fake), str(plan), "--terminal-log", str(console)]
        observation = boot.boot_image(argv, console, ENTRIES, TOHOST, 60,
                                      here / "trace.log")
        ensure(observation.returncode == 0 and not observation.timed_out,
               f"the fake ran: {observation.returncode}")
        ensure(boot.run_findings(observation, RECORD) == [], "the streamed run is clean")
        ensure(observation.console == b"AB", "the console file is read after the run")
        kept = (here / "trace.log").read_text(encoding="utf-8").splitlines()
        ensure(kept == _trace_lines(), "the kept trace is the stream, whole")
        plan.write_text(json.dumps({"console": "", "lines": [], "sleep": 30}), encoding="utf-8")
        slow = boot.boot_image(argv, console, ENTRIES, TOHOST, 0.5)
        ensure(slow.timed_out and slow.wall_seconds < 20,
               f"a run past its timeout is stopped and says so: {slow.wall_seconds}")
        ensure(any("timeout" in f for f in boot.run_findings(slow, RECORD)),
               "the timeout is a finding")

    with _scratch() as root:
        recipe = boot.load_recipe(root, FIXTURE)
        clean = _observation(_trace_lines(), b"AB")
        block = boot.expected_block(clean, "e" * 64)
        ensure(boot.refresh_expected(root, recipe, block), "the block is rewritten")
        ensure(not boot.refresh_expected(root, recipe, block), "a second refresh moves nothing")
        reread = boot.load_recipe(root, FIXTURE)
        ensure(reread.expected is not None and reread.expected.retired == 4
               and reread.members == recipe.members, "only the measured block moved")


# --- the assembler's placement ------------------------------------------------------


def _assembler_placement() -> None:
    source = (ROOT / "corpus" / "base-integer.s").read_text(encoding="utf-8")
    default = asm.Assembler(source, "base-integer.s").assemble()
    explicit = asm.Assembler(source, "base-integer.s", text_base=asm.TEXT_BASE,
                             data_base=asm.DATA_BASE, externals={}).assemble()
    ensure([bytes(s.data) for s in default[0]] == [bytes(s.data) for s in explicit[0]]
           and default[1:] == explicit[1:], "the defaults are the lone program's placement")
    unit = ("        .text\n_start:\n        la c5, neighbour\n        cjr c5\n"
            "        .data\nhere:\n        .dword neighbour\n")
    sections, symbols, entry = asm.Assembler(
        unit, "unit.s", text_base=0x80004000, data_base=0x8000C000,
        externals={"neighbour": 0x80001000}).assemble()
    ensure(entry == 0x80004000 and sections[0].addr == 0x80004000
           and sections[1].addr == 0x8000C000, "the unit lands where the composer placed it")
    ensure(int.from_bytes(bytes(sections[1].data[:8]), "little") == 0x80001000,
           "an import evaluates to the neighbour's address")
    ensure("neighbour" not in symbols and symbols["here"] == (".data", 0x8000C000),
           "an import is not a symbol of this unit")
    _refused(asm.AsmError, lambda: asm.Assembler("neighbour:\n        nop\n", "unit.s",
                                                 externals={"neighbour": 4}).assemble(),
             "imported from another unit")
    _refused(asm.AsmError, lambda: asm.Assembler("        la c5, stranger\n", "unit.s",
                                                 externals={}).assemble(), "no symbol stranger")


# --- the command --------------------------------------------------------------------


def _cli(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = cli.main(argv)
    return code, out.getvalue()


def _command() -> None:
    code, said = _cli(["roster"])
    ensure(code == 0 and "OPEN boot roster" in said and "statement-only" in said,
           f"the contract's roster reads and says it is blocked: {said}")
    code, said = _cli(["roster", "--roster", "tools/boot/missing.json"])
    ensure(code == 2, f"an unreadable roster is exit 2: {said}")
    parent = toolenv.environment(ROOT, sys.platform).parent / "boot-tests"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as temporary:
        out = Path(temporary) / "out"
        code, said = _cli(["compose", FIXTURE, "--out", str(out)])
        ensure(code == 0 and "ok boot compose" in said and "open: fixture members" in said,
               f"the fixture composes: {said}")
        missing = str(Path(temporary) / "no-such-emulator")
        code, said = _cli(["run", FIXTURE, "--out", str(out), "--simulator", missing])
        ensure(code == 2 and "no golden emulator" in said, f"no emulator is exit 2: {said}")
        code, said = _cli(["run", FIXTURE, "--out", str(Path(temporary) / "empty")])
        ensure(code == 2 and "compose the recipe first" in said,
               f"no record is exit 2: {said}")
    code, said = _cli(["compose", "tools/boot/no-such-recipe.json", "--out", "unused"])
    ensure(code == 2, f"an unreadable recipe is exit 2: {said}")


def _golden_emulator() -> None:
    """The tracked fixture boots on this lane's emulator to its recorded digests."""
    environment = env.load()
    recipe = boot.load_recipe(ROOT, FIXTURE)
    out = environment.lane_root / "boot-tests" / "fixture"
    record = boot.compose(ROOT, recipe, out)
    ensure(boot.stale(ROOT, record, out) == [], "fresh")
    console = out / "console.log"
    argv = [str(environment.simulator), "--config", str(ROOT / recipe.configuration),
            "--trace-commit", "--terminal-log", str(console), "--inst-limit",
            str(recipe.inst_limit), str(out / "image.elf")]
    observation = boot.boot_image(argv, console, boot.entries_of(record), recipe.tohost, 120)
    findings = boot.run_findings(observation, record)
    findings += boot.against_expected(observation,
                                      cast("dict[str, str]", record["image"])["sha256"],
                                      recipe.expected)
    ensure(findings == [], f"the fixture's reference run reproduces: {findings}")


def cases() -> list[Case]:
    return [Case("contract-roster-reads", _contract_roster_reads),
            Case("roster-refusals", _roster_refusals),
            Case("recipe-refusals", _recipe_refusals),
            Case("fixture-composes-to-the-measured-image", _fixture_composes_to_the_measured_image),
            Case("membership-refusals", _membership_refusals),
            Case("placement-refusals", _placement_refusals),
            Case("staleness", _staleness),
            Case("projection-and-digests", _projection),
            Case("run-findings", _run_findings),
            Case("against-expected", _against_expected),
            Case("fake-emulator-stream-timeout-and-refresh", _fake_emulator),
            Case("assembler-placement-and-imports", _assembler_placement),
            Case("command-exits", _command),
            Case("golden-emulator-reproduces-the-fixture", _golden_emulator,
                 slow=True, lane="toolchain")]
