# SPDX-License-Identifier: Apache-2.0
# The two register-file instructions the profile adds: the conditional
# capability move and the masked clear (R-15-054a, R-15-069a).
#
# They are the two halves of one idea, which is that a merged register file
# needs operations over whole registers rather than over their integer reading.
# `cmovz`/`cmovn` write the destination whole, tag included, on the taken arm
# and leave it untouched on the other, because the zero-then-OR idiom `Zicond`
# uses has no capability form: the recombining `or` would be reconstruction from
# a bit pattern, which the profile forbids at the root (R-15-054, R-05-136).
# `cclear` writes sixteen of them to untagged NULL in one issue, which is what a
# compartment switch needs and what nothing else covers (R-15-069b).

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        li      t0, scratch
        csetaddr c10, c8, t0

        # The taken arm carries the whole register: same tag, same bounds, same
        # permissions, same object type, which `cseqx` compares in one answer.
        li      gp, 1
        cmove   c11, cnull
        li      t0, 0
        cmovz   c11, c10, t0
        cgettag t1, c11
        li      t2, 1
        bne     t1, t2, fail
        cseqx   t1, c11, c10
        li      t2, 1
        bne     t1, t2, fail

        # The untaken arm leaves the destination untouched, which is stronger
        # than leaving it unchanged in value: nothing is written, so a
        # destination that already held authority keeps its own.
        li      gp, 2
        cmove   c12, cnull
        li      t0, 1
        cmovz   c12, c10, t0
        cgettag t1, c12
        bnez    t1, fail
        cseqx   t1, c12, cnull
        li      t2, 1
        bne     t1, t2, fail

        # `cmovn` is the complementary condition on the same operands.
        li      gp, 3
        cmove   c13, cnull
        li      t0, 1
        cmovn   c13, c10, t0
        cseqx   t1, c13, c10
        li      t2, 1
        bne     t1, t2, fail

        li      gp, 4
        cmove   c14, cnull
        li      t0, 0
        cmovn   c14, c10, t0
        cseqx   t1, c14, cnull
        li      t2, 1
        bne     t1, t2, fail

        # The condition is the *integer* reading of the selector register, so a
        # register holding a tagged capability at a non-zero address is non-zero
        # and the two polarities read it alike.
        li      gp, 5
        cmove   c15, cnull
        cmovn   c15, c10, t0
        cseqx   t1, c15, cnull
        li      t2, 1
        bne     t1, t2, fail
        cmovn   c15, c10, c10
        cseqx   t1, c15, c10
        li      t2, 1
        bne     t1, t2, fail

        # A select over data is still a select: an untagged source arrives
        # untagged, so the instruction cannot mint authority any more than
        # `cmove` can.
        li      gp, 6
        li      t3, 0x1234
        cmove   c16, c10
        li      t0, 0
        cmovz   c16, c13, t0
        cgettag t1, c16
        li      t2, 1
        bne     t1, t2, fail
        cmovz   c16, ct3, t0
        cgettag t1, c16
        bnez    t1, fail
        cgetaddr t1, c16
        li      t2, 0x1234
        bne     t1, t2, fail

        # `cclear` clears exactly the registers the mask names within the half
        # `h` names, each to the all-zeroes granule that decodes as untagged
        # NULL (R-15-182). Bits 12 through 15 of the low half are a2 through a5.
        li      gp, 7
        cmove   c12, c10
        cmove   c13, c10
        cmove   c14, c10
        cmove   c15, c10
        cmove   c11, c10
        cclear  0, 0xf000
        cgettag t1, c12
        bnez    t1, fail
        cgettag t1, c15
        bnez    t1, fail
        cseqx   t1, c12, cnull
        li      t2, 1
        bne     t1, t2, fail
        cgetperm t1, c15
        bnez    t1, fail

        # And leaves every register it does not name, in this half or the other.
        li      gp, 8
        cseqx   t1, c11, c10
        li      t2, 1
        bne     t1, t2, fail
        cgettag t1, c8
        li      t2, 1
        bne     t1, t2, fail

        # The half selector moves the same sixteen positions up the file: bit 8
        # of the mask names s8 rather than a6.
        li      gp, 9
        cmove   c24, c10
        cmove   c25, c10
        cmove   c22, c10
        cclear  1, 0x0300
        cgettag t1, c24
        bnez    t1, fail
        cgettag t1, c25
        bnez    t1, fail
        cseqx   t1, c22, c10
        li      t2, 1
        bne     t1, t2, fail

        # An empty mask clears nothing, and costs what a full mask costs: the
        # clear is unconditional, so its worst case is its every case and the
        # saving it buys is off the bound rather than off the mean (R-15-069b).
        li      gp, 10
        cmove   c17, c10
        cclear  0, 0
        cclear  1, 0
        cseqx   t1, c17, c10
        li      t2, 1
        bne     t1, t2, fail

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
        .align  6
scratch:
        .space  64
