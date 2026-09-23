# SPDX-License-Identifier: Apache-2.0
# The boot-handoff harness's RoT input probe, run under
# model/config/verifiedos-rot.json. Not firmware.
#
# It reads the three device inputs the RoT's release decision takes from the
# RoT composition's own windows (model/model/sys/rot.sail) and leaves them in
# the signature region for tools/vos/boot_handoff.py: the lifecycle index, the
# entropy root's health word after the start-up tests run, and the
# image-security-version counter that is the anti-rollback floor.
#
# The golden emulator's run is one power-on with no retained OTP state, so a
# floor that earlier security updates advanced does not survive into it. The
# probe advances that counter FLOOR_ADVANCES times before reading it, which is
# the harness establishing the modeled floor through the one door that moves
# it, and the harness reports the value as probe-established.

        .equ    OTP, 0x2400000
        .equ    TRNG, 0x2500000
        .equ    CTR, 0x2600000
        .equ    FLOOR_ADVANCES, 2

        .text
        .globl _start
_start:
        cmove   c8, c1
        li      t0, OTP
        csetaddr c10, c8, t0
        li      t0, TRNG
        csetaddr c11, c8, t0
        li      t0, CTR
        csetaddr c12, c8, t0
        li      t0, begin_signature
        csetaddr c13, c8, t0

        # The lifecycle state's index.
        li      gp, 1
        ld      t1, 0(c10)
        sd      t1, 0(c13)

        # Run the start-up health tests, then read the per-source verdicts, the
        # completion bit (32) and the fail-stop latch (33).
        li      gp, 2
        sd      zero, 32(c11)
        ld      t1, 8(c11)
        sd      t1, 8(c13)

        # Establish the floor through the advance door, then read counter 0.
        li      gp, 3
        li      t2, FLOOR_ADVANCES
advance:
        beqz    t2, advanced
        sd      zero, 32(c12)
        addi    t2, t2, -1
        j       advance
advanced:
        ld      t1, 0(c12)
        sd      t1, 16(c13)

        li      t0, 1
        li      t1, tohost
        csetaddr c31, c8, t1
        sd      t0, 0(c31)
halt:
        j       halt

        .data
        .align  3
tohost:
        .dword  0
begin_signature:
        .dword  0
        .dword  0
        .dword  0
end_signature:
