#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Compile every reproduction here with the named opam switch's rocq and check each with
# that switch's rocqchk -silent -o, the invocation the proof gate uses. One line per
# file: its name, the compiler's exit status, the checker's exit status and the
# checker's message or "summary written". Outputs land under OUTDIR, which must be on
# the guest's own filesystem, never under /mnt/ or /tmp.
#   usage: run.sh SWITCH OUTDIR
set -u
SW=$1; OUT=$2
HERE=$(cd "$(dirname "$0")" && pwd)
FILES="Minimal MinimalTransparent VstShape VstShapeTransparent SealedNoSubmodule AliasTypedField"
mkdir -p "$OUT" && cd "$OUT" || exit 2
cp "$HERE"/*.v . || exit 2
BIN=$(opam var --switch="$SW" bin) || exit 2
{ "$BIN/rocqchk" --version; sha256sum "$BIN/rocqchk"; "$BIN/rocq" --version; sha256sum ./*.v; } > tools.txt 2>&1
for f in $FILES; do
  opam exec --switch="$SW" -- rocq c -q -Q . Repro "$f.v" > "$f.compile.log" 2>&1; c=$?
  k=n/a; msg=
  if [ "$c" -eq 0 ]; then
    opam exec --switch="$SW" -- /usr/bin/time -v -o "$f.time" "$BIN/rocqchk" -silent -o -Q . Repro "Repro.$f" > "$f.stdout" 2> "$f.stderr"; k=$?
    if [ "$k" -eq 0 ]; then msg="summary written"; else msg=$(grep -v 'Running as root' "$f.stderr" | head -3 | tr -s ' \n' ' '); fi
  else
    msg="rocq c failed"
  fi
  printf '%s\trocq c %s\trocqchk %s\t%s\n' "$f" "$c" "$k" "$msg"
done
