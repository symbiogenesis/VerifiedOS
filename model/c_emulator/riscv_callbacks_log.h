#pragma once
#include "riscv_callbacks_if.h"
#include "sail.h"

class log_callbacks : public callbacks_if {

public:
  explicit log_callbacks(
    bool config_print_gpr = true,
    bool config_print_vreg = true,
    bool config_print_csr = true,
    bool config_print_mem_access = true,
    bool config_use_abi_names = false,

    FILE *trace_log = nullptr
  );

  // callbacks_if
  void mem_write_callback(ModelImpl &model, const char *type, sbits paddr, int64_t width, lbits value) override;
  void mem_read_callback(ModelImpl &model, const char *type, sbits paddr, int64_t width, lbits value) override;
  void xreg_full_write_callback(ModelImpl &model, const_sail_string abi_name, sbits reg, sbits value) override;
  void csr_full_write_callback(ModelImpl &model, const_sail_string csr_name, unsigned reg, sbits value) override;
  void csr_full_read_callback(ModelImpl &model, const_sail_string csr_name, unsigned reg, sbits value) override;
  void vreg_write_callback(ModelImpl &model, unsigned reg, lbits value) override;

private:
  bool config_print_gpr;
  bool config_print_vreg;
  bool config_print_csr;
  bool config_print_mem_access;
  bool config_use_abi_names;
  FILE *trace_log;
};
