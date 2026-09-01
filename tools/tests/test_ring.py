# SPDX-License-Identifier: Apache-2.0
"""The ring emitter's two owners, and K-89's fail-closed reading of them.

`vos/cli/ring.py` is the only tool in this directory whose output a rule holds byte
for byte, so what is worth pinning here is not the bytes, which K-89 already decides,
but the three claims the emitter makes about *where they came from*.

The first is that the states the artifact carries are read out of the register's own
sentences rather than off positions in its chain: a figure computed as an ordinal
difference is true of today's register and stays true of one it no longer describes,
which is this repository's *computation that encodes its own answer*. The first two
cases move a state and require the figure to move with it.

The second is that an owner the emitter cannot read is refused rather than
mis-emitted, at each of the shapes `owned()` and `declaration()` name.

The third is K-89's own: a generator that raises is that rule's finding and never that
rule's crash. `checks/ring.py` catches the emitter's refusal and every other exception
alike, and the last case holds it to that by handing it a declaration whose shape no
guard is written against.
"""

import json
from collections.abc import Callable
from typing import Any

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos.checks import Context
from vos.checks import ring as rule
from vos.cli import ring
from vos.register import Register, read_artifacts
from vos.report import Reporter

# The lifecycle chain the register states, and the same chain with one state inserted
# between the two ends of the malformed step. Every skip case below is that pair.
_CHAIN = "Free → Writing → Submitted → Accepted → Terminal → Reclaimed"
_LONGER = "Free → Writing → Submitted → Accepted → Failed → Terminal → Reclaimed"

_ANSWERS = "`cancelled`, `too_late` and `not_live`"


def _register(chain: str = _CHAIN, malformed: str = "Submitted", to: str = "Terminal",
              unstarted: str = "Submitted", cancels: str = _ANSWERS) -> Register:
    """A register carrying exactly the four entries `owned()` reads."""
    return Register(body={
        ring.STATUS_ENTRY: "a status from the closed common set (`ok`, `refused`, "
                           "`invalid`, `cancelled`)",
        ring.LIFECYCLE_ENTRY: f"the monotone lifecycle {chain}: a malformed request "
                              f"moves from {malformed} directly to {to} without "
                              f"acquiring device authority",
        ring.FULL_RING_ENTRY: "submission against a full request ring has the sole "
                              "typed result `would_block`",
        ring.CANCEL_ENTRY: f"a target still {unstarted} completes cancelled unstarted; "
                           f"the answers are {cancels}",
    })


def _declaration() -> dict[str, Any]:
    """The tracked declaration, so the shape cases mutate the real one."""
    root = corpus_mod.find_root()
    text = (root / ring.DECLARATION).read_text(encoding="utf-8")
    parsed: dict[str, Any] = json.loads(text)
    return parsed


def _refused(fn: Callable[[], object], why: str) -> None:
    """`fn` must raise the emitter's own refusal and not anything else."""
    try:
        fn()
    except ring.RingError:
        return
    raise AssertionError(why)


def _a_state_inserted_moves_the_skip() -> None:
    # The defect this case exists for: `states.index(states[4]) - states.index(states[2])`
    # is 4 - 2 for any chain of distinct states, so it answers 2 whatever the register
    # says. With a state inserted before the terminal one, the true skip is 3.
    short = ring.owned(_register())
    ensure(ring._skip(short) == 2,
           f"the register's own chain gives a skip of 2, got {ring._skip(short)}")
    longer = ring.owned(_register(chain=_LONGER))
    ensure(ring._skip(longer) == 3,
           f"a state inserted between the two the entry names must move the skip to "
           f"3, got {ring._skip(longer)}")


def _the_named_states_are_read_not_counted() -> None:
    own = ring.owned(_register(chain=_LONGER))
    ensure(own.malformed_from == "Submitted" and own.malformed_to == "Terminal",
           f"the step's ends read back as {own.malformed_from} -> {own.malformed_to}, "
           f"where the entry's own sentence names Submitted and Terminal")
    ensure(ring._live(own) == "Accepted",
           f"the live-and-started state is the successor of the state the cancellation "
           f"entry names, got {ring._live(own)}")
    moved = ring.owned(_register(chain=_LONGER, unstarted="Accepted"))
    ensure(ring._live(moved) == "Failed",
           f"moving the state that entry names must move the successor, got "
           f"{ring._live(moved)}")


def _owned_fails_closed_on_each_shape() -> None:
    shapes = {
        "no arrow chain": _register(chain="Free, Writing, Submitted"),
        "no malformed step": _register(malformed="", to=""),
        "a step naming a state off the chain": _register(malformed="Drafting"),
        "a step that skips nothing": _register(malformed="Accepted", to="Terminal"),
        "two cancellation answers": _register(cancels="`cancelled` and `not_live`"),
        "no entries at all": Register(body={}),
    }
    for why, reg in shapes.items():
        _refused(lambda held=reg: ring.owned(held),
                 f"owned() accepted a register with {why}")


def _declaration_names_every_key_the_emitter_reads() -> None:
    # The gap this case closes: `label_levels` was read at emit time and named by no
    # guard, so a declaration without it raised KeyError out of the checker instead of
    # being refused. Each key the emitter reads is dropped in turn.
    base = _declaration()
    with sandbox_tree({ring.DECLARATION: json.dumps(base)}) as root:
        path = root / ring.DECLARATION
        for key in ring.DECL_KEYS:
            path.write_text(json.dumps({k: v for k, v in base.items() if k != key}),
                            encoding="utf-8")
            _refused(lambda held=root: ring.declaration(held),
                     f"declaration() accepted a declaration with no `{key}`")
        for key in ring.ENCODING_KEYS:
            short = dict(base)
            short["encoding"] = {k: v for k, v in base["encoding"].items() if k != key}
            path.write_text(json.dumps(short), encoding="utf-8")
            _refused(lambda held=root: ring.declaration(held),
                     f"declaration() accepted a declaration with no encoding `{key}`")
        for key in ring.OP_KEYS:
            short = dict(base)
            short["operations"] = [{k: v for k, v in op.items() if k != key}
                                   for op in base["operations"]]
            path.write_text(json.dumps(short), encoding="utf-8")
            _refused(lambda held=root: ring.declaration(held),
                     f"declaration() accepted an operation with no `{key}`")
        path.write_text("{ not json", encoding="utf-8")
        _refused(lambda: ring.declaration(root),
                 "declaration() accepted a file that is not JSON")


def _the_rule_reports_rather_than_crashes() -> None:
    # A declaration carrying every key the guards name, whose scalar width is a word
    # rather than a number: no guard is written against it, `emit()` raises something
    # other than a RingError, and K-89's claim is that this is one red rule and not a
    # dead run.
    base = _declaration()
    base["operations"][0]["scalars"] = [
        {"name": "extent_index", "width_bytes": "four", "validated_at_use": True}]
    files = {
        ring.DECLARATION: json.dumps(base),
        ring.ARTIFACT: "(* whatever a person typed *)\n",
        "docs/requirements-register.md": "# R\n\n## 1\n\n**R-01-001** MUST x.\n"
                                         "· Trace: t\n",
    }
    with sandbox_tree(files) as root:
        corpus = corpus_mod.load(root)
        ctx = Context(root=root, corpus=corpus, reg=_register(),
                      art=read_artifacts(corpus), rep=Reporter())
        rule.run(ctx)
        said = "\n".join(ctx.rep.out)
    ensure("FAIL K-89" in said,
           f"a generator that raises must be this rule's finding; the rule said:\n{said}")
    ensure("cannot be emitted" in said,
           f"the finding must name the emitter's failure, got:\n{said}")


def cases() -> list[Case]:
    return [
        Case("a-state-inserted-moves-the-skip", _a_state_inserted_moves_the_skip),
        Case("the-named-states-are-read-not-counted",
             _the_named_states_are_read_not_counted),
        Case("owned-fails-closed-on-each-shape", _owned_fails_closed_on_each_shape),
        Case("declaration-names-every-key-the-emitter-reads",
             _declaration_names_every_key_the_emitter_reads),
        Case("the-rule-reports-rather-than-crashes",
             _the_rule_reports_rather_than_crashes),
    ]
