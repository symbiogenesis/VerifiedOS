#pragma once
#include "riscv_callbacks_if.h"
#include "sail.h"

class rvfi_callbacks : public callbacks_if {

public:
  // callbacks_if
  void mem_write_callback(ModelImpl &model, const char *type, uint64_t paddr, int64_t width, lbits value) override;
  void mem_read_callback(ModelImpl &model, const char *type, uint64_t paddr, int64_t width, lbits value) override;
  void mem_exception_callback(ModelImpl &model, uint64_t paddr, uint64_t num_of_exception) override;
  void xreg_full_write_callback(ModelImpl &model, const_sail_string abi_name, sbits reg, uint64_t value) override;
  void trap_callback(ModelImpl &model, bool is_interrupt, fbits cause) override;
};
