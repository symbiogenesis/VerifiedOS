# SPDX-License-Identifier: Apache-2.0
# Boot harness fixture, rank 3: a stand-in for the last started service, and
# not a service. The real members the supervisor starts are the storage server
# and the copy-based service, whose executable owners the roster names.
#
# It prints `S` and a newline through the HTIF terminal and ends the run with
# the HTIF exit the corpus's members write on success.

        .text
        .globl _start
_start:
        li      t1, tohost
        csetaddr c31, c8, t1
        li      t0, 0x0101000000000053
        sd      t0, 0(c31)
        li      t0, 0x010100000000000A
        sd      t0, 0(c31)

        li      t0, 1
        sd      t0, 0(c31)
halt:
        j       halt
