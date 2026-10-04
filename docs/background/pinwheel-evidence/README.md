# Exact check of the pinwheel Kernel Conjecture counterexample

This directory retains the independent check behind the counterexample recorded in
the [open mathematics survey](../open-math-conjectures.md#pinwheel-scheduling-certificates-and-complexity).
Gąsieniec, Smith and Wild's Conjecture 2.3 asserts that every schedulable
`k`-task instance is dominated by a schedulable one whose largest period is at
most `2^(k-1)`. The [counterexample repository](https://github.com/MathIsEvenEasier/pinwheel-kernel-counterexample/tree/08f48090c39bf665a0bce7a044e7fcab001f8e17)
proposes `(3,4,5,20,22,36)`; this check recomputes the finite facts it needs
without using that repository's code or certificates.

From the repository root, with Python 3.10 or later:

```console
python docs/background/pinwheel-evidence/check.py
```

[check.py](check.py) explores the age-state graph from the all-zero state, in
which every window of `a_i` consecutive slots, the initial windows included, must
contain task `i`. An instance is schedulable exactly when an infinite legal path
leaves that state. The script requires `(3,4,5,20,22,32)` and `(3,4,5,20,22,35)`
to have no such path, with 50,881 and 56,284 reachable states, `(3,4,5,20,22,36)`
to have one, and a 36-slot periodic word to serve `(3,4,5,20,22,36)` but not
`(3,4,5,20,22,35)`. Four small instances with known answers serve as positive and
negative controls. The script exits nonzero on any mismatch.

Lowering a period only adds constraints, so infeasibility at `b = 35` covers every
`b <= 35`, and every instance dominating `(3,4,5,20,22,36)` with largest period
at most `32` is infeasible. The check establishes these finite facts only. It
neither replays the repository's Lean proofs nor bears on the complexity of
pinwheel feasibility.
