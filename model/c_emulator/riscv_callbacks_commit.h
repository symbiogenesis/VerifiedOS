#pragma once
#include <cstdint>
#include <string>

#include "riscv_callbacks_if.h"
#include "sail.h"

// The capability-widened commit trace: one record per retired instruction and
// one per effect under it, in the schema
// docs/differential-corpus.md versions (M0.12).
//
// It rides the same plumbing RVFI does and for the same reason: the generic
// callbacks already report every effect, and a callbacks class is where a
// per-instruction record is assembled from them. What it does not ride is the
// RVFI *packet*, which is fixed-size and holds one memory access per
// instruction, so it cannot express a block operation or a tag-group load
// (core/rvfi_dii.sail). The packet keeps the subset it can carry, for the RTL's
// `rvfi` port; this stream carries the whole schema.
class commit_callbacks : public callbacks_if {

public:
  explicit commit_callbacks(FILE *trace_log);

  // callbacks_if
  void pre_step_callback(ModelImpl &model, bool is_waiting) override;
  void post_step_callback(ModelImpl &model, bool is_waiting) override;
  void fetch_callback(ModelImpl &model, sbits opcode) override;
  void mem_write_callback(ModelImpl &model, const char *type, uint64_t paddr, int64_t width, lbits value, bool tag)
    override;
  void mem_read_callback(ModelImpl &model, const char *type, uint64_t paddr, int64_t width, lbits value, bool tag)
    override;
  void xreg_full_write_callback(ModelImpl &model, const_sail_string abi_name, sbits reg, uint64_t value, bool tag)
    override;
  void scr_full_write_callback(ModelImpl &model, const_sail_string name, fbits scr, uint64_t value, bool tag) override;
  void csr_full_write_callback(ModelImpl &model, const_sail_string csr_name, unsigned reg, uint64_t value) override;
  void trap_callback(ModelImpl &model, bool is_interrupt, fbits cause) override;

private:
  void record(const std::string &line);
  void access(ModelImpl &model, char kind, uint64_t paddr, int64_t width, lbits value, bool tag);

  FILE *trace_log;
  uint64_t order = 0;
  uint64_t pc = 0;
  uint64_t insn = 0;
  std::string effects;
};
