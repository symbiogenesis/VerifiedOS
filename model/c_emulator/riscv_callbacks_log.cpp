#include "riscv_callbacks_log.h"
#include "riscv_model_impl.h"
#include <algorithm>
#include <inttypes.h>
#include <vector>

log_callbacks::log_callbacks(
  bool config_print_gpr,
  bool config_print_vreg,
  bool config_print_csr,
  bool config_print_mem_access,
  bool config_use_abi_names,
  FILE *trace_log
) :
    config_print_gpr(config_print_gpr),
    config_print_vreg(config_print_vreg),
    config_print_csr(config_print_csr),
    config_print_mem_access(config_print_mem_access),
    config_use_abi_names(config_use_abi_names),
    trace_log(trace_log) {
}

// Implementations of default callbacks for trace printing.
// The model assumes that these functions do not change the state of the model.

// The tag rides beside the value in every one of these, because on this machine
// a value and its authority are one register and one granule: `t:0` is a
// statement about the access rather than a placeholder (R-15-007i, R-15-007r).

void log_callbacks::mem_write_callback(
  ModelImpl &model,
  const char *type,
  uint64_t paddr,
  int64_t width,
  lbits value,
  bool tag
) {
  // This is just passed due to Sail type system requirements.
  (void)width;
  if (trace_log != nullptr && config_print_mem_access) {
    fprintf(
      trace_log,
      "mem[%s,0x%0*" PRIX64 "] <- t:%d ",
      type,
      static_cast<int>((model.physaddrbits_len() + 3) / 4),
      paddr,
      tag ? 1 : 0
    );
    gmp_fprintf(trace_log, "0x%0*ZX\n", value.len / 4, *value.bits);
  }
}

void log_callbacks::mem_read_callback(
  ModelImpl &model,
  const char *type,
  uint64_t paddr,
  int64_t width,
  lbits value,
  bool tag
) {
  // This is just passed due to Sail type system requirements.
  (void)width;
  if (trace_log != nullptr && config_print_mem_access) {
    fprintf(
      trace_log,
      "mem[%s,0x%0*" PRIX64 "] -> t:%d ",
      type,
      static_cast<int>((model.physaddrbits_len() + 3) / 4),
      paddr,
      tag ? 1 : 0
    );
    gmp_fprintf(trace_log, "0x%0*ZX\n", value.len / 4, *value.bits);
  }
}

void log_callbacks::xreg_full_write_callback(
  ModelImpl &,
  const_sail_string abi_name,
  sbits reg,
  uint64_t value,
  bool tag
) {
  if (trace_log != nullptr && config_print_gpr) {
    if (config_use_abi_names) {
      fprintf(trace_log, "%s <- t:%d 0x%0*" PRIX64 "\n", abi_name, tag ? 1 : 0, 16 /* XLEN=64 */, value);
    } else {
      fprintf(
        trace_log,
        "x%" PRIu64 " <- t:%d 0x%0*" PRIX64 "\n",
        reg.bits,
        tag ? 1 : 0,
        16 /* XLEN=64 */,
        value
      );
    }
  }
}

void log_callbacks::scr_full_write_callback(
  ModelImpl &,
  const_sail_string name,
  fbits scr,
  uint64_t value,
  bool tag
) {
  if (trace_log != nullptr && config_print_csr) {
    fprintf(
      trace_log,
      "SCR %s (%" PRIu64 ") <- t:%d 0x%0*" PRIX64 "\n",
      name,
      scr,
      tag ? 1 : 0,
      16 /* XLEN=64 */,
      value
    );
  }
}


void log_callbacks::csr_full_write_callback(ModelImpl &, const_sail_string csr_name, unsigned reg, uint64_t value) {
  if (trace_log != nullptr && config_print_csr) {
    fprintf(
      trace_log,
      "CSR %s (0x%03X) <- 0x%0*" PRIX64 "\n",
      csr_name,
      reg,
      16 /* XLEN=64 */,
      value
    );
  }
}

void log_callbacks::csr_full_read_callback(ModelImpl &, const_sail_string csr_name, unsigned reg, uint64_t value) {
  if (trace_log != nullptr && config_print_csr) {
    fprintf(
      trace_log,
      "CSR %s (0x%03X) -> 0x%0*" PRIX64 "\n",
      csr_name,
      reg,
      16 /* XLEN=64 */,
      value
    );
  }
}

void log_callbacks::vreg_write_callback(ModelImpl &, unsigned reg, lbits value) {
  if (trace_log != nullptr && config_print_vreg) {
    fprintf(trace_log, "v%d <- ", reg);
    gmp_fprintf(trace_log, "0x%0*ZX\n", value.len / 4, *value.bits);
  }
}

