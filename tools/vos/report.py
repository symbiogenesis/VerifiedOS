"""The reporting convention every check shares.

One rule, one verdict, one line. A rule that finds nothing prints what it decided;
a rule that finds something prints how many and then each finding, indented under
it. Nothing else is printed by a check, so a run reads as a list of decisions and a
person scanning it sees only the rules that bit.

Output is accumulated rather than streamed. The run is fast enough that streaming
buys nothing, and accumulating is what lets the mutation selftest call a whole run
in-process and read its verdict back as data instead of re-parsing a subprocess's
stdout.
"""


class Reporter:
    """Collects a run's output and counts its findings."""

    def __init__(self) -> None:
        self.findings = 0
        self.out: list[str] = []

    def line(self, text: str = "") -> None:
        self.out.append(text)

    def report(self, rule: str, label: str, items, ok: str = "", pad: str = "") -> None:
        """Decide one rule.

        `items` is whatever the check produced; falsy members are dropped, because a
        check that builds its findings inside a comprehension over a larger set
        yields `None` for every member it cleared.
        """
        found = [str(i) for i in items if i]
        if found:
            self.findings += len(found)
            self.out.append(f"{pad}FAIL {rule}: {len(found)} {label}")
            self.out.extend(f"{pad}       {f}" for f in found)
        else:
            self.out.append(f"{pad}ok {rule}: {ok or label}")

    def failed_rules(self) -> list[str]:
        """The rule ids this run reported, so a caller asserts against the verdict
        rather than against the prose."""
        seen = []
        for text in self.out:
            stripped = text.lstrip()
            if stripped.startswith("FAIL "):
                rule = stripped[5:].split(":", 1)[0]
                if rule not in seen:
                    seen.append(rule)
        return sorted(seen)
