# SPDX-License-Identifier: Apache-2.0
"""Rule reporting and formatting helpers shared across checker rules.

The `FAIL `, `ok `, and `fixed:` prefixes and the seven-space finding indent are
parsed by [vos/cli/selftest.py](cli/selftest.py).
"""

from collections.abc import Iterable


class Reporter:
    """Collect a checker run's output lines, rule decisions, and finding counts."""

    def __init__(self) -> None:
        self.findings = 0
        self.out: list[str] = []
        self.decisions: list[str] = []

    def line(self, text: str = "") -> None:
        self.out.append(text)

    def report(self, rule: str, label: str, items: Iterable[object],
               ok: str = "", pad: str = "", count: int | None = None) -> None:
        """Record a rule's decision and append its formatted verdict and findings.

        Falsy items are ignored. `count` overrides `len(found)` when `items` contains
        grouped summary lines rather than one line per finding (as in `typecheck.py`).
        """
        self.decisions.append(rule)
        found = [str(i) for i in items if i]
        if found:
            total = len(found) if count is None else count
            self.findings += total
            self.out.append(f"{pad}FAIL {rule}: {total} {label}")
            self.out.extend(f"{pad}       {f}" for f in found)
        else:
            self.out.append(f"{pad}ok {rule}: {ok or label}")


def sites(name: str, lines: list[int], cap: int = 12) -> str:
    """Format a file name and up to `cap` 1-based line numbers."""
    shown = (", ".join(str(n) for n in lines[:cap]) + f", and {len(lines) - cap} more"
             if len(lines) > cap else ", ".join(str(n) for n in lines))
    return f"{name}: {len(lines)} line(s): {shown}"


def apart(ref: str, commit: str) -> tuple[str, str]:
    """Truncate two revision strings to at least 12 hex digits and past any shared prefix."""
    if ref == commit:
        return ref[:12], commit[:12]
    shown = max(12, next((i + 1 for i, (a, b) in enumerate(zip(ref, commit, strict=False))
                          if a != b), min(len(ref), len(commit)) + 1))
    return ref[:shown], commit[:shown]
