# SPDX-License-Identifier: Apache-2.0
"""Quarantined analysis instruments and their consistency checks.

Two instruments live here while the measurements they depend on remain deferred:
- the profile-freeze measurement analyzer ([freeze.py](freeze.py),
  [freeze-report.py](freeze-report.py)), and
- the second-class bank-count exploration ([banks.py](banks.py),
  [bank-dse.py](bank-dse.py)).

[README.md](README.md) states what each instrument waits on and the condition that
un-quarantines it. [check-rules.md](check-rules.md) is this directory's rule registry,
and [gate.py](gate.py) runs the quarantined check groups (K-58 and K-77), their
enumeration floors, the registry check, seeded mutants, and every test module under
[tests/](tests/__init__.py).

This package imports shared parsing and reporting utilities from `vos`, while K-83 in
[vos/checks/meta.py](../vos/checks/meta.py#run) forbids non-quarantine tools from
importing `quarantine`.
"""
