#pragma once

#include "sail.h"

class callbacks_if;

namespace hart {

class Model;

struct zMemoryAccessTypezIEmem_payloadz5zK;

} // namespace hart

// The Model class derives from this one so when Sail calls C callback
// functions it actually calls methods of this class. However they are
// virtual functions so they actually call the Platform implementations
// (see riscv_model_impl.h). It's done this way because:
//
// a) This allows the platform implementation to access the Model.
// b) This allows exposing the Model in the library without fixing
//    the Platform implementation.

class PlatformInterface {
public:
  virtual unit fetch_callback(sbits opcode);

  virtual unit mem_write_callback(const char *type, uint64_t paddr, int64_t width, lbits value);

  virtual unit mem_read_callback(const char *type, uint64_t paddr, int64_t width, lbits value);

  virtual unit mem_exception_callback(uint64_t paddr, uint64_t num_of_exception);

  virtual unit xreg_full_write_callback(const_sail_string abi_name, sbits reg, uint64_t value);


  virtual unit csr_full_write_callback(const_sail_string csr_name, unsigned reg, uint64_t value);

  virtual unit csr_full_read_callback(const_sail_string csr_name, unsigned reg, uint64_t value);

  virtual unit vreg_write_callback(unsigned reg, lbits value);

  virtual unit pc_write_callback(uint64_t new_pc);

  virtual unit redirect_callback(uint64_t new_pc);

  virtual unit trap_callback(bool is_interrupt, fbits cause);
  virtual unit xret_callback(bool is_mret);
  virtual unit instret_callback(unit);

  virtual unit plat_term_write(mach_bits);

  virtual bool sys_enable_experimental_extensions(unit);

  virtual unit print_string(const_sail_string prefix, const_sail_string msg);
  virtual unit print_log(const_sail_string s);
  virtual unit print_log_instr(const_sail_string s, uint64_t pc);
  virtual unit print_step(unit);

  virtual bool get_config_print_instr(unit);
  virtual bool get_config_print_clint(unit);
  virtual bool get_config_print_exception(unit);
  virtual bool get_config_print_interrupt(unit);
  virtual bool get_config_print_htif(unit);
  virtual bool get_config_print_pma(unit);
  virtual bool get_config_rvfi(unit);
  virtual bool get_config_use_abi_names(unit);
};
