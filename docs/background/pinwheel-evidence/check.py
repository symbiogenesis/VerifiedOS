#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exact feasibility check for the pinwheel Kernel Conjecture counterexample.

A state records each task's age, the slots since its last execution, starting
from all zeros. Scheduling task j resets its age and increments the others; the
move is legal when every resulting age i is below a_i. An infinite schedule
meeting every window of a_i consecutive slots, the initial windows included,
exists exactly when an infinite legal path leaves the all-zero state. The check
enumerates the reachable states and repeatedly deletes states with no surviving
successor.
"""

import sys
from collections import deque

PREFIX = (3, 4, 5, 20, 22)

# Last period -> (feasible, reachable states from the all-zero start).
EXPECTED = {
    32: (False, 50881),
    35: (False, 56284),
    36: (True, 58085),
}

# A 36-slot periodic word for (3, 4, 5, 20, 22, 36); task indices from 0.
WITNESS = (
    0, 2, 1, 0, 1, 2, 0, 5, 1, 0, 2, 0, 1, 3, 0, 2, 1, 0,
    1, 2, 0, 4, 1, 0, 2, 0, 1, 2, 0, 3, 1, 0, 2, 0, 1, 4,
)

# Small instances with known answers.
CONTROLS = {
    (2, 3): True,
    (2, 4, 4): True,
    (3, 3, 3): True,
    (2, 3, 12): False,
}


def successors(state, periods):
    out = []
    for j in range(len(periods)):
        nxt = tuple(0 if i == j else age + 1 for i, age in enumerate(state))
        if all(age < period for age, period in zip(nxt, periods)):
            out.append(nxt)
    return out


def feasible(periods):
    start = tuple(0 for _ in periods)
    succ = {start: successors(start, periods)}
    queue = deque([start])
    while queue:
        for t in succ[queue.popleft()]:
            if t not in succ:
                succ[t] = successors(t, periods)
                queue.append(t)
    pred = {s: [] for s in succ}
    outdeg = {}
    for s, ns in succ.items():
        outdeg[s] = len(ns)
        for t in ns:
            pred[t].append(s)
    dead = deque(s for s, d in outdeg.items() if d == 0)
    removed = set()
    while dead:
        s = dead.popleft()
        if s in removed:
            continue
        removed.add(s)
        for p in pred[s]:
            if p not in removed:
                outdeg[p] -= 1
                if outdeg[p] == 0:
                    dead.append(p)
    return start not in removed, len(succ)


def word_serves(word, periods):
    """Whether repeating word meets every window, the initial ones included."""
    n = len(word)
    for task, period in enumerate(periods):
        slots = [t for t, x in enumerate(word) if x == task]
        if not slots or slots[0] >= period:
            return False
        for here, there in zip(slots, slots[1:] + [slots[0] + n]):
            if there - here > period:
                return False
    return True


def main():
    failures = []
    for periods, want in CONTROLS.items():
        got = feasible(periods)[0]
        print(f"control {periods}: feasible={got}")
        if got != want:
            failures.append(f"control {periods}")
    for last, want in EXPECTED.items():
        got = feasible(PREFIX + (last,))
        print(f"{PREFIX + (last,)}: feasible={got[0]} reachable={got[1]}")
        if got != want:
            failures.append(f"b = {last}")
    if not word_serves(WITNESS, PREFIX + (36,)):
        failures.append("witness for b = 36")
    if word_serves(WITNESS, PREFIX + (35,)):
        failures.append("witness unexpectedly serves b = 35")
    print("witness serves b = 36:", word_serves(WITNESS, PREFIX + (36,)))
    if failures:
        print("MISMATCH:", ", ".join(failures))
        return 1
    print("all results match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
