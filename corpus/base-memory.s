# Loads and stores at every width, through a capability derived from the root
# data capability the machine resets with in `c8` (postlude/step_ext.sail).
#
# There is no other way to write the program: an integer in a base register is
# an untagged capability and faults where the access is, so `li` names the
# address and `csetaddr` turns the authority that spans the space into one at
# that address (R-15-001c, core/addr_checks.sail). Every corpus program that
# touches memory opens with the same two instructions.

        .text
        .globl _start
_start:
        # c1 holds the store-side root and is also the link register, so a
        # program that calls would overwrite its own authority. Every corpus
        # program moves it out first and names c8 thereafter.
        cmove   c8, c1
        li      t0, scratch
        csetaddr c10, c8, t0

        li      gp, 1
        li      t1, 0x0123456789abcdef
        sd      t1, 0(c10)
        ld      t2, 0(c10)
        bne     t1, t2, fail

        # Little-endian, which is what says the doubleword above landed the way
        # the image was written rather than reversed by the harness.
        li      gp, 2
        lbu     t2, 0(c10)
        li      t3, 0xef
        bne     t2, t3, fail
        lbu     t2, 7(c10)
        li      t3, 0x01
        bne     t2, t3, fail

        # A word load sign-extends and `lwu` does not, which is the one place
        # the two differ and the reason both encodings exist.
        li      gp, 3
        li      t1, 0x80000000
        sw      t1, 8(c10)
        lw      t2, 8(c10)
        li      t3, -2147483648
        bne     t2, t3, fail
        lwu     t2, 8(c10)
        li      t3, 0x80000000
        bne     t2, t3, fail

        li      gp, 4
        li      t1, 0x8001
        sh      t1, 16(c10)
        lh      t2, 16(c10)
        li      t3, -32767
        bne     t2, t3, fail
        lhu     t2, 16(c10)
        li      t3, 0x8001
        bne     t2, t3, fail

        li      gp, 5
        li      t1, 0x81
        sb      t1, 24(c10)
        lb      t2, 24(c10)
        li      t3, -127
        bne     t2, t3, fail
        lbu     t2, 24(c10)
        li      t3, 0x81
        bne     t2, t3, fail

        # A negative displacement reaches backwards from the authority's
        # address, which is the offset arithmetic and not a second addressing
        # mode: the authority is the same capability either way.
        li      gp, 6
        li      t0, scratch + 32
        csetaddr c11, c8, t0
        li      t1, 0x5a5a
        sd      t1, -32(c11)
        ld      t2, 0(c10)
        bne     t1, t2, fail

        # A narrowed authority still reaches what it was narrowed to. The
        # out-of-bounds half of this is a fault and is `cap-trap`'s.
        li      gp, 7
        csetboundsimm c12, c10, 16
        li      t1, 0x1234
        sd      t1, 8(c12)
        ld      t2, 8(c10)
        bne     t1, t2, fail
        cgetlen t2, c12
        li      t3, 16
        bne     t2, t3, fail

        # Every store width writes exactly its own bytes and leaves the rest of
        # the granule standing.
        li      gp, 8
        li      t1, -1
        sd      t1, 32(c10)
        sb      zero, 32(c10)
        ld      t2, 32(c10)
        li      t3, -256
        bne     t2, t3, fail
        sh      zero, 34(c10)
        ld      t2, 32(c10)
        li      t3, 0xffffffff0000ff00
        bne     t2, t3, fail

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
scratch:
        .space  64
