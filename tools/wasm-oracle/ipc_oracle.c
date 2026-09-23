/* SPDX-License-Identifier: Apache-2.0 */
/* =========================================================================
   ipc_oracle.c

   The purecap counterpart of ipc_oracle.v, for M1.2f's component-level
   differential: the same 84 checks over EndpointIPC.v's decision
   procedures, written GC-free in the selected scalar C profile and lowered
   through the contained purecap backend, then run on the golden emulator.
   `run.py compiler-diff component` holds its result against the Wasm
   oracle's run of ipc_oracle.v under one declared output encoding.

   What this file is. A hand-written refinement of the computable content
   ipc_oracle.v folds into one boolean, check for check and in the same
   order, which is the CompCert-C route's shape (the checklist's section 0):
   GC-free C first, its refinement proof deferred, differential testing
   against the Wasm oracle and the Sail emulator standing in. Nothing here
   is extracted or generated from the Gallina, and no theorem relates the
   two; agreement of the two runs says the two pipelines return the same
   answer on this battery and nothing more.

   How the Gallina is represented. Every inductive is a small integer code
   in its constructor order. Every list is a caller-owned array with an
   explicit length. Every function-valued argument (a readiness state, a
   transfer, a grant, a holding, a decider, an observation, a delivery, a
   step) is defunctionalized into a code the one function that applies it
   switches on, because the selected profile admits no indirect call through
   unknown memory. Structural recursion is a loop, the profile refusing a
   recursive call path with no admitted stack bound. The kernel record keeps
   only the parked list's length, the one field any check reads. No global
   object is declared: the profile binds global authority only through a
   composition, so every table is built in the caller's frame.

   The result. `main` returns 0 when every check holds and otherwise the
   1-based index of the first check that does not, in ipc_oracle.v's order;
   the driver's component harness prints `true` or `false` from that, as
   run_demo.mjs prints the Wasm module's boolean. A battery whose length is
   not ipc_oracle.v's 84 returns 255, so a dropped or duplicated check
   cannot pass as agreement.
   ========================================================================= */

/* Invocation, in R-07-031b's order. */
enum { SEND, RECEIVE, POLL_SITE_YIELD, GRANT_REDEEM, REVOKE };

/* AbiGroup. */
enum { ENDPOINT_GROUP, NOTIFICATION_GROUP, PARTITION_CONTEXT_GROUP, REVOCATION_GROUP };

/* Nameable. */
enum { N_ENDPOINT, N_NOTIFICATION, N_PARTITION_CONTEXT, N_GRANT_TABLE,
       N_SCHEDULE_TABLE, N_REPLY_OBJECT };

/* Act. */
enum { A_SEND, A_RECEIVE, A_YIELD, A_GRANT_REDEEM, A_REVOKE, A_NOTIFY_SIGNAL,
       A_NOTIFY_RECEIVE, A_GRANT_MINT, A_FOCUS_REBIND, A_RUNG_SELECT, A_SUSPEND,
       A_SYNCHRONOUS_EXCEPTION, A_RETYPE, A_CAP_SPACE_OP, A_DERIVATION_TREE_OP,
       A_SUBMISSION_QUEUE_OPCODE, A_REPLY_INVOCATION };

/* The defunctionalized function values. */
enum { READY_BITS, READY_ALWAYS, READY_NEVER };          /* Readiness */
enum { T_SPEC, T_OPTIMISTIC, T_QUEUEING };               /* Transfer */
enum { G_SPEC, G_STINGY, G_REPLACING, G_AMBIENT };       /* Grant */
enum { H_ALL, H_NONE };                                  /* Holdings */
enum { D_SPEC, D_NAIVE, D_POST_ONLY };                   /* Decider */
enum { DL_SPEC, DL_UNSWAPPED, DL_HEAD_MEMBER };          /* Delivery */
enum { ST_STEP_OF, ST_CLEARING, ST_SHARING };            /* Step */
enum { GR_GROUP_OF, GR_NOTIFYING };                      /* Grouping */
enum { P_NUMBERED, P_TRAPS, P_TRAPS_SCHEDULE, P_TRAPS_UNNUMBERED,
       P_TRAPS_SCHEDULE_UNNUMBERED };                    /* act predicates */

#define LIST_MAX 17
#define CHECKS 84

/* A message: R-07-031's registers and capability slots. */
struct message {
    long nregs;
    long regs[16];
    long ncaps;
    long caps[4];
};

/* The Machine fields a check reads; `label` and `pending` are the same
   functions in `demo` and `demo_static`, so they are code below. */
struct machine {
    long partition_count;
    long endpoint_count;
    long word_count;
    long slot_count;
    long badge_width;
    long ngroup;
    long group_members[3];
    long pending_arm;
    long pending_width;
};

/* ---- List, boolean and numeric helpers -------------------------------- */

static long negb(long b)
{
    return b ? 0 : 1;
}

static long same_bool(long a, long b)
{
    return a ? b : negb(b);
}

static long upto(long n, long *out)
{
    long k;
    for (k = 0; k < n; k++)
        out[k] = k;
    return n;
}

static long before_last(long n)
{
    return n == 0 ? 0 : n - 1;
}

static long halve(long n)
{
    return n / 2;
}

static long oddb(long n)
{
    return n % 2;
}

static long bit_at(long i, long n)
{
    long k, v = n;
    for (k = 0; k < i; k++)
        v = halve(v);
    return oddb(v);
}

static long two_pow(long n)
{
    long k, p = 1;
    for (k = 0; k < n; k++)
        p = p + p;
    return p;
}

static long head_or(long *l, long n, long d)
{
    return n == 0 ? d : l[0];
}

/* ---- The closed enumerations ------------------------------------------ */

static long all_invocations(long *out)
{
    out[0] = SEND;
    out[1] = RECEIVE;
    out[2] = POLL_SITE_YIELD;
    out[3] = GRANT_REDEEM;
    out[4] = REVOKE;
    return 5;
}

static long all_groups(long *out)
{
    out[0] = ENDPOINT_GROUP;
    out[1] = NOTIFICATION_GROUP;
    out[2] = PARTITION_CONTEXT_GROUP;
    out[3] = REVOCATION_GROUP;
    return 4;
}

static long all_nameable(long *out)
{
    out[0] = N_ENDPOINT;
    out[1] = N_NOTIFICATION;
    out[2] = N_PARTITION_CONTEXT;
    out[3] = N_GRANT_TABLE;
    out[4] = N_SCHEDULE_TABLE;
    out[5] = N_REPLY_OBJECT;
    return 6;
}

static long numbered_acts(long *out)
{
    out[0] = A_SEND;
    out[1] = A_RECEIVE;
    out[2] = A_YIELD;
    out[3] = A_GRANT_REDEEM;
    out[4] = A_REVOKE;
    return 5;
}

static long unnumbered_acts(long *out)
{
    out[0] = A_NOTIFY_SIGNAL;
    out[1] = A_NOTIFY_RECEIVE;
    out[2] = A_GRANT_MINT;
    out[3] = A_FOCUS_REBIND;
    out[4] = A_RUNG_SELECT;
    out[5] = A_SUSPEND;
    out[6] = A_SYNCHRONOUS_EXCEPTION;
    return 7;
}

static long deleted_acts(long *out)
{
    out[0] = A_RETYPE;
    out[1] = A_CAP_SPACE_OP;
    out[2] = A_DERIVATION_TREE_OP;
    out[3] = A_SUBMISSION_QUEUE_OPCODE;
    out[4] = A_REPLY_INVOCATION;
    return 5;
}

/* app numbered_acts (app unnumbered_acts deleted_acts) */
static long all_acts(long *out)
{
    long part[LIST_MAX];
    long n = 0, m, k;
    m = numbered_acts(part);
    for (k = 0; k < m; k++)
        out[n++] = part[k];
    m = unnumbered_acts(part);
    for (k = 0; k < m; k++)
        out[n++] = part[k];
    m = deleted_acts(part);
    for (k = 0; k < m; k++)
        out[n++] = part[k];
    return n;
}

static long schedule_transitions(long *out)
{
    out[0] = A_FOCUS_REBIND;
    out[1] = A_RUNG_SELECT;
    out[2] = A_SUSPEND;
    return 3;
}

/* ---- Acts and the numbering ------------------------------------------- */

static long act_eqb(long a, long b)
{
    return a == b;
}

static long group_of(long i)
{
    if (i == SEND || i == RECEIVE)
        return ENDPOINT_GROUP;
    if (i == POLL_SITE_YIELD)
        return PARTITION_CONTEXT_GROUP;
    return REVOCATION_GROUP;
}

static long notifying_grouping(long i)
{
    if (i == POLL_SITE_YIELD)
        return NOTIFICATION_GROUP;
    return group_of(i);
}

static long apply_grouping(long g, long i)
{
    return g == GR_NOTIFYING ? notifying_grouping(i) : group_of(i);
}

/* members_of g, written into out */
static long members_of(long g, long *out)
{
    long inv[LIST_MAX];
    long n = all_invocations(inv), k, m = 0;
    for (k = 0; k < n; k++)
        if (group_of(inv[k]) == g)
            out[m++] = inv[k];
    return m;
}

static long census(long grouping, long a)
{
    long inv[LIST_MAX];
    long n = all_invocations(inv), k, m = 0;
    for (k = 0; k < n; k++)
        if (apply_grouping(grouping, inv[k]) == a)
            m++;
    return m;
}

static long act_of(long i)
{
    if (i == SEND)
        return A_SEND;
    if (i == RECEIVE)
        return A_RECEIVE;
    if (i == POLL_SITE_YIELD)
        return A_YIELD;
    if (i == GRANT_REDEEM)
        return A_GRANT_REDEEM;
    return A_REVOKE;
}

static long numbered_act(long a)
{
    return a == A_SEND || a == A_RECEIVE || a == A_YIELD || a == A_GRANT_REDEEM
        || a == A_REVOKE;
}

static long is_the_act_of_an_invocation(long a)
{
    long inv[LIST_MAX];
    long n = all_invocations(inv), k;
    for (k = 0; k < n; k++)
        if (act_eqb(act_of(inv[k]), a))
            return 1;
    return 0;
}

static long deleted_act(long a)
{
    long del[LIST_MAX];
    long n = deleted_acts(del), k;
    for (k = 0; k < n; k++)
        if (act_eqb(del[k], a))
            return 1;
    return 0;
}

static long traps_act(long a)
{
    return numbered_act(a) || a == A_SYNCHRONOUS_EXCEPTION;
}

static long traps_with_the_schedule_transitions(long a)
{
    return traps_act(a) || act_eqb(a, A_FOCUS_REBIND) || act_eqb(a, A_RUNG_SELECT)
        || act_eqb(a, A_SUSPEND);
}

static long act_predicate(long which, long a)
{
    if (which == P_NUMBERED)
        return numbered_act(a);
    if (which == P_TRAPS)
        return traps_act(a);
    if (which == P_TRAPS_SCHEDULE)
        return traps_with_the_schedule_transitions(a);
    if (which == P_TRAPS_UNNUMBERED)
        return traps_act(a) && negb(numbered_act(a));
    return traps_with_the_schedule_transitions(a) && negb(numbered_act(a));
}

/* count_of (filter_of p all_acts) */
static long count_acts(long which)
{
    long acts[LIST_MAX];
    long n = all_acts(acts), k, m = 0;
    for (k = 0; k < n; k++)
        if (act_predicate(which, acts[k]))
            m++;
    return m;
}

/* any_of p all_acts */
static long any_act(long which)
{
    return count_acts(which) > 0;
}

static long is_schedule_transition(long a)
{
    long st[LIST_MAX];
    long n = schedule_transitions(st), k;
    for (k = 0; k < n; k++)
        if (act_eqb(st[k], a))
            return 1;
    return 0;
}

/* ---- The object inventory ---------------------------------------------- */

static long is_object(long c)
{
    return c == N_ENDPOINT || c == N_NOTIFICATION || c == N_PARTITION_CONTEXT;
}

static long is_table(long c)
{
    return c == N_GRANT_TABLE || c == N_SCHEDULE_TABLE;
}

static long object_classes(long *out)
{
    long all[LIST_MAX];
    long n = all_nameable(all), k, m = 0;
    for (k = 0; k < n; k++)
        if (is_object(all[k]))
            out[m++] = all[k];
    return m;
}

static long kernel_tables(long *out)
{
    long all[LIST_MAX];
    long n = all_nameable(all), k, m = 0;
    for (k = 0; k < n; k++)
        if (is_table(all[k]))
            out[m++] = all[k];
    return m;
}

static long occurrences(long c, long *l, long n)
{
    long k, m = 0;
    for (k = 0; k < n; k++)
        if (l[k] == c)
            m++;
    return m;
}

static long inventory_ok(long *l, long n)
{
    long classes[LIST_MAX];
    long nc = object_classes(classes), k;
    for (k = 0; k < n; k++)
        if (!is_object(l[k]))
            return 0;
    for (k = 0; k < nc; k++)
        if (occurrences(classes[k], l, n) != 1)
            return 0;
    return 1;
}

/* drop_at n l: every member but the one at n, or l itself past its end */
static long drop_at(long at, long *l, long n, long *out)
{
    long k, m = 0;
    for (k = 0; k < n; k++)
        if (k != at)
            out[m++] = l[k];
    return m;
}

/* insert_at n c l: c before position n, or at the end past it */
static long insert_at(long at, long c, long *l, long n, long *out)
{
    long k, m = 0;
    for (k = 0; k < n; k++) {
        if (k == at)
            out[m++] = c;
        out[m++] = l[k];
    }
    if (at >= n)
        out[m++] = c;
    return m;
}

/* swap_at n l: positions n and n+1 exchanged where both exist */
static long swap_at(long at, long *l, long n, long *out)
{
    long k;
    for (k = 0; k < n; k++)
        out[k] = l[k];
    if (at + 1 < n) {
        out[at] = l[at + 1];
        out[at + 1] = l[at];
    }
    return n;
}

/* ---- The frozen surface ------------------------------------------------ */

static long frozen_surface(long *l, long n)
{
    long inv[LIST_MAX];
    long ni = all_invocations(inv), k;
    for (k = 0; k < ni; k++)
        if (occurrences(inv[k], l, n) != 1)
            return 0;
    return 1;
}

/* index_in spec_surface i: the position, or the length when absent */
static long index_of(long i)
{
    long surface[LIST_MAX];
    long n = all_invocations(surface), k;
    for (k = 0; k < n; k++)
        if (surface[k] == i)
            return k;
    return n;
}

static long admits_of_mask(long mask, long i)
{
    return bit_at(index_of(i), mask);
}

static long surface_mask_ok(long mask)
{
    long inv[LIST_MAX];
    long n = all_invocations(inv), k;
    for (k = 0; k < n; k++)
        if (!admits_of_mask(mask, inv[k]))
            return 0;
    return 1;
}

/* ---- The message medium and the badge space ----------------------------- */

static void demo_machine(struct machine *m, long arm)
{
    m->partition_count = 4;
    m->endpoint_count = 4;
    m->word_count = 4;
    m->slot_count = 2;
    m->badge_width = 3;
    m->ngroup = 3;
    m->group_members[0] = 0;
    m->group_members[1] = 1;
    m->group_members[2] = 2;
    m->pending_arm = arm;
    m->pending_width = 3;
}

/* bulk_message n: registers n-1 down to 0, no capability slot */
static void bulk_message(long n, struct message *msg)
{
    long k;
    msg->nregs = n;
    for (k = 0; k < n; k++)
        msg->regs[k] = n - 1 - k;
    msg->ncaps = 0;
}

static long message_ok(struct machine *m, struct message *msg)
{
    return msg->nregs <= m->word_count && msg->ncaps <= m->slot_count;
}

/* badges w, as lengths and bits: true-first then false-first at each level */
static long badges(long w, long *lengths, long *bits)
{
    long next_len[16], next_bits[64];
    long count = 1, level, k, j, m;
    lengths[0] = 0;
    for (level = 0; level < w; level++) {
        m = 0;
        for (j = 0; j < 2; j++) {
            for (k = 0; k < count; k++) {
                long b;
                next_len[m] = lengths[k] + 1;
                next_bits[m * 4] = j == 0 ? 1 : 0;
                for (b = 0; b < lengths[k]; b++)
                    next_bits[m * 4 + b + 1] = bits[k * 4 + b];
                m++;
            }
        }
        count = m;
        for (k = 0; k < count; k++) {
            long b;
            lengths[k] = next_len[k];
            for (b = 0; b < next_len[k]; b++)
                bits[k * 4 + b] = next_bits[k * 4 + b];
        }
    }
    return count;
}

static long badge_ok(struct machine *m, long length)
{
    return length == m->badge_width;
}

/* ---- The transfer ------------------------------------------------------ */

static long readiness(long kind, long n, long e)
{
    if (kind == READY_ALWAYS)
        return 1;
    if (kind == READY_NEVER)
        return 0;
    return bit_at(e, n);
}

/* One transfer of `offer_into at` under transfer `t`: returns is_refused of
   the outcome and leaves the kernel's parked count in *held. */
static long transfer(long t, long tk, long *held, long rkind, long rn, long at)
{
    long ready = readiness(rkind, rn, at);
    if (t == T_SPEC)
        return negb(ready);
    if (t == T_OPTIMISTIC)
        return negb(ready || at < tk);
    if (ready)
        return 0;
    *held = *held + 1;
    return 1;
}

/* said t empty_kernel st (offer_into at) is refused */
static long refused_from_empty(long t, long tk, long rkind, long rn, long at)
{
    long held = 0;
    return transfer(t, tk, &held, rkind, rn, at);
}

/* run_offers over offers into 0 .. n-1 from empty_kernel: the parked count;
   *all_refused is all_of is_refused (outcomes_of ...) over the same run */
static long run_offers(long t, long tk, long rkind, long rn, long n, long *all_refused)
{
    long held = 0, e;
    *all_refused = 1;
    for (e = 0; e < n; e++)
        if (!transfer(t, tk, &held, rkind, rn, e))
            *all_refused = 0;
    return held;
}

/* ---- The explicit capability transfer ------------------------------------ */

static long carried(struct message *msg, long c)
{
    long k;
    for (k = 0; k < msg->ncaps; k++)
        if (msg->caps[k] == c)
            return 1;
    return 0;
}

static long holding(long h, long c)
{
    return h == H_ALL;
}

static long grant(long g, struct message *msg, long h, long c)
{
    if (g == G_SPEC)
        return holding(h, c) || carried(msg, c);
    if (g == G_STINGY)
        return holding(h, c);
    if (g == G_REPLACING)
        return carried(msg, c);
    return holding(h, c) || carried(msg, c) || c == 0;
}

/* ---- The ring deciders --------------------------------------------------- */

static long has_work(long produced, long consumed)
{
    return consumed < produced;
}

static long decide(long d, long bp, long bc, long np, long nc)
{
    if (d == D_SPEC)
        return negb(has_work(bp, bc)) && negb(has_work(np, nc));
    if (d == D_NAIVE)
        return negb(has_work(bp, bc));
    return negb(has_work(np, nc));
}

/* ---- The notification word ------------------------------------------------ */

static long spec_signal(long b)
{
    return 1;
}

static long spec_reset(long b)
{
    return 0;
}

static long counting_signal(long n)
{
    return n + 1;
}

static long counting_armed(long n)
{
    return 0 < n;
}

static long counting_reset(long n)
{
    return 0;
}

/* ---- The rotation ------------------------------------------------------- */

static long rotate_from(long *l, long n, long u, long wrap)
{
    long k;
    for (k = 0; k < n; k++)
        if (l[k] == u)
            return k + 1 < n ? l[k + 1] : wrap;
    return wrap;
}

static long advance(struct machine *m, long u)
{
    return rotate_from(m->group_members, m->ngroup, u,
                       head_or(m->group_members, m->ngroup, u));
}

/* spec_advance ignores the observation; the work-stealing advance reads it */
static long spec_advance(struct machine *m, long observed, long u)
{
    return advance(m, u);
}

static long work_stealing_advance(struct machine *m, long observed, long u)
{
    if (0 < observed)
        return advance(m, advance(m, u));
    return advance(m, u);
}

static long label(long u)
{
    return u < 3 ? 0 : 1;
}

static long same_label_group(long *g, long n)
{
    long k;
    for (k = 0; k < n; k++)
        if (label(g[k]) != label(head_or(g, n, g[k])))
            return 0;
    return 1;
}

/* ---- The pending component at the switch ---------------------------------- */

static long pending(long s, long b)
{
    return s == b;
}

static long delivery(long d, struct machine *m, long pred, long succ, long b)
{
    if (d == DL_SPEC)
        return pending(succ, b);
    if (d == DL_UNSWAPPED)
        return m->pending_arm ? pending(pred, b) : pending(succ, b);
    return pending(head_or(m->group_members, m->ngroup, succ), b);
}

/* run_dispatches st (fun _ _ => true) pred0 targets, read at (u, b), with
   react = fun _ _ => false: each step is read backwards from the last. */
static long dispatched(long st, long pred0, long *targets, long n, long u, long b)
{
    long k, pred, s;
    for (k = n - 1; k >= 0; k--) {
        s = targets[k];
        pred = k == 0 ? pred0 : targets[k - 1];
        if (st == ST_SHARING)
            return 0;
        if (u == s)
            return 0;
        if (st == ST_CLEARING && u == pred)
            return 0;
    }
    return 1;
}

/* ---- The battery, section by section, in ipc_oracle.v's order ------------- */

static long enumeration_checks(long *c)
{
    long l[LIST_MAX];
    long n = 0;
    c[n++] = all_invocations(l) == 5;
    c[n++] = all_groups(l) == 4;
    c[n++] = all_nameable(l) == 6;
    c[n++] = all_acts(l) == 17;
    c[n++] = all_invocations(l) < 12;
    return n;
}

static long act_checks(long *c)
{
    long acts[LIST_MAX], inv[LIST_MAX], st[LIST_MAX];
    long na = all_acts(acts), ni = all_invocations(inv), ns = schedule_transitions(st);
    long n = 0, k, ok;

    c[n++] = count_acts(P_NUMBERED) == 5;
    c[n++] = count_acts(P_TRAPS) == 6 && count_acts(P_TRAPS_SCHEDULE) == 9;
    ok = 1;
    for (k = 0; k < na; k++)
        if (!same_bool(negb(same_bool(traps_act(acts[k]),
                                      traps_with_the_schedule_transitions(acts[k]))),
                       is_schedule_transition(acts[k])))
            ok = 0;
    c[n++] = ok;
    c[n++] = count_acts(P_TRAPS_UNNUMBERED) == 1
        && count_acts(P_TRAPS_SCHEDULE_UNNUMBERED) == 4;
    c[n++] = any_act(P_TRAPS_UNNUMBERED) && any_act(P_TRAPS_SCHEDULE_UNNUMBERED);
    ok = 1;
    for (k = 0; k < ni; k++)
        if (!numbered_act(act_of(inv[k])))
            ok = 0;
    c[n++] = ok;
    ok = 1;
    for (k = 0; k < na; k++)
        if (!same_bool(is_the_act_of_an_invocation(acts[k]), numbered_act(acts[k])))
            ok = 0;
    c[n++] = ok;
    c[n++] = numbered_act(A_SEND) && traps_act(A_SEND)
        && traps_with_the_schedule_transitions(A_SEND);
    c[n++] = traps_act(A_SYNCHRONOUS_EXCEPTION)
        && traps_with_the_schedule_transitions(A_SYNCHRONOUS_EXCEPTION)
        && negb(numbered_act(A_SYNCHRONOUS_EXCEPTION));
    c[n++] = negb(numbered_act(A_SUBMISSION_QUEUE_OPCODE))
        && deleted_act(A_SUBMISSION_QUEUE_OPCODE)
        && negb(traps_act(A_SUBMISSION_QUEUE_OPCODE))
        && negb(traps_with_the_schedule_transitions(A_SUBMISSION_QUEUE_OPCODE));
    ok = 1;
    for (k = 0; k < ns; k++)
        if (!(negb(numbered_act(st[k])) && negb(is_the_act_of_an_invocation(st[k]))))
            ok = 0;
    c[n++] = ok;
    return n;
}

static long group_checks(long *c)
{
    long l[LIST_MAX];
    long n = 0;
    c[n++] = members_of(NOTIFICATION_GROUP, l) == 0;
    c[n++] = members_of(ENDPOINT_GROUP, l) == 2;
    c[n++] = members_of(group_of(POLL_SITE_YIELD), l) == 1;
    c[n++] = members_of(group_of(REVOKE), l) == 2;
    return n;
}

/* all_of (fun l => negb (inventory_ok l)) (inventory_insertions_of c), and
   the family's size */
static long no_insertion_is_admitted(long c, long *size)
{
    long inventory[LIST_MAX], member[LIST_MAX], index[LIST_MAX];
    long ni = object_classes(inventory);
    long count = upto(ni + 1, index), k, ok = 1;
    for (k = 0; k < count; k++) {
        long m = insert_at(index[k], c, inventory, ni, member);
        if (inventory_ok(member, m))
            ok = 0;
    }
    *size = count;
    return ok;
}

static long inventory_checks(long *c)
{
    long classes[LIST_MAX], tables[LIST_MAX], member[LIST_MAX], index[LIST_MAX];
    long nc = object_classes(classes), nt = kernel_tables(tables);
    long deletions = upto(nc, index), insertions, k, ok, n = 0;

    c[n++] = nc == 3 && nt == 2;
    c[n++] = inventory_ok(classes, nc);
    no_insertion_is_admitted(N_REPLY_OBJECT, &insertions);
    c[n++] = deletions == 3 && insertions == 4;
    ok = 1;
    for (k = 0; k < deletions; k++) {
        long m = drop_at(index[k], classes, nc, member);
        if (inventory_ok(member, m))
            ok = 0;
    }
    c[n++] = ok;
    c[n++] = no_insertion_is_admitted(N_GRANT_TABLE, &insertions);
    c[n++] = no_insertion_is_admitted(N_REPLY_OBJECT, &insertions);
    c[n++] = no_insertion_is_admitted(N_ENDPOINT, &insertions);
    return n;
}

static long surface_checks(long *c)
{
    long surface[LIST_MAX], inv[LIST_MAX], member[LIST_MAX], index[LIST_MAX];
    long ns = all_invocations(surface), ni = all_invocations(inv);
    long deletions, insertions, transpositions, k, m, ok, n = 0;

    c[n++] = frozen_surface(surface, ns);
    ok = 1;
    for (k = 0; k < ni; k++)
        if (occurrences(inv[k], surface, ns) != 1)
            ok = 0;
    c[n++] = ok;
    deletions = upto(ns, index);
    insertions = upto(ns + 1, index);
    transpositions = upto(before_last(ns), index);
    c[n++] = deletions == 5 && insertions == 6 && transpositions == 4;
    ok = 1;
    deletions = upto(ns, index);
    for (k = 0; k < deletions; k++) {
        m = drop_at(index[k], surface, ns, member);
        if (frozen_surface(member, m))
            ok = 0;
    }
    c[n++] = ok;
    ok = 1;
    insertions = upto(ns + 1, index);
    for (k = 0; k < insertions; k++) {
        m = insert_at(index[k], SEND, surface, ns, member);
        if (frozen_surface(member, m))
            ok = 0;
    }
    c[n++] = ok;
    ok = 1;
    transpositions = upto(before_last(ns), index);
    for (k = 0; k < transpositions; k++) {
        m = swap_at(index[k], surface, ns, member);
        if (!frozen_surface(member, m))
            ok = 0;
    }
    c[n++] = ok;
    ok = 1;
    m = drop_at(2, surface, ns, member);
    if (frozen_surface(member, m))
        ok = 0;
    m = insert_at(3, SEND, surface, ns, member);
    if (frozen_surface(member, m))
        ok = 0;
    m = swap_at(1, surface, ns, member);
    if (!frozen_surface(member, m))
        ok = 0;
    c[n++] = ok;
    c[n++] = index_of(SEND) == 0 && index_of(RECEIVE) == 1 && index_of(POLL_SITE_YIELD) == 2
        && index_of(GRANT_REDEEM) == 3 && index_of(REVOKE) == 4;
    ok = 1;
    for (k = 0; k < ni; k++)
        if (!(index_of(inv[k]) < ns))
            ok = 0;
    c[n++] = ok;
    return n;
}

static long mask_checks(long *c)
{
    long masks[64], inv[LIST_MAX];
    long ni = all_invocations(inv);
    long nm = upto(two_pow(ni), masks), k, found, ok, n = 0;

    c[n++] = nm == 32;
    found = 0;
    for (k = 0; k < nm; k++)
        if (surface_mask_ok(masks[k]))
            found++;
    c[n++] = found == 1;
    c[n++] = surface_mask_ok(31);
    ok = 1;
    nm = upto(31, masks);
    for (k = 0; k < nm; k++)
        if (surface_mask_ok(masks[k]))
            ok = 0;
    c[n++] = ok;
    ok = 1;
    for (k = 0; k < ni; k++)
        if (!admits_of_mask(31, inv[k]))
            ok = 0;
    c[n++] = ok;
    c[n++] = negb(admits_of_mask(30, SEND)) && admits_of_mask(30, RECEIVE);
    return n;
}

static long medium_checks(long *c)
{
    struct machine demo;
    struct message msg;
    long lengths[16], bits[64], index[LIST_MAX];
    long k, m, ok, count3, count4, n = 0;

    demo_machine(&demo, 1);
    bulk_message(4, &msg);
    ok = message_ok(&demo, &msg);
    bulk_message(5, &msg);
    c[n++] = ok && negb(message_ok(&demo, &msg));
    ok = 1;
    m = upto(5, index);
    for (k = 0; k < m; k++) {
        bulk_message(index[k], &msg);
        if (!message_ok(&demo, &msg))
            ok = 0;
    }
    c[n++] = ok;
    ok = 1;
    m = upto(4, index);
    for (k = 0; k < m; k++) {
        bulk_message(5 + index[k], &msg);
        if (message_ok(&demo, &msg))
            ok = 0;
    }
    c[n++] = ok;
    count3 = badges(3, lengths, bits);
    count4 = badges(4, lengths, bits);
    c[n++] = count3 == 8 && count4 == two_pow(4);
    ok = 1;
    count3 = badges(3, lengths, bits);
    for (k = 0; k < count3; k++)
        if (!badge_ok(&demo, lengths[k]))
            ok = 0;
    c[n++] = ok;
    ok = 1;
    m = badges(2, lengths, bits);
    for (k = 0; k < m; k++)
        if (badge_ok(&demo, lengths[k]))
            ok = 0;
    m = badges(4, lengths, bits);
    for (k = 0; k < m; k++)
        if (badge_ok(&demo, lengths[k]))
            ok = 0;
    c[n++] = ok;
    return n;
}

static long transfer_checks(long *c)
{
    long states[LIST_MAX], endpoints[LIST_MAX], ks[LIST_MAX];
    long ns, ne, nk, i, j, ok, all, held, n = 0;

    ok = 1;
    ns = upto(16, states);
    ne = upto(4, endpoints);
    for (i = 0; i < ns; i++)
        for (j = 0; j < ne; j++)
            if (!same_bool(negb(refused_from_empty(T_SPEC, 0, READY_BITS, states[i],
                                                   endpoints[j])),
                           bit_at(endpoints[j], states[i])))
                ok = 0;
    c[n++] = ok;
    ok = 1;
    for (j = 0; j < ne; j++)
        if (!refused_from_empty(T_OPTIMISTIC, 0, READY_NEVER, 0, endpoints[j]))
            ok = 0;
    c[n++] = ok;
    ok = 1;
    nk = upto(4, ks);
    for (i = 0; i < nk; i++) {
        all = 1;
        for (j = 0; j < ne; j++)
            if (!refused_from_empty(T_OPTIMISTIC, ks[i] + 1, READY_NEVER, 0, endpoints[j]))
                all = 0;
        if (all)
            ok = 0;
    }
    c[n++] = ok;
    ok = 1;
    ne = upto(4, endpoints);
    for (j = 0; j < ne; j++)
        if (refused_from_empty(T_SPEC, 0, READY_ALWAYS, 0, endpoints[j]))
            ok = 0;
    c[n++] = ok;
    run_offers(T_SPEC, 0, READY_NEVER, 0, 3, &all);
    c[n++] = all;
    held = 0;
    transfer(T_SPEC, 0, &held, READY_NEVER, 0, 0);
    c[n++] = held == 0;
    c[n++] = run_offers(T_SPEC, 0, READY_NEVER, 0, 3, &all) == 0;
    c[n++] = run_offers(T_QUEUEING, 0, READY_NEVER, 0, 3, &all) == 3;
    return n;
}

static long grant_checks(long *c)
{
    struct message msg;
    long n = 0;
    bulk_message(4, &msg);
    c[n++] = negb(carried(&msg, 2));
    c[n++] = grant(G_SPEC, &msg, H_ALL, 5) && grant(G_STINGY, &msg, H_ALL, 5);
    c[n++] = negb(grant(G_REPLACING, &msg, H_ALL, 5)) && grant(G_SPEC, &msg, H_ALL, 5);
    c[n++] = grant(G_AMBIENT, &msg, H_NONE, 0) && negb(grant(G_SPEC, &msg, H_NONE, 0));
    return n;
}

static long decider_checks(long *c)
{
    long n = 0;
    c[n++] = has_work(3, 2) && negb(has_work(2, 2));
    c[n++] = decide(D_SPEC, 2, 2, 2, 2) && negb(decide(D_SPEC, 2, 2, 3, 2))
        && negb(decide(D_SPEC, 3, 2, 2, 2)) && negb(decide(D_SPEC, 3, 2, 3, 2));
    c[n++] = decide(D_NAIVE, 2, 2, 3, 2) && negb(decide(D_SPEC, 2, 2, 3, 2));
    c[n++] = decide(D_POST_ONLY, 3, 2, 2, 2) && negb(decide(D_SPEC, 3, 2, 2, 2));
    return n;
}

static long notification_checks(long *c)
{
    long n = 0;
    c[n++] = same_bool(spec_signal(spec_signal(0)), spec_signal(0));
    c[n++] = negb(spec_reset(1)) && negb(spec_reset(0));
    c[n++] = negb(counting_signal(counting_signal(0)) == counting_signal(0));
    c[n++] = negb(counting_armed(0)) && counting_armed(1)
        && negb(counting_armed(counting_reset(3)));
    return n;
}

static long rotation_checks(long *c)
{
    struct machine demo;
    long g[LIST_MAX];
    long quiet = 0, loaded = 4, m, n = 0;

    demo_machine(&demo, 1);
    c[n++] = advance(&demo, 0) == 1 && advance(&demo, 1) == 2 && advance(&demo, 2) == 0;
    c[n++] = spec_advance(&demo, quiet, 0) == spec_advance(&demo, loaded, 0);
    c[n++] = work_stealing_advance(&demo, quiet, 0) == 1
        && work_stealing_advance(&demo, loaded, 0) == 2
        && negb(work_stealing_advance(&demo, quiet, 0)
                == work_stealing_advance(&demo, loaded, 0));
    m = upto(3, g);
    c[n] = same_label_group(g, m);
    m = upto(4, g);
    c[n] = c[n] && negb(same_label_group(g, m));
    n++;
    return n;
}

/* all_of over s, b in upto 3 of same_bool (d1 m1 p s b) (d2 m2 p s b) */
static long deliveries_agree(long d1, struct machine *m1, long d2, struct machine *m2,
                             long p1, long p2)
{
    long idx[LIST_MAX];
    long ni = upto(3, idx), s, b;
    for (s = 0; s < ni; s++)
        for (b = 0; b < ni; b++)
            if (!same_bool(delivery(d1, m1, p1, idx[s], idx[b]),
                           delivery(d2, m2, p2, idx[s], idx[b])))
                return 0;
    return 1;
}

static long pending_checks(long *c)
{
    struct machine demo, demo_static;
    long targets[2];
    long n = 0;

    demo_machine(&demo, 1);
    demo_machine(&demo_static, 0);
    targets[0] = 1;
    targets[1] = 2;
    c[n++] = pending(1, 1) && negb(pending(1, 0));
    c[n++] = negb(delivery(DL_SPEC, &demo, 0, 2, 0)) && delivery(DL_SPEC, &demo, 0, 2, 2);
    c[n++] = deliveries_agree(DL_SPEC, &demo, DL_SPEC, &demo, 0, 1);
    c[n++] = delivery(DL_HEAD_MEMBER, &demo, 0, 2, 0)
        && negb(delivery(DL_SPEC, &demo, 0, 2, 0));
    c[n++] = deliveries_agree(DL_UNSWAPPED, &demo_static, DL_SPEC, &demo_static, 0, 0)
        && negb(deliveries_agree(DL_UNSWAPPED, &demo, DL_SPEC, &demo, 0, 0));
    c[n++] = negb(delivery(DL_UNSWAPPED, &demo, 1, 0, 0))
        && delivery(DL_UNSWAPPED, &demo_static, 1, 0, 0);
    c[n++] = dispatched(ST_STEP_OF, 0, targets, 2, 0, 0)
        && negb(dispatched(ST_CLEARING, 0, targets, 2, 0, 0))
        && negb(dispatched(ST_SHARING, 0, targets, 2, 0, 0));
    c[n++] = census(GR_GROUP_OF, NOTIFICATION_GROUP) == 0
        && census(GR_NOTIFYING, NOTIFICATION_GROUP) == 1;
    return n;
}

static long helper_checks(long *c)
{
    long idx[LIST_MAX];
    long k, m, ok, n = 0;
    c[n++] = same_bool(bit_at(0, 13), 1) && same_bool(bit_at(1, 13), 0)
        && same_bool(bit_at(2, 13), 1) && same_bool(bit_at(3, 13), 1);
    ok = 1;
    m = upto(5, idx);
    for (k = 0; k < m; k++)
        if (bit_at(idx[k], 0))
            ok = 0;
    c[n++] = ok;
    c[n++] = two_pow(5) == 32;
    c[n++] = upto(7, idx) == 7;
    return n;
}

int main(void)
{
    long checks[CHECKS + 16];
    long n = 0, k;
    n = n + enumeration_checks(checks + n);
    n = n + act_checks(checks + n);
    n = n + group_checks(checks + n);
    n = n + inventory_checks(checks + n);
    n = n + surface_checks(checks + n);
    n = n + mask_checks(checks + n);
    n = n + medium_checks(checks + n);
    n = n + transfer_checks(checks + n);
    n = n + grant_checks(checks + n);
    n = n + decider_checks(checks + n);
    n = n + notification_checks(checks + n);
    n = n + rotation_checks(checks + n);
    n = n + pending_checks(checks + n);
    n = n + helper_checks(checks + n);
    if (n != CHECKS)
        return 255;
    for (k = 0; k < n; k++)
        if (!checks[k])
            return (int)(k + 1);
    return 0;
}
