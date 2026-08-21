#pragma once
#include "riscv_callbacks_if.h"
#include "sail.h"

class rvfi_callbacks : public callbacks_if {

public:
  // callbacks_if
  void mem_write_callback(ModelImpl &model, const char *type, uint64_t paddr, int64_t width, lbits value, bool tag)
    override;
  void mem_read_callback(ModelImpl &model, const char *type, uint64_t paddr, int64_t width, lbits value, bool tag)
    override;
  void mem_exception_callback(ModelImpl &model, uint64_t paddr, uint64_t num_of_exception) override;
  void xreg_full_write_callback(ModelImpl &model, const_sail_string abi_name, sbits reg, uint64_t value, bool tag)
    override;
  // No `scr_full_write_callback`: the RVFI packet has no field for the
  // capability registers outside the merged file, its CHERI SCR extension
  // being unimplemented upstream (core/rvfi_dii_v2.sail). The commit trace
  // carries them (M0.12).
  void trap_callback(ModelImpl &model, bool is_interrupt, fbits cause) override;
};
