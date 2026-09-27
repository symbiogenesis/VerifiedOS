// SPDX-License-Identifier: Apache-2.0
#include "vos_supervisor_context.h"

static void initial_ack(uint64_t *ack, uint64_t epoch, uint32_t units)
{
    uint32_t i;
    for (i = 0; i < VOS_CTX_ACK_WORDS; ++i)
        ack[i] = 0;
    ack[VOS_CTX_ACK_EPOCH] = epoch;
    ack[VOS_CTX_ACK_REFUSED] = units;
}

static void running_ack(uint64_t *ack, uint64_t sequence)
{
    ack[VOS_CTX_ACK_SEQUENCE] = sequence;
    ack[VOS_CTX_ACK_OPERATION] = VOS_CTX_OP_START;
    ack[VOS_CTX_ACK_PHASE] = VOS_CTX_PHASE_RUNNING;
    ack[VOS_CTX_ACK_MEMBERS] = 7;
    ack[VOS_CTX_ACK_STARTED] = 7;
    ack[VOS_CTX_ACK_COUNT] = 3;
    ack[VOS_CTX_ACK_REFUSED] = 3;
    ack[VOS_CTX_ACK_STATUS] = VOS_CTX_STATUS_OK;
}

static void retired_ack(uint64_t *ack, uint64_t sequence, uint32_t members)
{
    ack[VOS_CTX_ACK_SEQUENCE] = sequence;
    ack[VOS_CTX_ACK_OPERATION] = VOS_CTX_OP_RETIRE;
    ack[VOS_CTX_ACK_PHASE] = VOS_CTX_PHASE_RETIRED;
    ack[VOS_CTX_ACK_STATUS] = VOS_CTX_STATUS_OK;
    ack[VOS_CTX_ACK_MEMBERS] = members;
    ack[VOS_CTX_ACK_STARTED] = 7U & ~members;
    ack[VOS_CTX_ACK_COUNT] = 0;
    ack[VOS_CTX_ACK_REFUSED] = 3;
    ack[VOS_CTX_ACK_ATTEMPTS] = 1;
    ack[VOS_CTX_ACK_EPOCH] += 1;
    ack[VOS_CTX_ACK_NOW] = 10;
    ack[VOS_CTX_ACK_DEADLINE] = 11;
}

int vos_supervisor_context_controls(void)
{
    struct vos_supervisor_manifest m = {
        3, {0, 1, 2}, {0, 1, 0},
        {3, 3, 3, 3, 3, 3, 3, 3}, {1, 1, 1, 1, 1, 1, 1, 1},
        {0, 0, 7, 0, 7, 8, 0, 0}, 2, 3, 8, 4, {1, 2, 3, 5}, 5, 3, 7
    };
    struct vos_supervisor_context s = {0}, saved;
    uint64_t ack[VOS_CTX_ACK_WORDS], req[VOS_CTX_REQ_WORDS], seq = 99;
    uint32_t i, checks = 0;
#define CHECK(c) do { ++checks; if (!(c)) return (int)(checks % 254U + 1U); } while (0)
#define STEP(d) vos_supervisor_context_step(&m, &s, ack, (d), req, &seq)
    /* The kernel consumes an invalid operation and acknowledges NONE/INVALID.
     * Fresh entry must recover that watermark to make the next valid request. */
    initial_ack(ack, 0x100000001ULL, m.units);
    ack[VOS_CTX_ACK_SEQUENCE] = 1;
    ack[VOS_CTX_ACK_STATUS] = VOS_CTX_STATUS_INVALID;
    CHECK(vos_supervisor_context_recover(&m, ack, &s));
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(seq == 2 && s.acknowledged_sequence == 1);
    ack[VOS_CTX_ACK_STATUS] = VOS_CTX_STATUS_OK;
    CHECK(!vos_supervisor_context_recover(&m, ack, &s));
    /* Definitive refusals consume their fresh sequence, never an effect. */
    for (i = VOS_CTX_STATUS_INVALID; i <= VOS_CTX_STATUS_EARLY; ++i) {
        initial_ack(ack, 0x100000001ULL, m.units);
        CHECK(vos_supervisor_context_recover(&m, ack, &s));
        CHECK(STEP(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
        ack[VOS_CTX_ACK_SEQUENCE] = 1;
        ack[VOS_CTX_ACK_OPERATION] = VOS_CTX_OP_START;
        ack[VOS_CTX_ACK_STATUS] = i;
        CHECK(STEP(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_REJECTED);
        CHECK(s.acknowledged_sequence == 1 && s.outstanding_sequence == 0 &&
              s.status == i && seq == 0);
    }
    initial_ack(ack, 0x100000001ULL, m.units);
    CHECK(vos_supervisor_context_recover(&m, ack, &s));
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_HOLD) == VOS_SUPERVISOR_CONTEXT_IDLE);
    CHECK(seq == 0 && req[VOS_CTX_REQ_SEQUENCE] == 0);
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(seq == 1 && req[VOS_CTX_REQ_SEQUENCE] == 0);
    CHECK(req[VOS_CTX_REQ_OPERATION] == VOS_CTX_OP_START &&
          req[VOS_CTX_REQ_EPOCH] == 0x100000001ULL &&
          req[VOS_CTX_REQ_MEMBERS] == 7 && req[VOS_CTX_REQ_COUNT] == 3);
    CHECK(req[VOS_CTX_REQ_STARTS] == 0 && req[VOS_CTX_REQ_STARTS + 2] == 1 &&
          req[VOS_CTX_REQ_STARTS + 3] == 1 && req[VOS_CTX_REQ_STARTS + 4] == 2);
    for (i = VOS_CTX_REQ_STARTS + 6; i < VOS_CTX_REQ_WORDS; ++i)
        CHECK(req[i] == 0);
    /* A cut before publication loses local phase and reuses the unconsumed seq. */
    CHECK(vos_supervisor_context_recover(&m, ack, &s));
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(seq == 1 && s.acknowledged_sequence == 0);
    saved = s;
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_WAIT);
    CHECK(seq == 0 && s.outstanding_sequence == saved.outstanding_sequence &&
          s.acknowledged_sequence == 0);
    /* A newer but unmatched acknowledgment must not be consumed either. */
    running_ack(ack, 2);
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_WAIT);
    CHECK(s.acknowledged_sequence == 0 && seq == 0);
    ack[VOS_CTX_ACK_SEQUENCE] = 1;
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_DONE);
    CHECK(seq == 0 && s.started == 7 && s.count == 3);
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_REJECTED);
    CHECK(seq == 0);
    /* A fresh entry recovers the acknowledged phase, never a partial local one. */
    CHECK(vos_supervisor_context_recover(&m, ack, &s));
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(seq == 2 && req[VOS_CTX_REQ_OPERATION] == VOS_CTX_OP_RETIRE &&
          req[VOS_CTX_REQ_MEMBERS] == 7 && req[VOS_CTX_REQ_COUNT] == 0);
    retired_ack(ack, 2, 7);
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_WAIT);
    CHECK(seq == 0 && s.phase == VOS_SUPERVISOR_CONTEXT_BACKOFF);
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_WAIT);
    CHECK(seq == 0);
    ack[VOS_CTX_ACK_NOW] = 11;
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_HOLD) == VOS_SUPERVISOR_CONTEXT_WAIT);
    CHECK(seq == 0);
    ack[VOS_CTX_ACK_RETIRED + 1] = 1;
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(seq == 3 && req[VOS_CTX_REQ_ATTEMPTS] == 1 &&
          req[VOS_CTX_REQ_EPOCH] == 0x100000002ULL &&
          req[VOS_CTX_REQ_STARTS + 3] == 0);
    /* A failed start retains exactly its acknowledged prefix. */
    running_ack(ack, 3);
    ack[VOS_CTX_ACK_STATUS] = VOS_CTX_STATUS_START_REFUSED;
    ack[VOS_CTX_ACK_PHASE] = VOS_CTX_PHASE_FAILED;
    ack[VOS_CTX_ACK_STARTED] = 1;
    ack[VOS_CTX_ACK_COUNT] = 1;
    ack[VOS_CTX_ACK_REFUSED] = 1;
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_REJECTED);
    CHECK(seq == 0 && s.started == 1 && s.count == 1 && s.refused == 1 &&
          s.acknowledged_sequence == 3);
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_REJECTED);
    CHECK(vos_supervisor_context_recover(&m, ack, &s));
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(seq == 4 && req[VOS_CTX_REQ_OPERATION] == VOS_CTX_OP_RETIRE);
    /* Incomplete retirement cannot become a start. */
    ack[VOS_CTX_ACK_SEQUENCE] = 4;
    ack[VOS_CTX_ACK_OPERATION] = VOS_CTX_OP_RETIRE;
    ack[VOS_CTX_ACK_STATUS] = VOS_CTX_STATUS_INCOMPLETE;
    ack[VOS_CTX_ACK_COUNT] = 0;
    ack[VOS_CTX_ACK_REFUSED] = 3;
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_REJECTED);
    CHECK(seq == 0 && s.status == VOS_CTX_STATUS_INCOMPLETE);
    /* Sequence exhaustion never wraps to a new request. */
    ack[VOS_CTX_ACK_SEQUENCE] = UINT64_MAX;
    CHECK(vos_supervisor_context_recover(&m, ack, &s));
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_REJECTED);
    CHECK(seq == 0 && req[VOS_CTX_REQ_SEQUENCE] == 0);
    ack[VOS_CTX_ACK_SEQUENCE] = UINT64_MAX - 1U;
    CHECK(vos_supervisor_context_recover(&m, ack, &s));
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_REJECTED);
    CHECK(seq == 0);
    /* A subset restart preserves the live sibling outside the retired set. */
    m.restart_members = 6;
    initial_ack(ack, UINT64_MAX - 1U, m.units);
    CHECK(vos_supervisor_context_recover(&m, ack, &s));
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(req[VOS_CTX_REQ_MEMBERS] == 7 && req[VOS_CTX_REQ_COUNT] == 3);
    running_ack(ack, 1);
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_DONE);
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(req[VOS_CTX_REQ_MEMBERS] == 6);
    retired_ack(ack, 2, 6);
    CHECK(vos_supervisor_context_recover(&m, ack, &s));
    CHECK(s.started == 1 && s.epoch == UINT64_MAX);
    ack[VOS_CTX_ACK_NOW] = 11;
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(seq == 3 && req[VOS_CTX_REQ_COUNT] == 2 &&
          req[VOS_CTX_REQ_STARTS] == 1 && req[VOS_CTX_REQ_STARTS + 2] == 2 &&
          req[VOS_CTX_REQ_STARTS + 4] == 0);
    ack[VOS_CTX_ACK_SEQUENCE] = 3;
    ack[VOS_CTX_ACK_OPERATION] = VOS_CTX_OP_START;
    ack[VOS_CTX_ACK_PHASE] = VOS_CTX_PHASE_RUNNING;
    ack[VOS_CTX_ACK_STARTED] = 7;
    ack[VOS_CTX_ACK_COUNT] = 2;
    CHECK(STEP(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_DONE);
    /* Whole-word widths and padding are checked before truncating scalars. */
    saved = s;
    ack[VOS_CTX_ACK_ATTEMPTS] = 0x100000000ULL;
    CHECK(!vos_supervisor_context_recover(&m, ack, &s));
    CHECK(s.acknowledged_sequence == saved.acknowledged_sequence);
    ack[VOS_CTX_ACK_ATTEMPTS] = 1;
    ack[VOS_CTX_ACK_USED] = 1;
    CHECK(!vos_supervisor_context_recover(&m, ack, &s));
    ack[VOS_CTX_ACK_USED] = 0;
    ack[VOS_CTX_ACK_RETIRED + 3] = 1;
    CHECK(!vos_supervisor_context_recover(&m, ack, &s));
    ack[VOS_CTX_ACK_RETIRED + 3] = 0;
    ack[VOS_CTX_ACK_COUNT] = 1;
    CHECK(!vos_supervisor_context_recover(&m, ack, &s));
    ack[VOS_CTX_ACK_COUNT] = 2;
    CHECK(vos_supervisor_context_recover(&m, ack, &s));
    CHECK(STEP(99) == VOS_SUPERVISOR_CONTEXT_REJECTED);
    CHECK(seq == 0);
#ifdef VOS_CONTEXT_PERTURB
    CHECK(s.acknowledged_sequence == 4);
#else
    CHECK(s.acknowledged_sequence == 3);
#endif
    return 0;
#undef STEP
#undef CHECK
}

int main(void)
{
    return vos_supervisor_context_controls();
}
