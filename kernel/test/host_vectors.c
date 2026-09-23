// SPDX-License-Identifier: Apache-2.0
/*
 * The kernel C's host-model differential against the Gallina front.
 *
 * Reads the vectors tools/quickchick/KernelVectors.v prints, one per line on
 * standard input, rebuilds each line's inputs as the kernel's own records,
 * recomputes every column the kernel implements, and names each disagreement
 * by family, line and column. The `kt` lines belong to the trace reader and
 * are skipped here. Compiled with VOS_HOST_MODEL; nothing here is target code.
 *
 * Fail-closed: an unparsable line, an unknown family, a family with no lines
 * and any disagreement each make the exit status nonzero.
 *
 * Three kinds of expectation are counted apart, because only the first is
 * the Gallina definitions' answer:
 *   - a Gallina disagreement: a column the vector line carries;
 *   - a release expectation: the instant the cursor releases an accepted
 *     table's entry at, which CyclicExecutive.v does not define and this
 *     harness states from R-11-014a and R-11-014d;
 *   - a consumer control: partition.c's refusals of purecap-abi.md section
 *     7, which have no Gallina counterpart and run after the vectors as a
 *     short fixed campaign.
 * Each kind prints its own FAIL total, so a caller can say which one moved.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "vos_kernel.h"

#define LINE_MAX_BYTES 262144
#define TOKENS_MAX 512
#define SHOW_MAX 20

static char line_buf[LINE_MAX_BYTES];
static char *tok[TOKENS_MAX];
static int ntok;
static long line_no;
static long mismatches;
static long expectations;
static long expectation_misses;
static long shown;
static long malformed;

struct family {
  const char *name;
  long lines;
  long bad;
};

static struct family fam_kx = {"kx", 0, 0};
static struct family fam_kc = {"kc", 0, 0};
static struct family fam_kr = {"kr", 0, 0};
static struct family fam_kq = {"kq", 0, 0};
static struct family fam_ke = {"ke", 0, 0};
static long kt_skipped;

/* Tables the executive accepted, and each refusal it gave, over kx. */
static long kx_status[VOS_DISPATCH_STALE_IMAGE + 1];

static void split(char *s)
{
  ntok = 0;
  while (*s != '\0' && ntok < TOKENS_MAX) {
    while (*s == ' ') {
      s++;
    }
    if (*s == '\0') {
      break;
    }
    tok[ntok++] = s;
    while (*s != '\0' && *s != ' ') {
      s++;
    }
    if (*s == ' ') {
      *s++ = '\0';
    }
  }
}

static void differ(struct family *f, const char *column, const char *want, const char *got)
{
  f->bad++;
  mismatches++;
  if (shown < SHOW_MAX) {
    printf("DIFFER %s line %ld column %s: Gallina %s, kernel %s\n", f->name, line_no, column,
           want, got);
    shown++;
  }
}

static void differ_u(struct family *f, const char *column, unsigned long long want,
                     unsigned long long got)
{
  char a[32];
  char b[32];
  if (want == got) {
    return;
  }
  snprintf(a, sizeof a, "%llu", want);
  snprintf(b, sizeof b, "%llu", got);
  differ(f, column, a, b);
}

/* A release expectation this harness states, counted apart from the Gallina
 * columns (see the head of this file). */
static void expect_u(const char *column, unsigned long long want, unsigned long long got)
{
  expectations++;
  if (want == got) {
    return;
  }
  expectation_misses++;
  if (shown < SHOW_MAX) {
    printf("EXPECT kx line %ld column %s: harness %llu, kernel %llu\n", line_no, column, want,
           got);
    shown++;
  }
}

static int bad_line(const char *why)
{
  malformed++;
  if (shown < SHOW_MAX) {
    printf("MALFORMED line %ld: %s\n", line_no, why);
    shown++;
  }
  return 0;
}

static int parse_u64(const char *s, unsigned long long *out)
{
  char *end;
  if (s == 0 || *s == '\0') {
    return 0;
  }
  *out = strtoull(s, &end, 10);
  return *end == '\0';
}

/* "value/tag" */
static int parse_reg(const char *s, vos_cap_t *out)
{
  char copy[64];
  char *slash;
  unsigned long long v;
  unsigned long long t;
  if (strlen(s) >= sizeof copy) {
    return 0;
  }
  strcpy(copy, s);
  slash = strchr(copy, '/');
  if (slash == 0) {
    return 0;
  }
  *slash = '\0';
  if (!parse_u64(copy, &v) || !parse_u64(slash + 1, &t) || t > 1u) {
    return 0;
  }
  out->value = (uint64_t)v;
  out->tag = (uint8_t)t;
  return 1;
}

static int expect(int at, const char *word)
{
  return at < ntok && strcmp(tok[at], word) == 0;
}

/* ------------------------------------------------------------------------
 * kx: kx MF w0 o0 w1 o1 w2 o2 -> D I0 I1 I2 TW | t:i ...
 * ------------------------------------------------------------------------ */
static int check_kx(void)
{
  struct family *f = &fam_kx;
  struct vos_frame fr;
  unsigned long long mf;
  unsigned long long v;
  unsigned long long d;
  unsigned long long inframe[3];
  unsigned long long tw;
  long answer_at_offset[3];
  int i;
  int k;
  int all_in = 1;
  enum vos_status st;
  if (ntok < 15 || !expect(8, "->") || !expect(14, "|")) {
    return bad_line("kx shape");
  }
  memset(&fr, 0, sizeof fr);
  if (!parse_u64(tok[1], &mf)) {
    return bad_line("kx major frame");
  }
  fr.major_frame = mf;
  fr.phase_offset = 0;
  fr.reserved_count = 1;
  fr.slot_count = 3;
  for (i = 0; i < 3; i++) {
    unsigned long long w;
    unsigned long long o;
    if (!parse_u64(tok[2 + 2 * i], &w) || !parse_u64(tok[3 + 2 * i], &o)) {
      return bad_line("kx slot");
    }
    fr.slots[i].width = w;
    fr.slots[i].offset = o;
    fr.slots[i].bound = 0;
    fr.slots[i].period = 100;
    fr.slots[i].tenant = (uint32_t)i;
  }
  if (!parse_u64(tok[9], &d) || !parse_u64(tok[10], &inframe[0])
      || !parse_u64(tok[11], &inframe[1]) || !parse_u64(tok[12], &inframe[2])
      || !parse_u64(tok[13], &tw)) {
    return bad_line("kx verdicts");
  }
  differ_u(f, "pairwise_disjoint", d, (unsigned long long)vos_frame_pairwise_disjoint(&fr));
  for (i = 0; i < 3; i++) {
    differ_u(f, "in_frame", inframe[i],
             (unsigned long long)vos_slot_in_frame(&fr.slots[i], fr.major_frame));
    if (inframe[i] != 1u) {
      all_in = 0;
    }
  }
  differ_u(f, "total_width", tw, (unsigned long long)vos_frame_total_width(&fr));
  for (i = 0; i < 3; i++) {
    answer_at_offset[i] = -2;
  }
  for (k = 15; k < ntok; k++) {
    char copy[64];
    char *colon;
    unsigned long long t;
    long want;
    int32_t got;
    if (strlen(tok[k]) >= sizeof copy) {
      return bad_line("kx probe");
    }
    strcpy(copy, tok[k]);
    colon = strchr(copy, ':');
    if (colon == 0) {
      return bad_line("kx probe");
    }
    *colon = '\0';
    if (!parse_u64(copy, &t)) {
      return bad_line("kx probe instant");
    }
    if (strcmp(colon + 1, "n") == 0) {
      want = VOS_NO_SLOT;
    } else if (parse_u64(colon + 1, &v)) {
      want = (long)v;
    } else {
      return bad_line("kx probe answer");
    }
    got = vos_slot_index_at(&fr, (uint64_t)t);
    if ((long)got != want) {
      char a[32];
      char b[32];
      snprintf(a, sizeof a, "%ld", want);
      snprintf(b, sizeof b, "%ld", (long)got);
      differ(f, "slot_index_at", a, b);
    }
    /* the probe list places slot i's own offset at position 2 + 4i */
    if (k - 15 >= 2 && (k - 15 - 2) % 4 == 0 && (k - 15 - 2) / 4 < 3) {
      answer_at_offset[(k - 15 - 2) / 4] = want;
    }
  }
  st = vos_frame_validate(&fr);
  kx_status[st]++;
  /* The executive may not accept what Gallina's own conjuncts refuse. */
  if (st == VOS_OK && (d != 1u || !all_in)) {
    differ(f, "validate", "a refused conjunct", "accepted");
  }
  if (st == VOS_TABLE_OVERLAP && d != 0u) {
    differ(f, "validate", "disjoint", "overlap");
  }
  if (st == VOS_TABLE_OUTSIDE_FRAME && all_in) {
    differ(f, "validate", "in frame", "outside frame");
  }
  /* For an accepted table, the entry the executive releases at each slot's
   * table instant is the slot Gallina's time-to-slot map names there (a
   * Gallina column), and the instants themselves are this harness's reading
   * of R-11-014a and R-11-014d (release expectations). */
  if (st == VOS_OK) {
    struct vos_exec e;
    vos_exec_start(&e);
    for (i = 0; i < 3; i++) {
      uint64_t at = vos_exec_release(&fr, &e);
      expect_u("release", fr.slots[i].offset, at);
      if (answer_at_offset[i] != (long)vos_exec_slot(&e)) {
        differ(f, "sequence", "the time map's slot", "a different table entry");
      }
      vos_exec_advance(&fr, &e);
    }
    expect_u("wrap", 1u, e.frame_index);
    expect_u("wrap_release", fr.major_frame + fr.slots[0].offset, vos_exec_release(&fr, &e));
  }
  return 1;
}

/* ------------------------------------------------------------------------
 * kc: kc n z sw rot mask count sp pp succ R*32 csr C*count pre R*32 csr C*count
 *        -> S R*32 | c* | p R c* | p
 * ------------------------------------------------------------------------ */
static int check_kc(void)
{
  struct family *f = &fam_kc;
  struct vos_machine m;
  struct vos_context succ;
  struct vos_context pre;
  struct vos_context post;
  struct vos_context rot;
  unsigned long long n;
  unsigned long long z;
  unsigned long long sw;
  unsigned long long ro;
  unsigned long long mask;
  unsigned long long count;
  unsigned long long sp;
  unsigned long long pp;
  unsigned long long v;
  int at;
  uint32_t i;
  if (ntok < 10 || !parse_u64(tok[1], &n) || !parse_u64(tok[2], &z) || !parse_u64(tok[3], &sw)
      || !parse_u64(tok[4], &ro) || !parse_u64(tok[5], &mask) || !parse_u64(tok[6], &count)
      || !parse_u64(tok[7], &sp) || !parse_u64(tok[8], &pp) || count > VOS_MAX_CSRS) {
    return bad_line("kc header");
  }
  memset(&m, 0, sizeof m);
  memset(&succ, 0, sizeof succ);
  memset(&pre, 0, sizeof pre);
  memset(&post, 0, sizeof post);
  memset(&rot, 0, sizeof rot);
  m.csr_count = (uint32_t)count;
  for (i = 0; i < m.csr_count; i++) {
    m.roster[i].csr = i;
    m.roster[i].nameable = (uint8_t)((n >> i) & 1u);
    m.roster[i].zeroized = (uint8_t)((z >> i) & 1u);
  }
  m.pending_swapped = (uint8_t)sw;
  m.rotation_swaps_pending = (uint8_t)ro;
  m.pending_static_mask = mask;
  succ.pending = sp;
  pre.pending = pp;
  at = 9;
  if (!expect(at, "succ")) {
    return bad_line("kc succ");
  }
  at++;
  for (i = 0; i < VOS_REGISTER_COUNT; i++, at++) {
    if (at >= ntok || !parse_reg(tok[at], &succ.reg[i])) {
      return bad_line("kc succ register");
    }
  }
  if (!expect(at, "csr")) {
    return bad_line("kc succ csr");
  }
  at++;
  for (i = 0; i < m.csr_count; i++, at++) {
    if (at >= ntok || !parse_u64(tok[at], &v)) {
      return bad_line("kc succ csr value");
    }
    succ.csr[i] = v;
  }
  if (!expect(at, "pre")) {
    return bad_line("kc pre");
  }
  at++;
  for (i = 0; i < VOS_REGISTER_COUNT; i++, at++) {
    if (at >= ntok || !parse_reg(tok[at], &pre.reg[i])) {
      return bad_line("kc pre register");
    }
  }
  if (!expect(at, "csr")) {
    return bad_line("kc pre csr");
  }
  at++;
  for (i = 0; i < m.csr_count; i++, at++) {
    if (at >= ntok || !parse_u64(tok[at], &v)) {
      return bad_line("kc pre csr value");
    }
    pre.csr[i] = v;
  }
  if (!expect(at, "->") || !expect(at + 1, "S")) {
    return bad_line("kc verdict");
  }
  at += 2;
  vos_switch_image(&m, &succ, &pre, &post);
  vos_rotation_image(&m, &succ, &pre, &rot);
  for (i = 0; i < VOS_REGISTER_COUNT; i++, at++) {
    vos_cap_t want;
    if (at >= ntok || !parse_reg(tok[at], &want)) {
      return bad_line("kc switch register");
    }
    differ_u(f, "switch_register_value", want.value, post.reg[i].value);
    differ_u(f, "switch_register_tag", want.tag, post.reg[i].tag);
    differ_u(f, "rotation_register_value", want.value, rot.reg[i].value);
    differ_u(f, "rotation_register_tag", want.tag, rot.reg[i].tag);
  }
  if (!expect(at, "|")) {
    return bad_line("kc switch csr");
  }
  at++;
  for (i = 0; i < m.csr_count; i++, at++) {
    if (at >= ntok) {
      return bad_line("kc switch csr value");
    }
    if (strcmp(tok[at], "-") != 0) {
      if (!parse_u64(tok[at], &v)) {
        return bad_line("kc switch csr value");
      }
      differ_u(f, "switch_csr", v, post.csr[i]);
    }
  }
  if (!expect(at, "|") || at + 1 >= ntok || !parse_u64(tok[at + 1], &v)) {
    return bad_line("kc switch pending");
  }
  differ_u(f, "switch_pending", v, post.pending);
  at += 2;
  if (!expect(at, "R")) {
    return bad_line("kc rotation");
  }
  at++;
  for (i = 0; i < m.csr_count; i++, at++) {
    if (at >= ntok) {
      return bad_line("kc rotation csr value");
    }
    if (strcmp(tok[at], "-") != 0) {
      if (!parse_u64(tok[at], &v)) {
        return bad_line("kc rotation csr value");
      }
      differ_u(f, "rotation_csr", v, rot.csr[i]);
    }
  }
  if (!expect(at, "|") || at + 1 >= ntok) {
    return bad_line("kc rotation pending");
  }
  if (strcmp(tok[at + 1], "-") != 0) {
    if (!parse_u64(tok[at + 1], &v)) {
      return bad_line("kc rotation pending");
    }
    differ_u(f, "rotation_pending", v, rot.pending);
  }
  if (at + 2 != ntok) {
    return bad_line("kc trailing tokens");
  }
  return 1;
}

/* ------------------------------------------------------------------------
 * kr: kr mask R*31 -> sanitized nostale_image nostale_filtered | tag*31
 * ------------------------------------------------------------------------ */
static int check_kr(void)
{
  struct family *f = &fam_kr;
  struct vos_bitmap bm;
  struct vos_context succ;
  struct vos_context filtered;
  unsigned long long mask;
  unsigned long long v;
  unsigned long long san;
  unsigned long long nostale;
  unsigned long long nostale_filtered;
  int at;
  uint32_t r;
  int got;
  if (ntok != 1 + 1 + 31 + 1 + 3 + 1 + 31 || !parse_u64(tok[1], &mask)) {
    return bad_line("kr shape");
  }
  memset(&succ, 0, sizeof succ);
  bm.marked = mask;
  at = 2;
  for (r = 1u; r < VOS_REGISTER_COUNT; r++, at++) {
    if (!parse_reg(tok[at], &succ.reg[r])) {
      return bad_line("kr register");
    }
  }
  if (!expect(at, "->") || !parse_u64(tok[at + 1], &san) || !parse_u64(tok[at + 2], &nostale)
      || !parse_u64(tok[at + 3], &nostale_filtered) || !expect(at + 4, "|")) {
    return bad_line("kr verdicts");
  }
  got = vos_image_sanitized(&bm, &succ);
  differ_u(f, "sanitized", san, (unsigned long long)got);
  differ_u(f, "image_carries_no_stale", nostale, (unsigned long long)got);
  differ_u(f, "dispatch_check", san ? VOS_OK : VOS_DISPATCH_STALE_IMAGE,
           (unsigned long long)vos_dispatch_check(&bm, &succ));
  filtered = succ;
  at += 5;
  for (r = 1u; r < VOS_REGISTER_COUNT; r++, at++) {
    int t = vos_filtered_tag(&bm, succ.reg[r]);
    if (!parse_u64(tok[at], &v)) {
      return bad_line("kr filtered tag");
    }
    differ_u(f, "filtered_tag", v, (unsigned long long)t);
    filtered.reg[r].tag = (uint8_t)t;
  }
  differ_u(f, "filtered_carries_no_stale", nostale_filtered,
           (unsigned long long)vos_image_sanitized(&bm, &filtered));
  return 1;
}

/* kq: kq b0 b1 b2 b3 b4 b5 -> sem epoch */
static int check_kq(void)
{
  struct family *f = &fam_kq;
  struct vos_completion c;
  unsigned long long b[6];
  unsigned long long sem;
  int i;
  if (ntok != 10 || !expect(7, "->")) {
    return bad_line("kq shape");
  }
  for (i = 0; i < 6; i++) {
    if (!parse_u64(tok[1 + i], &b[i]) || b[i] > 1u) {
      return bad_line("kq field");
    }
  }
  if (!parse_u64(tok[8], &sem)) {
    return bad_line("kq verdict");
  }
  c.bits_published = (uint8_t)b[0];
  c.epoch_advanced = (uint8_t)b[1];
  c.resident_roots_cleared = (uint8_t)b[2];
  c.saved_contexts_filtered = (uint8_t)b[3];
  c.loans_cancelled = (uint8_t)b[4];
  c.device_boundary_reached = (uint8_t)b[5];
  differ_u(f, "semantic_completion", sem, (unsigned long long)vos_semantic_completion(&c));
  return 1;
}

/* "x:y", two decimals: an extent's base and top, or a probe and its answer. */
static int parse_pair(const char *s, unsigned long long *x, unsigned long long *y)
{
  char copy[64];
  char *colon;
  if (strlen(s) >= sizeof copy) {
    return 0;
  }
  strcpy(copy, s);
  colon = strchr(copy, ':');
  if (colon == 0) {
    return 0;
  }
  *colon = '\0';
  return parse_u64(copy, x) && parse_u64(colon + 1, y);
}

static int parse_extent(const char *s, struct vos_extent *out)
{
  unsigned long long b;
  unsigned long long t;
  if (!parse_pair(s, &b, &t)) {
    return 0;
  }
  out->base = (uint64_t)b;
  out->top = (uint64_t)t;
  return 1;
}

/* ------------------------------------------------------------------------
 * ke p A B -> eqb separated compatible | p:w p:w p:w p:w
 * ------------------------------------------------------------------------ */
static int check_ke_pair(void)
{
  struct family *f = &fam_ke;
  struct vos_extent a;
  struct vos_extent b;
  unsigned long long eq;
  unsigned long long sep;
  unsigned long long comp;
  unsigned long long p;
  unsigned long long w;
  int k;
  if (ntok != 13 || !expect(4, "->") || !expect(8, "|")) {
    return bad_line("ke p shape");
  }
  if (!parse_extent(tok[2], &a) || !parse_extent(tok[3], &b)) {
    return bad_line("ke p extent");
  }
  if (!parse_u64(tok[5], &eq) || !parse_u64(tok[6], &sep) || !parse_u64(tok[7], &comp)) {
    return bad_line("ke p verdicts");
  }
  differ_u(f, "extent_eqb", eq, (unsigned long long)vos_extent_equal(&a, &b));
  differ_u(f, "separated", sep, (unsigned long long)vos_extent_separated(&a, &b));
  differ_u(f, "compatible", comp, (unsigned long long)vos_extent_compatible(&a, &b));
  for (k = 9; k < ntok; k++) {
    if (!parse_pair(tok[k], &p, &w)) {
      return bad_line("ke p probe");
    }
    differ_u(f, "within", w, (unsigned long long)vos_extent_within(&a, (uint64_t)p));
  }
  return 1;
}

/* ------------------------------------------------------------------------
 * ke r SW E0 E1 E2 t T0 T1 T2 -> readable
 *
 * Tenant i declares extent Ei; the frame's three slots, reserved first, name
 * tenants T0 to T2. The kernel answers through the descriptor it validates.
 * ------------------------------------------------------------------------ */
static int check_ke_readable(void)
{
  struct family *f = &fam_ke;
  struct vos_init_desc d;
  unsigned long long want;
  unsigned long long t;
  int i;
  if (ntok != 12 || !expect(6, "t") || !expect(10, "->")) {
    return bad_line("ke r shape");
  }
  memset(&d, 0, sizeof d);
  if (!parse_extent(tok[2], &d.switch_text)) {
    return bad_line("ke r switch text");
  }
  d.partition_count = 3;
  for (i = 0; i < 3; i++) {
    d.partitions[i].tenant = (uint32_t)i;
    d.partitions[i].has_context = 1;
    if (!parse_extent(tok[3 + i], &d.partitions[i].text)) {
      return bad_line("ke r extent");
    }
  }
  d.frame.major_frame = 200;
  d.frame.reserved_count = 1;
  d.frame.slot_count = 3;
  for (i = 0; i < 3; i++) {
    if (!parse_u64(tok[7 + i], &t) || t > 2u) {
      return bad_line("ke r tenant");
    }
    d.frame.slots[i].tenant = (uint32_t)t;
  }
  if (!parse_u64(tok[11], &want)) {
    return bad_line("ke r verdict");
  }
  differ_u(f, "readable", want, (unsigned long long)vos_extents_readable(&d));
  return 1;
}

/* ------------------------------------------------------------------------
 * The consumer checks: fixed refusal controls with no Gallina counterpart.
 * ------------------------------------------------------------------------ */

static void base_descriptor(struct vos_init_desc *d)
{
  memset(d, 0, sizeof *d);
  d->composition_id = 7;
  d->hart_id = 0;
  d->root.base = 1000;
  d->root.top = 2000;
  d->switch_text.base = 10;
  d->switch_text.top = 20;
  d->partition_count = 2;
  d->partitions[0].tenant = 0;
  d->partitions[0].has_context = 1;
  d->partitions[0].text.base = 1000;
  d->partitions[0].text.top = 1100;
  d->partitions[0].data.base = 1100;
  d->partitions[0].data.top = 1200;
  d->partitions[1].tenant = 1;
  d->partitions[1].has_context = 1;
  d->partitions[1].text.base = 1200;
  d->partitions[1].text.top = 1300;
  d->partitions[1].data.base = 1300;
  d->partitions[1].data.top = 1400;
  d->window_count = 1;
  d->windows[0].base = 3000;
  d->windows[0].top = 3100;
  d->frame.major_frame = 200;
  d->frame.reserved_count = 1;
  d->frame.slot_count = 2;
  d->frame.slots[0].width = 60;
  d->frame.slots[0].offset = 0;
  d->frame.slots[0].tenant = 0;
  d->frame.slots[1].width = 90;
  d->frame.slots[1].offset = 60;
  d->frame.slots[1].tenant = 1;
  d->machine.csr_count = 2;
}

static long consumer_checks;
static long consumer_failures;

static void consumer(const char *name, enum vos_status want, enum vos_status got)
{
  consumer_checks++;
  if (want != got) {
    consumer_failures++;
    printf("CONSUMER %s: expected status %d, kernel returned %d\n", name, (int)want, (int)got);
  }
}

static void run_consumer_checks(void)
{
  struct vos_init_desc d;
  base_descriptor(&d);
  consumer("accepted descriptor", VOS_OK, vos_init_validate(&d, 7, 0));
  consumer("missing descriptor", VOS_INIT_MISSING, vos_init_validate(0, 7, 0));
  consumer("wrong composition", VOS_INIT_WRONG_COMPOSITION, vos_init_validate(&d, 8, 0));
  consumer("wrong hart", VOS_INIT_WRONG_HART, vos_init_validate(&d, 7, 1));
  base_descriptor(&d);
  d.partitions[1].has_context = 0;
  consumer("slot without a planned successor", VOS_INIT_NO_PLANNED_SUCCESSOR,
           vos_init_validate(&d, 7, 0));
  base_descriptor(&d);
  d.frame.slots[1].tenant = 5;
  consumer("slot naming no partition", VOS_INIT_NO_PLANNED_SUCCESSOR,
           vos_init_validate(&d, 7, 0));
  base_descriptor(&d);
  d.partitions[1].data.top = 2100;
  consumer("data extent past the root", VOS_INIT_EXTENT_OUTSIDE_ROOT,
           vos_init_validate(&d, 7, 0));
  base_descriptor(&d);
  d.partitions[0].text.top = d.partitions[0].text.base;
  consumer("empty text extent", VOS_INIT_EXTENT_MALFORMED, vos_init_validate(&d, 7, 0));
  base_descriptor(&d);
  d.switch_text.base = 1050;
  d.switch_text.top = 1060;
  consumer("switch text inside a partition's text", VOS_INIT_EXTENTS_UNREADABLE,
           vos_init_validate(&d, 7, 0));
  base_descriptor(&d);
  d.partitions[1].text.base = 1050;
  d.partitions[1].text.top = 1150;
  d.partitions[1].data.base = 1300;
  consumer("two partitions' text extents overlap", VOS_INIT_EXTENTS_UNREADABLE,
           vos_init_validate(&d, 7, 0));
  base_descriptor(&d);
  d.frame.slots[1].offset = 30;
  consumer("overlapping slots", VOS_TABLE_OVERLAP, vos_init_validate(&d, 7, 0));
  base_descriptor(&d);
  d.frame.slots[0].offset = 150;
  d.frame.slots[0].width = 50;
  consumer("list order not time order", VOS_TABLE_UNORDERED, vos_init_validate(&d, 7, 0));
  base_descriptor(&d);
  d.window_count = VOS_MAX_WINDOWS + 1u;
  consumer("too many windows", VOS_INIT_TOO_MANY_WINDOWS, vos_init_validate(&d, 7, 0));
  base_descriptor(&d);
  d.machine.csr_count = VOS_MAX_CSRS + 1u;
  consumer("roster past capacity", VOS_ROSTER_TOO_LARGE, vos_init_validate(&d, 7, 0));
  base_descriptor(&d);
  d.partitions[1].tenant = 0;
  d.frame.slots[1].tenant = 0;
  consumer("two partitions carrying one tenant", VOS_INIT_TENANT_SHARED,
           vos_init_validate(&d, 7, 0));
}

static void report_family(const struct family *f, int *failed)
{
  printf("   %-3s %6ld line(s), %ld disagreement(s)\n", f->name, f->lines, f->bad);
  if (f->lines == 0) {
    printf("FAIL family %s carried no line; an empty comparison decides nothing\n", f->name);
    *failed = 1;
  }
}

int main(void)
{
  int failed = 0;
  int i;
  while (fgets(line_buf, sizeof line_buf, stdin) != 0) {
    size_t len = strlen(line_buf);
    line_no++;
    if (len == sizeof line_buf - 1u && line_buf[len - 1u] != '\n') {
      bad_line("line longer than the buffer");
      return 2;
    }
    while (len > 0u && (line_buf[len - 1u] == '\n' || line_buf[len - 1u] == '\r')) {
      line_buf[--len] = '\0';
    }
    if (len == 0u) {
      continue;
    }
    split(line_buf);
    if (ntok == 0) {
      continue;
    }
    if (strcmp(tok[0], "kx") == 0) {
      fam_kx.lines++;
      check_kx();
    } else if (strcmp(tok[0], "kc") == 0) {
      fam_kc.lines++;
      check_kc();
    } else if (strcmp(tok[0], "kr") == 0) {
      fam_kr.lines++;
      check_kr();
    } else if (strcmp(tok[0], "kq") == 0) {
      fam_kq.lines++;
      check_kq();
    } else if (strcmp(tok[0], "ke") == 0) {
      fam_ke.lines++;
      if (expect(1, "p")) {
        check_ke_pair();
      } else if (expect(1, "r")) {
        check_ke_readable();
      } else {
        bad_line("unknown ke kind");
      }
    } else if (strcmp(tok[0], "kt") == 0) {
      kt_skipped++;
    } else {
      bad_line("unknown family");
    }
  }
  run_consumer_checks();
  printf("== kernel host model against the Gallina front\n");
  report_family(&fam_kx, &failed);
  report_family(&fam_kc, &failed);
  report_family(&fam_kr, &failed);
  report_family(&fam_kq, &failed);
  report_family(&fam_ke, &failed);
  printf("   kt  %6ld line(s) left to the trace reader\n", kt_skipped);
  printf("   executive verdicts over kx:");
  for (i = 0; i <= (int)VOS_DISPATCH_STALE_IMAGE; i++) {
    if (kx_status[i] != 0) {
      printf(" status%d=%ld", i, kx_status[i]);
    }
  }
  printf("\n");
  printf("   release expectations over accepted kx tables: %ld checked, %ld missed "
         "(stated by this harness, not by Gallina)\n",
         expectations, expectation_misses);
  printf("   consumer checks: %ld run, %ld failed (fixed controls, not generated)\n",
         consumer_checks, consumer_failures);
  if (expectations == 0) {
    printf("FAIL no release expectation was checked; an empty comparison decides nothing\n");
    failed = 1;
  }
  if (malformed != 0) {
    printf("FAIL %ld malformed line(s)\n", malformed);
    failed = 1;
  }
  if (mismatches != 0) {
    printf("FAIL %ld disagreement(s) between the kernel C and the Gallina definitions\n",
           mismatches);
    failed = 1;
  }
  if (expectation_misses != 0) {
    printf("FAIL %ld release expectation(s) stated by this harness\n", expectation_misses);
    failed = 1;
  }
  if (consumer_failures != 0) {
    printf("FAIL %ld consumer check(s)\n", consumer_failures);
    failed = 1;
  }
  if (!failed) {
    printf("ok the kernel C agrees with the Gallina front on %ld generated line(s), and "
           "meets %ld release expectation(s) and %ld fixed consumer control(s) this "
           "harness states\n",
           fam_kx.lines + fam_kc.lines + fam_kr.lines + fam_kq.lines + fam_ke.lines,
           expectations, consumer_checks);
  }
  return failed ? 1 : 0;
}
