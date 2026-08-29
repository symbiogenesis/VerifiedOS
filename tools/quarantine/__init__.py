# SPDX-License-Identifier: Apache-2.0
"""The instruments whose decisions are deferred, and the rules that hold them.

Two whole instruments live here, each answering a specification rather than an
output, each tested and gated, and each waiting on a decision nobody can take yet:
the profile-freeze analyzer, whose ordered act falls behind the M8a gate, and the
bank-count exploration, whose hard constraint has no operands until R4 and R5
measure a macro. Nothing about either is wrong. What was wrong is that both sat in
a loop that runs before every landing, for decisions that will not be taken until
after that gate, so they were taken out of it and put here whole.

`README.md` beside this file states what each waits on and the condition that
un-quarantines it, `check-rules.md` is this directory's own rule registry, and
`gate.py` is the one command that runs everything here: the two rules over the live
tree, the floors under them, one seeded mutant per rule, this registry against the
checks carrying it, and the three test modules that moved with the instruments.

**The direction of the coupling is the whole point.** This package may read
`vos`, which is where the parses and the reporting convention live. Nothing outside
it may read this package, and rule K-83 in `vos.checks.meta` is what holds that:
the directory is importable from `tools/`, so without the rule the quarantine would
be a folder and the coupling would survive the move.
"""
