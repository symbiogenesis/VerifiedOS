#include "target_regs.h"
#include "config_utils.h"
#include "protocol_handler.h"
#include "riscv_model_impl.h"

#include <sstream>

register_map get_register_map() {
  // The floating-point annex is gone with scalar floating point
  // (docs/isa-profile.md, R-15-039): there are no `f0`-`f31` and no `fcsr`,
  // so the debugger sees the integer registers and the PC and nothing after
  // them.  Vector state is not exposed here either, as upstream does not.
  register_map map = {
    // TODO: handle the E base ISA
    .pc_offset = 32,
  };
  return map;
}

std::string get_target_xml(const ModelImpl &model) {
  const register_map map = get_register_map();
  std::ostringstream xml;

  xml << R"(<?xml version="1.0"?>
<!DOCTYPE target SYSTEM "gdb-target.dtd">
<target version="1.0">
)";

  // Current architectures are `riscv:rv32`, `riscv:rv64`, with
  // `riscv` being a default.
  xml << "<architecture>";
  if (model.xlen() == 32) {
    xml << "riscv:rv32";
  } else {
    xml << "riscv:rv64";
  }
  xml << "</architecture>" << std::endl;

  // The `org.gnu.gdb.riscv.cpu` feature is required for RISC-V
  // targets. It should contain the registers `x0` through `x31`, and
  // `pc`. Either the architectural names (`x0`, `x1`, etc) can be
  // used, or the ABI names (`zero`, `ra`, etc).
  xml << R"(<feature name="org.gnu.gdb.riscv.cpu">)" << std::endl;
  // TODO: handle 16 registers for the E base ISA.
  int regnum = 0;
  for (int i = 0; i < 32; ++i) {
    std::string typ = (i == 1) ? "code_ptr" : ((i == 2 || i == 3 || i == 4 || i == 8) ? "data_ptr" : "int");
    xml << "  <reg name=\"x" << i << "\" bitsize=\"" << model.xlen() << "\" type=\"" << typ
        << "\" save-restore=\"yes\" group=\"general\"";
    if (i == 0) {
      xml << R"( regnum="0" )";
    }
    xml << "/>" << std::endl;
    ++regnum;
  }
  assert(regnum == map.pc_offset);
  xml << "  <reg name=\"pc\" bitsize=\"" << model.xlen()
      << "\" type=\"code_ptr\" save-restore=\"yes\" group=\"general\"/>" << std::endl;
  xml << "</feature>" << std::endl;

  // The optional `org.gnu.gdb.riscv.fpu` feature is not emitted: it holds
  // `f0`-`f31` and `fcsr`, none of which exist here (R-15-039).

  xml << "</target>" << std::endl;
  return xml.str();
}

// get_general_regs:
//
// Response is of the form 'XX..'
// Each byte of register data is described by two hex digits. The
// bytes with the register are transmitted in target byte order. The
// size of each register and their position within the `g` packet are
// determined by the target description (the above XML).

namespace {

// This assumes `buf` has been set up with std::hex and std::setfill.
void append_reg(std::ostringstream &buf, uint64_t val, int64_t width) {
  // Send bytes in little-endian order.
  // TODO: handle big-endian model.
  for (int64_t i = 0; i < width; ++i) {
    unsigned byte = val & 0xff;
    buf << std::setw(2) << byte;
    val >>= 8;
  }
}

} // namespace

std::string get_general_regs(protocol_handler &proto_handler) {
  const register_map map = proto_handler.get_register_map();
  ModelImpl &model = proto_handler.get_model();
  std::ostringstream buf;
  buf << std::hex << std::setfill('0');
  int64_t int_width_bytes = model.xlen() / 8;

  for (int64_t i = 0; i < map.pc_offset; ++i) {
    const uint64_t val = model.xreg(i);
    append_reg(buf, val, int_width_bytes);
  }
  append_reg(buf, model.pc(), int_width_bytes);
  return buf.str();
}

std::string get_register(protocol_handler &proto_handler, uint64_t regidx) {
  int64_t idx = static_cast<int64_t>(regidx);
  const register_map map = proto_handler.get_register_map();
  ModelImpl &model = proto_handler.get_model();

  std::ostringstream buf;
  buf << std::hex << std::setfill('0');
  int64_t int_width_bytes = model.xlen() / 8;

  if (0 <= idx && idx < map.pc_offset) {
    uint64_t val = model.xreg(idx);
    append_reg(buf, val, int_width_bytes);
  } else if (idx == map.pc_offset) {
    append_reg(buf, model.pc(), int_width_bytes);
  } else {
    buf << "E.invalid_register_idx";
  }
  return buf.str();
}

std::string set_register(protocol_handler &proto_handler, uint64_t regidx, uint64_t val) {
  int64_t reg = static_cast<int64_t>(regidx);
  const register_map map = proto_handler.get_register_map();
  ModelImpl &model = proto_handler.get_model();

  if (0 <= reg && reg < map.pc_offset) {
    model.set_xreg(reg, val);
  } else if (reg == map.pc_offset) {
    model.set_pc(val);
  } else {
    return "E.invalid_register_idx";
  }

  return "OK";
}
