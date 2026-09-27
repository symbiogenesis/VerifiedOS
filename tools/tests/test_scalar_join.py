# SPDX-License-Identifier: Apache-2.0
"""Joined wire chronology must come from actual serialized target records."""

from tests.harness import Case, ensure
from vos import scalar_join


def wire_publication_order() -> None:
    def read(lines: list[str]) -> scalar_join.WireTrace:
        return scalar_join.wire_trace(lines, request=0x1000, acknowledgment=0x2000,
                                      request_words=2, acknowledgment_words=2,
                                      supervisor_entry=0x8000, supervisor_top=0x9000)

    ensure(read([]) == scalar_join.WireTrace((), (), ()), "empty trace created a lifecycle event")
    request = ["I 1 0000000000008000 00000013\n", "W 1008 8 0 2\n", "W 1000 8 0 1\n"]
    early = [*request, "W 2008 1 0 5\n", "W 2000 8 0 1\n", "R 2000 8 0 1\n"]
    parsed = read(early)
    ensure(parsed.requests[0].words == (1, 2), "request cells lost their publication order")
    ensure(parsed.acknowledgments[0].words == (1, 5), "ack byte writes were not reconstructed")
    ensure(not parsed.later_reads, "same-reaction read passed as later acknowledgment consumption")
    later = read([*early, "I 2 0000000000008000 00000013\n", "R 2000 8 0 1\n",
                  "W 2000 8 0 1\n"])
    ensure(later.later_reads == (1,) and len(later.acknowledgments) == 1,
           "refreshing an acknowledgment invented a second effect result")


def cases() -> list[Case]:
    return [Case("joined request publication and later acknowledgment chronology", wire_publication_order)]
