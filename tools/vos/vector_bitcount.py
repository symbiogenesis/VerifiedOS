# SPDX-License-Identifier: Apache-2.0
"""Generate bounded Zvbb architectural cases from fixed-width integer mathematics."""

from pathlib import Path

WIDTHS = (8, 16, 32, 64)
SAIL = "model/model/unit_tests/test_vector_bitcount.sail"
CORPUS = "corpus/vector-bitcount.s"
ARTIFACTS = (SAIL, CORPUS)
OPERATIONS = ("vclz.v", "vctz.v", "vcpop.v")
# A bounded harness allocation, checked against the realized geometry at runtime.
OUTPUT_BYTES = 4096


def counts(width: int, value: int) -> tuple[int, int, int]:
    """Return CLZ, CTZ and population count after modulo-width normalization."""
    if isinstance(width, bool) or not isinstance(width, int):
        raise TypeError("vector bitcount width must be an integer")
    if width not in WIDTHS:
        raise ValueError("vector bitcount requires SEW 8, 16, 32 or 64")
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("vector bitcount input must be an integer")
    value &= (1 << width) - 1
    return (width - value.bit_length(),
            width if value == 0 else (value & -value).bit_length() - 1,
            value.bit_count())


def values(width: int) -> tuple[int, ...]:
    """Exhaust bytes; sample larger lanes at every bit and run boundary."""
    counts(width, 0)
    if width == 8:
        return tuple(range(256))
    mask = (1 << width) - 1
    result = {0, mask, sum(1 << bit for bit in range(0, width, 2)),
              sum(1 << bit for bit in range(1, width, 2))}
    for bit in range(width):
        result.update((1 << bit, (1 << bit) - 1, mask ^ ((1 << bit) - 1)))
    return tuple(sorted(result))


def geometries(width: int) -> tuple[int, ...]:
    """Legal LMUL powers for the adopted ELEN=64 vector profile."""
    counts(width, 0)
    return tuple(power for power in range(-3, 4) if (64 << max(power, 0))
                 >= width * (1 << max(-power, 0)))


def _vtype(width: int, power: int) -> int:
    return (WIDTHS.index(width) << 3) | (power & 7)


_SAIL_HELPERS = r'''
function vector_bitcount_configure(sew : bits(3), lmul : bits(3), length : range(0, vlen)) -> unit = {
  mstatus[VS] = extStatus_map(Dirty);
  vtype = Mk_Vtype(zeros());
  vtype[vsew] = sew;
  vtype[vlmul] = lmul;
  vl = to_bits(xlen, length);
}

function vector_bitcount_retire(inst : instruction) -> unit = {
  match execute(inst) {
    Retire_Success() => (),
    _ => assert(false, "a legal vector bit-count instruction must retire"),
  }
}

function vector_bitcount_instruction(kind : range(0, 2), vm : bits(1),
                                     source : vregidx, target : vregidx) -> instruction =
  match kind {
    0 => VCLZ_V(vm, source, target),
    1 => VCTZ_V(vm, source, target),
    _ => VCPOP_V(vm, source, target),
  }

val vector_bitcount_case : forall 's, 's in {8, 16, 32, 64} .
  (int('s), bits(3), bits('s), range(0, 64), range(0, 64), range(0, 64)) -> unit
function vector_bitcount_case(SEW, sew, value, clz, ctz, pop) = {
  vector_bitcount_configure(sew, 0b000, 1);
  let source = Vregidx(0b01000);
  let separate = Vregidx(0b10000);
  let expected : vector(3, range(0, 64)) = [clz, ctz, pop];
  foreach (kind from 0 to 2) {
    foreach (inplace from 0 to 1) {
      let target = if inplace == 0 then separate else source;
      V(source) = ones();
      V(separate) = ones();
      write_single_element(SEW, 0, source, value);
      vector_bitcount_retire(vector_bitcount_instruction(kind, 0b1, source, target));
      assert(read_single_element(SEW, 0, target) == to_bits(SEW, expected[kind]),
             "vector bit-count differs from the independent integer oracle");
    };
  };
  // Fixed-width subtraction includes zero: zero - one wraps to all ones.
  write_single_element(SEW, 0, source, (value - 1) & not_vec(value));
  vector_bitcount_retire(VCPOP_V(0b1, source, separate));
  assert(read_single_element(SEW, 0, separate) == to_bits(SEW, ctz),
         "the modulo-width CTZ/popcount identity must include zero");
}

val vector_bitcount_geometry : forall 's, 's in {8, 16, 32, 64} .
  (int('s), bits(3), bits(3)) -> unit
function vector_bitcount_geometry(SEW, sew, lmul) = {
  vector_bitcount_configure(sew, lmul, 0);
  let LMUL_pow = get_lmul_pow();
  let num_elem = get_num_elem(LMUL_pow, SEW);
  let real_elem = if LMUL_pow >= 0 then num_elem else num_elem / (2 ^ (0 - LMUL_pow));
  assert(real_elem >= 1);
  let source = Vregidx(0b01000);
  let target = Vregidx(0b10000);
  foreach (kind from 0 to 2) {
    foreach (mode from 0 to 2) {
      // Full zero-input count; short mask with only element zero active;
      // zero length. All other physical elements must retain the sentinel.
      let length = if mode == 0 then real_elem else if mode == 1 then min(2, real_elem) else 0;
      vector_bitcount_configure(sew, lmul, length);
      foreach (i from 0 to (num_elem - 1)) {
        write_single_element(SEW, i, source, if mode == 0 then zeros() else ones());
        write_single_element(SEW, i, target, ones());
      };
      V(zvreg) = zero_extend(0b1);
      vector_bitcount_retire(vector_bitcount_instruction(kind,
                              if mode == 1 then 0b0 else 0b1, source, target));
      foreach (i from 0 to (num_elem - 1)) {
        let active = if mode == 0 then i < real_elem else mode == 1 & i == 0;
        let expected : bits('s) = if not(active) then ones()
          else if mode == 0 then to_bits(SEW, if kind == 2 then 0 else SEW)
          else to_bits(SEW, if kind == 2 then SEW else 0);
        assert(read_single_element(SEW, i, target) == expected,
               "vector bit-count changed a masked or undisturbed tail lane");
      };
    };
  };
}
'''


def emit_sail(root: Path) -> str:
    del root
    lines = ["// SPDX-License-Identifier: BSD-2-Clause",
             "// Generated by tools/run.py vector-bitcount emit; do not edit.",
             "// R-15-055: bounded independent expected counts, not a universal proof.",
             _SAIL_HELPERS.strip(), ""]
    for width in WIDTHS:
        sew = WIDTHS.index(width)
        lines += ["$[test]", f"function test_vector_bitcount_e{width}() -> unit = {{"]
        for value in values(width):
            clz, ctz, pop = counts(width, value)
            lines.append(f"  vector_bitcount_case({width}, 0b{sew:03b}, "
                         f"0x{value:0{width // 4}x}, {clz}, {ctz}, {pop});")
        for power in geometries(width):
            lines.append(f"  vector_bitcount_geometry({width}, 0b{sew:03b}, "
                         f"0b{power & 7:03b});")
        lines += ["}", ""]
    return "\n".join(lines)


def emit_corpus(root: Path) -> str:
    del root
    lines = ["# SPDX-License-Identifier: Apache-2.0",
             "# Generated by tools/run.py vector-bitcount emit; do not edit.",
             "# R-15-055: fixed-width independent answers and decoded Zvbb forms.",
             "        .text", "        .globl _start", "_start:",
             "        cmove c8, c1", "        li t0, 0x200",
             "        csrrs zero, mstatus, t0", "        li t0, output",
             "        csetaddr c10, c8, t0"]
    serial = 0
    branch = 0

    def put(*statements: str) -> None:
        nonlocal branch
        for statement in statements:
            if statement.startswith("bne ") and statement.endswith(", fail"):
                branch += 1
                label = f"answer_ok_{branch}"
                operands = statement[4:-6]
                lines.extend((f"        beq {operands}, {label}",
                              "        j fail", label + ":"))
            else:
                lines.append("        " + statement)

    def check() -> None:
        nonlocal serial
        serial += 1
        put(f"li gp, {serial}")

    def answer(expected: int) -> None:
        put("vmv.x.s t1, v16", f"li t2, {expected}", "bne t1, t2, fail")

    for width in WIDTHS:
        put("li t0, 1", f"vsetvli t1, t0, {_vtype(width, 0)}")
        for value in values(width):
            check()
            put(f"li t0, 0x{value:x}", "vmv.v.x v8, t0")
            expected = counts(width, value)
            for operation, count in zip(OPERATIONS, expected, strict=True):
                put("vmv.v.i v16, -1", f"{operation} v16, v8")
                answer(count)
            put("li t2, 1", "vsub.vx v16, v8, t2", "li t2, -1",
                "vxor.vx v17, v8, t2", "vand.vv v16, v16, v17", "vcpop.v v16, v16")
            answer(expected[1])
        for value in (0, 1 << (width - 1), (1 << width) - 1):
            check()
            for operation, count in zip(OPERATIONS, counts(width, value), strict=True):
                put(f"li t0, 0x{value:x}", "vmv.v.x v16, t0", f"{operation} v16, v16")
                answer(count)
        store = f"vse{width}.v"
        load = {8: "lbu", 16: "lhu", 32: "lwu", 64: "ld"}[width]
        for power in geometries(width):
            init = _vtype(width, max(power, 0))
            target = _vtype(width, power)
            for kind, operation in enumerate(OPERATIONS):
                for mode in range(3):
                    check()
                    put(f"vsetvli s2, zero, {init}", "vmv.v.i v16, -1",
                        f"vmv.v.i v8, {0 if mode == 0 else -1}")
                    if mode == 0:
                        put(f"vsetvli s3, zero, {target}", f"{operation} v16, v8")
                    elif mode == 1:
                        put("vmv.v.i v0, 0", "li t0, 1", "vmv.s.x v0, t0",
                            "li t0, 2", f"vsetvli t1, t0, {target}",
                            f"{operation} v16, v8, v0.t", "li s3, 1")
                    else:
                        put("li t0, 0", f"vsetvli t1, t0, {target}",
                            f"{operation} v16, v8", "li s3, 0")
                    active = (0 if kind == 2 else width) if mode == 0 else (width if kind == 2 else 0)
                    put(f"vsetvli t1, zero, {init}", f"slli t0, s2, {(width // 8).bit_length() - 1}",
                        f"li t2, {OUTPUT_BYTES}", f"bgeu t2, t0, extent_ok_{serial}", "j fail")
                    lines.append(f"extent_ok_{serial}:")
                    put(f"{store} v16, (c10)",
                        "cmove c11, c10", "li a2, 0")
                    lines.append(f"lanes_{serial}:")
                    put(f"{load} t1, 0(c11)", f"li t2, 0x{(1 << width) - 1:x}",
                        f"bgeu a2, s3, inactive_{serial}", f"li t2, {active}")
                    lines.append(f"inactive_{serial}:")
                    put("bne t1, t2, fail", f"cincoffsetimm c11, c11, {width // 8}",
                        "addi a2, a2, 1", f"bltu a2, s2, lanes_{serial}")
    put("li gp, 0", "li t0, 1", "j exit")
    lines.append("fail:")
    put("slli t0, gp, 1", "ori t0, t0, 1")
    lines.append("exit:")
    put("li t1, tohost", "csetaddr c31, c8, t1", "sd t0, 0(c31)")
    lines.append("halt:")
    put("j halt", ".data", ".align 3")
    lines.append("tohost:")
    put(".dword 0", ".align 6")
    lines.append("output:")
    put(f".space {OUTPUT_BYTES}")
    return "\n".join(lines) + "\n"


def check(root: Path) -> list[str]:
    findings = []
    for artifact, emit in ((SAIL, emit_sail), (CORPUS, emit_corpus)):
        try:
            actual = (root / artifact).read_bytes()
        except OSError as exc:
            findings.append(f"{artifact}: {exc}")
            continue
        if actual != emit(root).encode("utf-8"):
            findings.append(f"{artifact} differs from vector-bitcount emit")
    return findings
