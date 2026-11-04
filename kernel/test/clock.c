// SPDX-License-Identifier: Apache-2.0
/* Native boundary controls for the
 * [clock contract](../../docs/implementation/contracts/executive-clock-repair.md#acceptance).
 * This program executes the authored C; it supplies no purecap target verdict. */
#include <stdint.h>
#include <stdio.h>

#include "vos_target.h"

static unsigned failures;

static void check(int condition, const char *name)
{
  if (!condition) {
    ++failures;
    fprintf(stderr, "clock control failed: %s\n", name);
  }
}

static void refused_release(const struct vos_frame *f, const struct vos_exec *e,
                              const char *name)
{
  uint64_t output = 37;
  check(!vos_exec_release(f, e, &output) && output == 37, name);
}

static void refused_advance(const struct vos_frame *f, struct vos_exec *e,
                              const char *name)
{
  const struct vos_exec before = *e;
  check(!vos_exec_advance(f, e) && before.cursor == e->cursor &&
        before.frame_index == e->frame_index, name);
}

int main(void)
{
  struct vos_frame f = {0};
  struct vos_exec e = {0};
  uint64_t at = 37;
  check(vos_frame_validate(&f) == VOS_TABLE_EMPTY, "empty table");
  refused_release(&f, &e, "empty release");
  refused_advance(&f, &e, "empty advance");
  f.slot_count = 1;
  f.slots[0].width = 1;
  refused_release(&f, &e, "zero major frame");
  f.major_frame = 2;
  check(vos_frame_validate(&f) == VOS_OK && vos_exec_release(&f, &e, &at) &&
        at == 0, "zero is a valid instant");

  f.phase_offset = UINT64_MAX;
  f.slots[0].offset = 1;
  check(vos_frame_validate(&f) == VOS_TABLE_OVERFLOW, "initial phase overflow");
  refused_release(&f, &e, "initial release overflow");
  refused_advance(&f, &e, "invalid initial advance");
  f.phase_offset = UINT64_MAX - 1;
  check(vos_frame_validate(&f) == VOS_OK && vos_exec_release(&f, &e, &at) &&
        at == UINT64_MAX, "MAX is a valid instant");
  refused_advance(&f, &e, "next release exceeds horizon");

  f.phase_offset = 0;
  f.slots[0].offset = 0;
  e.frame_index = UINT64_MAX / 2 + 1;
  refused_release(&f, &e, "major-frame product overflow");
  f.phase_offset = 1;
  e.frame_index = UINT64_MAX / 2;
  check(vos_exec_release(&f, &e, &at) && at == UINT64_MAX,
        "product plus phase at boundary");
  f.phase_offset = 2;
  refused_release(&f, &e, "product plus phase overflow");
  f.phase_offset = 0;
  f.major_frame = 1;
  e.frame_index = UINT64_MAX;
  check(vos_exec_release(&f, &e, &at) && at == UINT64_MAX,
        "final frame is representable");
  refused_advance(&f, &e, "frame-index exhaustion");
  e.cursor = 1;
  refused_release(&f, &e, "out-of-range cursor");
  refused_advance(&f, &e, "invalid cursor advance");
  e.cursor = 0;
  f.slot_count = VOS_MAX_SLOTS + 1;
  refused_release(&f, &e, "oversized slot count");
  check(!vos_exec_release(0, &e, &at) && !vos_exec_release(&f, 0, &at) &&
        !vos_exec_release(&f, &e, 0), "missing release arguments");

  f.major_frame = 11;
  f.phase_offset = 7;
  f.slot_count = 2;
  f.slots[0].offset = 1;
  f.slots[1].offset = 5;
  f.slots[1].width = 1;
  vos_exec_start(&e);
  check(vos_frame_validate(&f) == VOS_OK, "ordinary table");
  for (uint32_t visit = 0; visit < 128; ++visit) {
    const uint64_t expected = 7 + (uint64_t)(visit / 2) * 11 + (visit % 2 ? 5 : 1);
    check(vos_exec_release(&f, &e, &at) && at == expected,
          "ordinary repeated release");
    check(vos_exec_advance(&f, &e), "ordinary repeated advance");
  }

  struct vos_target_state state = {0};
  state.handoff.init.frame = f;
  vos_exec_start(&state.executive);
  uint64_t comparator = 37;
  check(vos_target_release(&state, 3, 2, &comparator) && comparator == 13,
        "target deadline includes epoch and duration");
  comparator = 37;
  check(!vos_target_release(&state, UINT64_MAX, 0, &comparator) && comparator == 37,
        "epoch overflow writes no comparator output");
  check(!vos_target_release(&state, 0, UINT64_MAX, &comparator) && comparator == 37,
        "duration overflow writes no comparator output");
  check(!vos_target_release(0, 0, 0, &comparator) && comparator == 37 &&
        !vos_target_release(&state, 0, 0, 0), "missing target arguments");
  check(vos_target_advance(&state) && state.executive.cursor == 1,
        "target propagates successful advance");
  state.handoff.init.frame.major_frame = 1;
  state.handoff.init.frame.phase_offset = 0;
  state.handoff.init.frame.slot_count = 1;
  state.handoff.init.frame.slots[0].offset = 0;
  state.executive.cursor = 0;
  state.executive.frame_index = UINT64_MAX;
  check(vos_target_release(&state, 0, 0, &comparator) && comparator == UINT64_MAX,
        "target accepts MAX without sentinel ambiguity");
  comparator = 37;
  check(!vos_target_release(&state, 0, 1, &comparator) && comparator == 37,
        "horizon deadline writes no comparator output");
  check(!vos_target_advance(&state) && state.executive.frame_index == UINT64_MAX &&
        state.executive.cursor == 0 && !vos_target_advance(0),
        "target propagates horizon refusal");
  if (failures) {
    return 1;
  }
  puts("executive clock controls passed");
  return 0;
}
