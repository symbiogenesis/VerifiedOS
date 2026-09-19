# SPDX-License-Identifier: Apache-2.0
"""Refusal controls for external command membership and explicit audit coverage."""

from collections.abc import Callable

from tests.harness import Case, ensure
from vos.compute_audit import END, START, VERSIONS, audit_commands, compare, core_commands


def _registry() -> bytes:
    features = [f'<feature api="opencl" number="{version}"><require>'
                f'<command name="clExample{index}"/></require></feature>'
                for index, version in enumerate(sorted(VERSIONS))]
    return ("<registry>" + "".join(features) + "</registry>").encode()


def _document() -> str:
    rows = [f"| `clExample{index}` | F/E U(f) | Defined output and lifetime. |"
            for index in range(len(VERSIONS))]
    return "\n".join([START, *rows, END])


def _refused(action: Callable[[], object]) -> None:
    try:
        action()
    except ValueError:
        return
    raise AssertionError("invalid inventory or audit was accepted")


def _membership() -> None:
    registry, document = _registry(), _document()
    result = compare(registry, document, require_pin=False)
    ensure(result.complete, "all explicit core names covered")
    missing = compare(registry, document.replace("`clExample0`", "unspecified"),
                      require_pin=False)
    ensure(missing.missing == ("clExample0",), "missing explicit subject coverage")
    unknown = compare(registry, document.replace("`clExample0`", "`clInvented`"),
                      require_pin=False)
    ensure(unknown.unknown == ("clInvented",), "unknown API cannot conceal omission")
    duplicate = compare(registry, document.replace(END, "| `clExample0` | U(f) | output |\n" + END),
                        require_pin=False)
    ensure(duplicate.duplicate == ("clExample0",), "two owners cannot silently count twice")
    outside = document.replace("`clExample0`", "unspecified") + "\n`clExample0`"
    ensure(compare(registry, outside, require_pin=False).missing == ("clExample0",),
           "a citation outside the feature cell establishes no coverage")
    prose = document.replace("`clExample0`", "unspecified", 1).replace(
        "Defined output and lifetime.", "`clExample0` is a citation.", 1)
    ensure(compare(registry, prose, require_pin=False).missing == ("clExample0",),
           "a citation in the observable cell cannot supply membership")


def _closed_oracle() -> None:
    registry = _registry()
    _refused(lambda: compare(registry, _document()))
    _refused(lambda: core_commands(b"<registry/>"))
    _refused(lambda: core_commands(registry.replace(b'number="3.0"', b'number="3.1"')))
    _refused(lambda: core_commands(registry.replace(b'number="3.0"', b'number="2.2"')))
    _refused(lambda: core_commands(registry.replace(b'name="clExample0"', b'name=""')))
    _refused(lambda: core_commands(registry.replace(b'<command name="clExample0"/>', b'')))
    extensions = registry.replace(b"</registry>",
                                  b'<extensions><command name="clExtension"/></extensions></registry>')
    ensure("clExtension" not in core_commands(extensions), "extension is not core by adjacency")


def _closed_audit() -> None:
    document = _document()
    _refused(lambda: audit_commands(document.replace(START, "")))
    _refused(lambda: audit_commands(document + "\n" + START))
    _refused(lambda: audit_commands(END + "\n" + START))
    _refused(lambda: audit_commands(START + "\n" + END))
    _refused(lambda: audit_commands(document.replace("F/E U(f)", "unreviewed", 1)))
    _refused(lambda: audit_commands(document.replace("Defined output and lifetime.", "", 1)))
    _refused(lambda: audit_commands(document.replace("F/E U(f)", "U(f) | extra", 1)))


def cases() -> list[Case]:
    return [Case("explicit-membership-and-negative-controls", _membership),
            Case("pinned-complete-oracle", _closed_oracle),
            Case("closed-audit-boundaries-and-rows", _closed_audit)]
