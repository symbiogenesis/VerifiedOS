#!/bin/sh
# The R-05-163 assumption gate, wired ahead of the first closing theorem as
# R-05-168 requires. It compiles every shipped proof artifact and compares the
# mechanically enumerated assumption set of each constant the artifact prints
# (its trailing Print Assumptions block) against the declared set, which
# R-05-164 reads from the register: the admission axioms of R-06-011, the
# bootstrap root of R-06-014, and the Ax ledger of R-18-031(c). None of those
# is authored yet, so the declared set is empty and the only passing output is
# "Closed under the global context". When the register's declared set gains an
# entry, this gate grows an allowlist read from it, never from the development.
#
# An admitted lemma, an unresolved obligation, a locally declared parameter,
# or any axiom fails this gate rather than shipping green.
#
# Needs coqc on PATH. From Windows: wsl -d Ubuntu -e sh tools/proof-gate.sh
set -eu
cd "$(dirname "$0")/.."

# The statement artifact compiles first because every companion imports it;
# the rest follow in name order. -Q roots the logical path so a companion's
# Require Import resolves to the .vo built here, never to an installed one.
out=$(coqc -q -Q proofs '' proofs/ApexTheorem.v)
for f in proofs/*.v; do
    [ "$f" = "proofs/ApexTheorem.v" ] && continue
    out="$out
$(coqc -q -Q proofs '' "$f")"
done

bad=$(printf '%s\n' "$out" | grep -v '^Closed under the global context$' | grep -v '^[[:space:]]*$' || :)
closed=$(printf '%s\n' "$out" | grep -c '^Closed under the global context$' || :)

if [ -n "$bad" ]; then
    echo "FAIL: an assumption outside the declared set, which is empty (R-05-164):"
    printf '%s\n' "$bad"
    exit 1
fi
if [ "$closed" -eq 0 ]; then
    echo "FAIL: no constant was enumerated; the artifact must end in Print Assumptions"
    exit 1
fi
echo "ok: $closed constant(s), each closed under the global context"
