#include "riscv_callbacks_commit.h"
#include "riscv_model_impl.h"

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <gmp.h>
#include <inttypes.h>

namespace {

// A bitvector as fixed-width uppercase hex. The width is the vector's, not the
// value's, so a store of zero and a store of the same zero at another width are
// different records rather than the same one.
std::string hex_of(lbits value) {
  char *raw = mpz_get_str(nullptr, -16, *value.bits);
  std::string out(raw);
  void (*release)(void *, size_t) = nullptr;
  mp_get_memory_functions(nullptr, nullptr, &release);
  release(raw, std::strlen(raw) + 1);

  const size_t digits = static_cast<size_t>((value.len + 3) / 4);
  if (out.size() < digits) {
    out.insert(0, digits - out.size(), '0');
  }
  return out;
}

std::string formatted(const char *format, ...) {
  va_list args;
  va_start(args, format);
  char buffer[160];
  vsnprintf(buffer, sizeof(buffer), format, args);
  va_end(args);
  return std::string(buffer);
}

} // namespace

commit_callbacks::commit_callbacks(FILE *trace_log) : trace_log(trace_log) {
}

void commit_callbacks::record(const std::string &line) {
  effects += line;
}

// A step's records are buffered and emitted together, so the instruction record
// leads the effects it caused rather than trailing them: an effect belongs to
// the instruction above it, which is what makes the stream a *commit* trace and
// not an event log.
void commit_callbacks::pre_step_callback(ModelImpl &model, bool) {
  pc = model.pc();
  insn = 0;
  effects.clear();
}

void commit_callbacks::post_step_callback(ModelImpl &, bool is_waiting) {
  if (trace_log == nullptr || is_waiting) {
    return;
  }
  fprintf(trace_log, "I %" PRIu64 " %016" PRIX64 " %08" PRIX64 "\n", order, pc, insn);
  fputs(effects.c_str(), trace_log);
  effects.clear();
  ++order;
}

void commit_callbacks::fetch_callback(ModelImpl &, sbits opcode) {
  insn = opcode.bits;
}

void commit_callbacks::access(ModelImpl &model, char kind, uint64_t paddr, int64_t width, lbits value, bool tag) {
  record(formatted(
    "%c %0*" PRIX64 " %" PRId64 " %d %s\n",
    kind,
    static_cast<int>((model.physaddrbits_len() + 3) / 4),
    paddr,
    width,
    tag ? 1 : 0,
    hex_of(value).c_str()
  ));
}

void commit_callbacks::mem_write_callback(
  ModelImpl &model,
  const char *,
  uint64_t paddr,
  int64_t width,
  lbits value,
  bool tag
) {
  access(model, 'W', paddr, width, value, tag);
}

void commit_callbacks::mem_read_callback(
  ModelImpl &model,
  const char *type,
  uint64_t paddr,
  int64_t width,
  lbits value,
  bool tag
) {
  // Instruction fetches are dropped rather than reported. They carry nothing
  // the instruction record above them does not, they arrive in 16-bit granules
  // so there are two of them per instruction, and no `rvfi` port reports them,
  // so an executor that fetched differently could not be compared on them
  // anyway.
  if (type != nullptr && std::strcmp(type, "X") == 0) {
    return;
  }
  access(model, 'R', paddr, width, value, tag);
}

void commit_callbacks::xreg_full_write_callback(ModelImpl &, const_sail_string, sbits reg, uint64_t value, bool tag) {
  record(formatted("X %" PRIu64 " %d %016" PRIX64 "\n", reg.bits, tag ? 1 : 0, value));
}

void commit_callbacks::scr_full_write_callback(ModelImpl &, const_sail_string, fbits scr, uint64_t value, bool tag) {
  record(formatted("S %" PRIu64 " %d %016" PRIX64 "\n", scr, tag ? 1 : 0, value));
}

void commit_callbacks::csr_full_write_callback(ModelImpl &, const_sail_string, unsigned reg, uint64_t value) {
  record(formatted("C %03X %016" PRIX64 "\n", reg, value));
}

void commit_callbacks::trap_callback(ModelImpl &, bool is_interrupt, fbits cause) {
  record(formatted("T %d %" PRIu64 "\n", is_interrupt ? 1 : 0, cause));
}
