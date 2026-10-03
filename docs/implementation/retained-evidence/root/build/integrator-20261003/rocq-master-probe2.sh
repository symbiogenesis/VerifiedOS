#!/bin/bash
# Follow-up: build master's corelib through its dunestrap, then run the reproduction under master's rocq and rocqchk.
set -uo pipefail
ROOT=/root/build/integrator-20261003
SW=verifiedos-rocq-9.3.0-ocaml-5.4.1
REPRO=/mnt/c/Users/symbi/source/repos/VerifiedOS/.worktrees/q35h-20261003/tools/checker-reproductions/resolver-roots
cd "$ROOT/rocq-master" || exit 10
echo "start $(date -Is) master $(git rev-parse HEAD)"
start=$(date +%s)
opam exec --switch=$SW -- nice -n 19 make dunestrap > "$ROOT/build2.log" 2>&1 \
  && opam exec --switch=$SW -- nice -n 19 dune build -j 6 rocq-runtime.install rocq-core.install >> "$ROOT/build2.log" 2>&1
rc=$?
echo "build exit $rc after $(( $(date +%s) - start )) s"
[ $rc -eq 0 ] || { tail -40 "$ROOT/build2.log"; exit 11; }
BIN="$ROOT/rocq-master/_build/install/default/bin"
LIB="$ROOT/rocq-master/_build/install/default/lib/coq"
[ -d "$LIB" ] || LIB="$ROOT/rocq-master/_build/install/default/lib/rocq"
ls "$BIN"
sha256sum "$BIN/rocq" "$BIN/rocqchk"
WORK="$ROOT/repro"
rm -rf "$WORK"; mkdir -p "$WORK"
cp "$REPRO"/*.v "$WORK"/
cd "$WORK"
export ROCQLIB="$LIB"
"$BIN/rocq" --version
for f in Minimal MinimalTransparent VstShape VstShapeTransparent SealedNoSubmodule AliasTypedField; do
  [ -f "$f.v" ] || continue
  "$BIN/rocq" c -q -Q . Repro "$f.v" > "$f.compile.out" 2>&1
  c=$?
  "$BIN/rocqchk" -silent -o -Q . Repro "Repro.$f" > "$f.check.out" 2>&1
  k=$?
  echo "== $f: rocq c exit $c; rocqchk exit $k"
  head -c 600 "$f.compile.out"; head -c 1500 "$f.check.out"; echo
done
echo "end $(date -Is)"
