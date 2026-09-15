# SPDX-License-Identifier: Apache-2.0
"""Bounded native sanity vectors for the emitted Fiat headers, not target refinement."""

import argparse
import ctypes
import hashlib
import json
import random
import subprocess
from pathlib import Path

HARNESS = r'''
#include "25519_32.h"
#include "p256_32.h"
void probe25519(unsigned op, uint8_t out[32], const uint8_t a[32], const uint8_t b[32]) {
  fiat_25519_tight_field_element x, y, z;
  fiat_25519_loose_field_element loose;
  fiat_25519_from_bytes(x, a); fiat_25519_from_bytes(y, b);
  switch (op) {
  case 0: fiat_25519_carry_mul(z, x, y); break;
  case 1: fiat_25519_carry_square(z, x); break;
  case 2: fiat_25519_add(loose, x, y); fiat_25519_carry(z, loose); break;
  case 3: fiat_25519_sub(loose, x, y); fiat_25519_carry(z, loose); break;
  case 4: fiat_25519_opp(loose, x); fiat_25519_carry(z, loose); break;
  case 5: fiat_25519_selectznz(z, 0, x, y); break;
  case 6: fiat_25519_selectznz(z, 1, x, y); break;
  case 7: fiat_25519_carry(z, x); break;
  default: fiat_25519_carry_scmul_121666(z, x); break;
  }
  fiat_25519_to_bytes(out, z);
}
void probep256(unsigned op, uint8_t out[32], const uint8_t a[32], const uint8_t b[32]) {
  fiat_p256_non_montgomery_domain_field_element x, y, normal;
  fiat_p256_montgomery_domain_field_element mx, my, z;
  fiat_p256_from_bytes(x, a); fiat_p256_from_bytes(y, b);
  fiat_p256_to_montgomery(mx, x); fiat_p256_to_montgomery(my, y);
  switch (op) {
  case 0: fiat_p256_mul(z, mx, my); break;
  case 1: fiat_p256_square(z, mx); break;
  case 2: fiat_p256_add(z, mx, my); break;
  case 3: fiat_p256_sub(z, mx, my); break;
  case 4: fiat_p256_opp(z, mx); break;
  case 5: fiat_p256_selectznz(z, 0, mx, my); break;
  case 6: fiat_p256_selectznz(z, 1, mx, my); break;
  case 7: fiat_p256_selectznz(z, 0, mx, mx); break;
  default: fiat_p256_set_one(z); break;
  }
  fiat_p256_from_montgomery(normal, z); fiat_p256_to_bytes(out, normal);
}
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if not work.is_relative_to(Path("/root/build")):
        parser.error("--work-dir must be in the native /root/build lane")
    work.mkdir(parents=True, exist_ok=True)
    folder = Path(__file__).resolve().parent / "generated/fiat-crypto"
    source = work / "fiat-vectors.c"
    library = work / "fiat-vectors.so"
    source.write_text(HARNESS, encoding="utf-8")
    command = [args.cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
               "-Wno-unused-function", "-shared", "-fPIC", "-I", str(folder),
               str(source), "-o", str(library)]
    subprocess.run(command, cwd=work, check=True)
    native = ctypes.CDLL(str(library))
    byte_array = ctypes.c_uint8 * 32
    results = {}
    for name, modulus in [("25519", 2**255 - 19),
                          ("p256", 2**256 - 2**224 + 2**192 + 2**96 - 1)]:
        rng = random.Random(0xF1A7)  # noqa: S311 - reproducible test vectors, never keys
        edges = [0, 1, 2, modulus - 1, modulus - 2, 2**31, 2**32 - 1,
                 2**32, 2**64 - 1, 2**128, modulus // 2]
        pairs = [(a, b) for a in edges for b in edges]
        pairs += [(rng.randrange(modulus), rng.randrange(modulus)) for _ in range(256)]
        function = getattr(native, "probe" + name)
        function.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_uint8),
                             ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint8)]
        function.restype = None
        checked = 0
        for a, b in pairs:
            aa = byte_array.from_buffer_copy(a.to_bytes(32, "little"))
            bb = byte_array.from_buffer_copy(b.to_bytes(32, "little"))
            expected = [a*b, a*a, a+b, a-b, -a, a, b, a,
                        a*121666 if name == "25519" else 1]
            for op, value in enumerate(expected):
                out = byte_array()
                function(op, out, aa, bb)
                actual = int.from_bytes(bytes(out), "little")
                if actual != value % modulus:
                    raise AssertionError((name, op, a, b, actual, value % modulus))
                checked += 1
        results[name] = {"pairs": len(pairs), "operation_results": checked,
                         "header_sha256": hashlib.sha256((folder / (name + "_32.h")).read_bytes()).hexdigest()}
    report = {"compiler": subprocess.check_output([args.cc, "--version"], text=True).splitlines()[0],
              "command": command, "fields": results,
              "scope": "canonical inputs below p; multiply, square, add, subtract, negate, both selects, serialization round trip, 121666 scaling or Montgomery one; no divstep or target/constant-time claim"}
    (work / "fiat-vectors.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())