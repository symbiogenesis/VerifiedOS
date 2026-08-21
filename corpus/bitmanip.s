# The bit-manipulation surface the profile adopts: `Zba`, `Zbb` and `Zbs` for
# fixed-latency address and bit arithmetic, and `Zbkb`, `Zbkc` and `Zbkx` for
# software crypto on vectorless cores (isa-profile.md §2, R-15-067, R-15-042).
#
# Single-bit only at `Zbs`: the multi-bit bitfield case is `bfext`/`bfins`,
# which is bespoke and not yet modeled, so it is absent here rather than
# assumed (R-15-067a, M0.6g).

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1

        # Zba: the shift-and-add forms, and the two that zero-extend a word.
        li      gp, 1
        li      t0, 3
        li      t1, 5
        sh1add  t2, t0, t1
        li      t3, 11
        bne     t2, t3, fail
        sh2add  t2, t0, t1
        li      t3, 17
        bne     t2, t3, fail
        sh3add  t2, t0, t1
        li      t3, 29
        bne     t2, t3, fail

        li      gp, 2
        li      t0, 0xffffffff00000001
        add.uw  t2, t0, t1
        li      t3, 6
        bne     t2, t3, fail
        slli.uw t2, t0, 4
        li      t3, 0x10
        bne     t2, t3, fail

        # Zbb: the logic-with-complement trio.
        li      gp, 3
        li      t0, 0xc
        li      t1, 0xa
        andn    t2, t0, t1
        li      t3, 4
        bne     t2, t3, fail
        orn     t2, t0, t1
        li      t3, -3
        bne     t2, t3, fail
        xnor    t2, t0, t1
        li      t3, -7
        bne     t2, t3, fail

        # The min/max pairs, which differ in signedness and in nothing else.
        li      gp, 4
        li      t0, -1
        li      t1, 1
        min     t2, t0, t1
        li      t3, -1
        bne     t2, t3, fail
        max     t2, t0, t1
        li      t3, 1
        bne     t2, t3, fail
        minu    t2, t0, t1
        li      t3, 1
        bne     t2, t3, fail
        maxu    t2, t0, t1
        li      t3, -1
        bne     t2, t3, fail

        # Rotations are XLEN-wide and the W forms are 32-wide, which is what
        # separates `rol` from `rolw` on the same operands.
        li      gp, 5
        li      t0, 1
        li      t1, 63
        rol     t2, t0, t1
        li      t3, 1
        slli    t3, t3, 63
        bne     t2, t3, fail
        ror     t2, t0, t1
        li      t3, 2
        bne     t2, t3, fail
        rori    t2, t0, 1
        li      t3, 1
        slli    t3, t3, 63
        bne     t2, t3, fail
        li      t1, 31
        rolw    t2, t0, t1
        li      t3, 1
        slli    t3, t3, 31
        sub     t3, zero, t3
        bne     t2, t3, fail

        # The counting forms.
        li      gp, 6
        li      t0, 1
        clz     t2, t0
        li      t3, 63
        bne     t2, t3, fail
        li      t0, 8
        ctz     t2, t0
        li      t3, 3
        bne     t2, t3, fail
        li      t0, 0xff
        cpop    t2, t0
        li      t3, 8
        bne     t2, t3, fail
        li      t0, 1
        clzw    t2, t0
        li      t3, 31
        bne     t2, t3, fail
        li      t0, -1
        cpopw   t2, t0
        li      t3, 32
        bne     t2, t3, fail

        # The extension forms, which are what a narrower value costs on a
        # machine whose registers are 64 bits wide.
        li      gp, 7
        li      t0, 0x80
        sext.b  t2, t0
        li      t3, -128
        bne     t2, t3, fail
        li      t0, 0x8000
        sext.h  t2, t0
        li      t3, -32768
        bne     t2, t3, fail
        li      t0, -1
        zext.h  t2, t0
        li      t3, 0xffff
        bne     t2, t3, fail

        # Byte reversal and the byte-wise OR-combine, the two forms a wire
        # format reaches for.
        li      gp, 8
        li      t0, 0x0102030405060708
        rev8    t2, t0
        li      t3, 0x0807060504030201
        bne     t2, t3, fail
        li      t0, 0x0100
        orc.b   t2, t0
        li      t3, 0xff00
        bne     t2, t3, fail
        li      t0, 1
        brev8   t2, t0
        li      t3, 0x80
        bne     t2, t3, fail

        # Zbs, single-bit and register-indexed.
        li      gp, 9
        li      t0, 0
        li      t1, 3
        bset    t2, t0, t1
        li      t3, 8
        bne     t2, t3, fail
        li      t0, 0xf
        li      t1, 1
        bclr    t2, t0, t1
        li      t3, 0xd
        bne     t2, t3, fail
        li      t1, 0
        binv    t2, t0, t1
        li      t3, 0xe
        bne     t2, t3, fail
        li      t0, 0xf0
        li      t1, 4
        bext    t2, t0, t1
        li      t3, 1
        bne     t2, t3, fail

        li      gp, 10
        li      t0, 0
        bseti   t2, t0, 3
        li      t3, 8
        bne     t2, t3, fail
        li      t0, 0xf
        bclri   t2, t0, 1
        li      t3, 0xd
        bne     t2, t3, fail
        binvi   t2, t0, 0
        li      t3, 0xe
        bne     t2, t3, fail
        li      t0, 0xf0
        bexti   t2, t0, 4
        li      t3, 1
        bne     t2, t3, fail

        # Zbkb's packing forms, which is where a wire format's fields are
        # assembled rather than shifted one at a time.
        li      gp, 11
        li      t0, 0xaaaaaaaa
        li      t1, 0xbbbbbbbb
        pack    t2, t0, t1
        li      t3, 0xbbbbbbbbaaaaaaaa
        bne     t2, t3, fail
        li      t0, 0xaa
        li      t1, 0xbb
        packh   t2, t0, t1
        li      t3, 0xbbaa
        bne     t2, t3, fail
        li      t0, 0xaaaa
        li      t1, 0xbbbb
        packw   t2, t0, t1
        li      t3, 0xffffffffbbbbaaaa
        bne     t2, t3, fail

        # Zbkc's carry-less multiply, the field arithmetic behind GHASH.
        li      gp, 12
        li      t0, 3
        li      t1, 3
        clmul   t2, t0, t1
        li      t3, 5
        bne     t2, t3, fail
        li      t0, 1
        slli    t0, t0, 63
        li      t1, 2
        clmulh  t2, t0, t1
        li      t3, 1
        bne     t2, t3, fail

        # Zbkx's crossbar permutations, which is what makes a table-free
        # substitution constant-time.
        li      gp, 13
        li      t0, 0x0706050403020100
        li      t1, 0x0101010101010101
        xperm8  t2, t0, t1
        li      t3, 0x0101010101010101
        bne     t2, t3, fail
        li      t1, 0
        xperm8  t2, t0, t1
        bnez    t2, fail
        li      t0, 0xfedcba9876543210
        li      t1, 0
        xperm4  t2, t0, t1
        bnez    t2, fail

        li      gp, 0
        j       pass

fail:
        slli    t0, gp, 1
        ori     t0, t0, 1
        j       exit
pass:
        li      t0, 1
exit:
        li      t1, tohost
        csetaddr c31, c8, t1
        sd      t0, 0(c31)
halt:
        j       halt

        .data
        .align  3
tohost:
        .dword  0
