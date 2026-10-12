# SPDX-License-Identifier: Apache-2.0
"""Generate or check the independent vector bit-count qualification artifacts."""

import argparse
import subprocess
import tempfile
from pathlib import Path

from vos import env, vector_bitcount
from vos.corpus import find_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("emit", "check", "smoke"))
    args = parser.parse_args(argv)
    root = find_root()
    try:
        if args.action == "emit":
            for artifact, emit in ((vector_bitcount.SAIL, vector_bitcount.emit_sail),
                                   (vector_bitcount.CORPUS, vector_bitcount.emit_corpus)):
                (root / artifact).write_text(emit(root), encoding="utf-8", newline="\n")
            findings: list[str] = []
        elif args.action == "check":
            findings = vector_bitcount.check(root)
        else:
            findings = vector_bitcount.check(root)
            if not findings:
                return smoke()
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        findings = [str(exc)]
    if findings:
        print("FAIL vector-bitcount: " + "; ".join(findings))
        return 1
    print(f"ok vector-bitcount: {args.action} both generated artifacts")
    return 0


def smoke() -> int:
    """Compile only the oracle adapter to SMT; never build or run the whole model."""
    e = env.load()
    source, expected = vector_bitcount.smoke_source()
    directory = e.lane_root / "vector-bitcount-smoke"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        out = Path(temporary)
        script = out / "adapter.sail"
        script.write_text(source, encoding="utf-8", newline="\n")
        prefix = out / "adapter"
        done = subprocess.run(["sail", "--strict-var", "--strict-bitvector", "--strict-exponentials",
                               "--smt", "-o", str(prefix), str(script)], cwd=out, check=False,
                              timeout=60)
        if done.returncode:
            return done.returncode
        emitted = {path.name for path in out.glob("adapter_*.smt2")}
        required = {f"adapter_{name}.smt2" for name in expected}
        if emitted != required:
            raise ValueError(f"adapter SMT membership differs: missing={required - emitted}, extra={emitted - required}")
        for name, verdict in expected.items():
            done = subprocess.run(["z3", "-T:10", str(out / f"adapter_{name}.smt2")], cwd=out,
                                  capture_output=True, text=True, check=False, timeout=15)
            if done.returncode or done.stdout.strip() != verdict or done.stderr.strip():
                raise ValueError(f"{name}: expected {verdict}, exit={done.returncode}, "
                                 f"stdout={done.stdout!r}, stderr={done.stderr!r}")
            print(f"ok vector-bitcount adapter: {name} {verdict}")
    print("ok vector-bitcount smoke: all widths and operations; original mismatch reproduced")
    return 0
