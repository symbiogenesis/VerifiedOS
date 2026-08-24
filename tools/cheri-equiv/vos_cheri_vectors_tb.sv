// SPDX-License-Identifier: Apache-2.0
//
// The SystemVerilog side of the capability-format cross-check.
//
// It reads the vectors `tools/cheri-equiv/gen_vectors.sail` emitted from the
// curated Sail model, computes each answer with `rtl/vos_cheri_pkg`, and writes
// the line back out. Agreement is then a plain text comparison of two files, and
// nothing translates between the two implementations: this reads the same digits
// a person reads and prints digits a person can read beside the model's.
//
// It reformats the *inputs* from the values it parsed rather than echoing the
// characters it read, so that a misparse is a disagreement rather than something
// the echo hides. A line it does not recognise as a vector is copied through, so
// the model's commentary lines compare equal without either side stripping them.
//
// Both file names are fixed rather than taken from a plus-argument, and the run
// happens in a directory of the lane's own: `vectors.txt` in, `replay.txt` out.
// `tools/rtl.py crosscheck` is what puts it there.
//
// This is a checking harness and not hardware. It lives under `tools/` for that
// reason: `rtl/` holds what this repository would synthesize, and a file-reading
// testbench is not that.

module vos_cheri_vectors_tb;

  import vos_cheri_pkg::*;

  // The two files, and what a run decided.
  int unsigned fd_in;
  int unsigned fd_out;
  string       line;
  string       kind;
  int          got;
  longint unsigned vectors;
  longint unsigned skipped;
  longint unsigned unknown;

  // The parsed words. Every input arrives as a 64-bit hex token and is narrowed
  // to the width its field has, which is where a token too wide for its field
  // would be caught.
  logic [63:0] w0;
  logic [63:0] w1;
  logic [63:0] w2;

  // The inputs, at their own widths, which is what makes `%x` print the digits
  // the model printed.
  logic            in_tag;
  cap_bits_t       in_bits;
  cap_addr_t       in_base;
  cap_len_t        in_top;
  logic [Xlen-1:0] in_wide;
  cap_addr_t       in_inc;
  cap_len_t        in_size;

  cap_perms_code_t in_code;
  cap_perms_t      in_mask;
  cap_otype_t      in_otype;

  // The answers.
  capability_t cap;
  capability_t other;
  capability_t checked;
  cap_bounds_t bounds;
  cap_result_t res;
  cap_bits_t   out_bits;
  cap_len_t    out_len;
  logic        out_flag;
  cap_perms_code_t out_code;
  cap_perms_t      out_perms;
  cap_perms_t      out_acc;

  // The twelve accessors, assembled into the bitmap they index, so that an accessor
  // reading the wrong position and an expansion row carrying the wrong bit are two
  // sides of one comparison rather than two things nothing compares.
  function automatic cap_perms_t accessor_bitmap(capability_t c);
    return {cap_access_system_regs(c), cap_permit_unseal(c), cap_permit_seal(c),
            cap_permit_execute(c), cap_load_mutable(c), cap_load_global(c),
            cap_store_local_cap(c), cap_store_cap(c), cap_load_cap(c),
            cap_permit_store(c), cap_permit_load(c), cap_global(c)};
  endfunction

  initial begin
    fd_in  = $fopen("vectors.txt", "r");
    fd_out = $fopen("replay.txt", "w");
    if (fd_in == 0) begin
      $display("FAIL no vectors.txt in the working directory");
      $finish;
    end
    if (fd_out == 0) begin
      $display("FAIL replay.txt could not be opened for writing");
      $finish;
    end

    vectors = 0;
    skipped = 0;
    unknown = 0;

    while ($fgets(line, fd_in) != 0) begin
      if (line.len() < 2 || line[0] == "#") begin
        // commentary and blank lines pass through, so the comparison is over the
        // whole file rather than over a filtered view of it
        $fwrite(fd_out, "%s", line);
        skipped = skipped + 1;
      end else begin
        kind = "";
        got = $sscanf(line, "%s", kind);

        if (kind == "dec") begin
          got = $sscanf(line, "%s %x %x", kind, w0, w1);
          in_tag   = w0[0];
          in_bits  = w1;
          cap      = cap_bits_to_capability(in_tag, in_bits);
          bounds   = get_cap_bounds(cap);
          out_bits = capability_to_bits(cap);
          out_len  = get_cap_length(cap);
          out_flag = cap_bounds_malformed(cap);
          $fwrite(fd_out, "dec %x %x -> %x %x %x %x %x %x %x %x %x %x %x %x\n",
                  in_tag, in_bits,
                  cap.perms, cap.otype, cap.normalized, cap.e, cap.b, cap.t,
                  cap.address, out_bits, bounds.base, bounds.top, out_len,
                  out_flag);
          vectors = vectors + 1;

        end else if (kind == "sb") begin
          got = $sscanf(line, "%s %x %x %x", kind, w0, w1, w2);
          in_bits = w0;
          in_base = w1[CapAddrWidth-1:0];
          in_top  = w2[CapLenWidth-1:0];
          cap     = cap_bits_to_capability(1'b0, in_bits);
          res     = set_cap_bounds(cap, in_base, in_top);
          bounds  = get_cap_bounds(res.cap);
          out_len = get_cap_length(res.cap);
          $fwrite(fd_out, "sb %x %x %x -> %x %x %x %x %x %x %x %x %x\n",
                  in_bits, in_base, in_top,
                  res.ok, res.cap.normalized, res.cap.e, res.cap.b, res.cap.t,
                  res.cap.address, bounds.base, bounds.top, out_len);
          vectors = vectors + 1;

        end else if (kind == "sa") begin
          got = $sscanf(line, "%s %x %x %x", kind, w0, w1, w2);
          in_tag  = w0[0];
          in_bits = w1;
          in_wide = w2;
          cap     = cap_bits_to_capability(in_tag, in_bits);
          res     = set_cap_addr(cap, in_wide);
          checked = set_cap_addr_checked(cap, in_wide);
          $fwrite(fd_out, "sa %x %x %x -> %x %x %x\n",
                  in_tag, in_bits, in_wide, res.ok, res.cap.address, checked.tag);
          vectors = vectors + 1;

        end else if (kind == "so") begin
          got = $sscanf(line, "%s %x %x %x", kind, w0, w1, w2);
          in_tag  = w0[0];
          in_bits = w1;
          in_wide = w2;
          cap     = cap_bits_to_capability(in_tag, in_bits);
          res     = set_cap_offset(cap, in_wide);
          checked = set_cap_offset_checked(cap, in_wide);
          $fwrite(fd_out, "so %x %x %x -> %x %x %x\n",
                  in_tag, in_bits, in_wide, res.ok, res.cap.address, checked.tag);
          vectors = vectors + 1;

        end else if (kind == "io") begin
          got = $sscanf(line, "%s %x %x %x", kind, w0, w1, w2);
          in_tag  = w0[0];
          in_bits = w1;
          in_wide = w2;
          cap     = cap_bits_to_capability(in_tag, in_bits);
          res     = inc_cap_offset(cap, in_wide);
          $fwrite(fd_out, "io %x %x %x -> %x %x\n",
                  in_tag, in_bits, in_wide, res.ok, res.cap.address);
          vectors = vectors + 1;

        end else if (kind == "frc") begin
          got = $sscanf(line, "%s %x %x", kind, w0, w1);
          in_bits  = w0;
          in_inc   = w1[CapAddrWidth-1:0];
          cap      = cap_bits_to_capability(1'b0, in_bits);
          out_flag = fast_rep_check(cap, in_inc);
          $fwrite(fd_out, "frc %x %x -> %x\n", in_bits, in_inc, out_flag);
          vectors = vectors + 1;

        end else if (kind == "ib") begin
          got = $sscanf(line, "%s %x %x %x", kind, w0, w1, w2);
          in_bits  = w0;
          in_wide  = w1;
          in_size  = w2[CapLenWidth-1:0];
          cap      = cap_bits_to_capability(1'b0, in_bits);
          out_flag = in_cap_bounds(cap, in_wide,
                                   {{(Xlen - CapLenWidth){1'b0}}, in_size});
          $fwrite(fd_out, "ib %x %x %x -> %x\n",
                  in_bits, in_wide, in_size, out_flag);
          vectors = vectors + 1;

        end else if (kind == "pe") begin
          got = $sscanf(line, "%s %x", kind, w0);
          in_code   = w0[CapPermsCodeWidth-1:0];
          cap       = NullCap;
          cap.perms = in_code;
          out_perms = perms_expand(in_code);
          out_acc   = accessor_bitmap(cap);
          $fwrite(fd_out, "pe %x -> %x %x\n", in_code, out_perms, out_acc);
          vectors = vectors + 1;

        end else if (kind == "pn") begin
          got = $sscanf(line, "%s %x", kind, w0);
          in_mask   = w0[CapPermsWidth-1:0];
          out_code  = perms_narrow(in_mask);
          out_perms = perms_expand(out_code);
          $fwrite(fd_out, "pn %x -> %x %x\n", in_mask, out_code, out_perms);
          vectors = vectors + 1;

        end else if (kind == "sl") begin
          got = $sscanf(line, "%s %x %x", kind, w0, w1);
          in_bits  = w0;
          in_otype = w1[CapOTypeWidth-1:0];
          cap      = seal_cap(cap_bits_to_capability(1'b1, in_bits), in_otype);
          other    = unseal_cap(cap);
          $fwrite(fd_out, "sl %x %x -> %x %x %x %x %x\n",
                  in_bits, in_otype, is_cap_sealed(cap), has_reserved_otype(cap),
                  is_sentry(cap), capability_to_bits(cap), capability_to_bits(other));
          vectors = vectors + 1;

        end else if (kind == "mb") begin
          got = $sscanf(line, "%s %x %x", kind, w0, w1);
          in_tag   = w0[0];
          in_bits  = w1;
          cap      = cap_bits_to_capability(in_tag, in_bits);
          out_bits = capability_to_mem_bits(cap);
          other    = mem_bits_to_capability(in_tag, out_bits);
          $fwrite(fd_out, "mb %x %x -> %x %x %x\n",
                  in_tag, in_bits, out_bits, other.tag,
                  capability_to_bits(other));
          vectors = vectors + 1;

        end else if (kind == "it") begin
          got = $sscanf(line, "%s %x", kind, w0);
          in_wide = w0;
          cap     = int_to_cap(in_wide);
          $fwrite(fd_out, "it %x -> %x %x %x\n",
                  in_wide, cap.tag, capability_to_bits(cap), cap.address);
          vectors = vectors + 1;

        end else if (kind == "ac") begin
          got = $sscanf(line, "%s %x", kind, w0);
          in_bits = w0;
          cap     = cap_bits_to_capability(1'b0, in_bits);
          $fwrite(fd_out, "ac %x -> %x %x %x %x %x %x\n",
                  in_bits, get_cap_cursor(cap), cap_addr_bits(cap),
                  get_cap_base_bits(cap), get_cap_top_bits(cap),
                  get_cap_offset_bits(cap), cap_to_integer_pc(cap));
          vectors = vectors + 1;

        end else begin
          // A kind this harness does not carry is a vector the cross-check does
          // not decide, and it must **fail** rather than pass. Copying the
          // model's own line through would make the comparison agree on a line
          // nothing computed, so what is written is a line that cannot match any
          // vector the generator emits; the count beside it is what the driver
          // refuses on, so the failure survives even if the line ever could.
          $fwrite(fd_out, "unhandled-kind %s", line);
          unknown = unknown + 1;
        end
      end
    end

    $fclose(fd_out);
    $fclose(fd_in);
    $display("replayed %0d vector(s), %0d commentary line(s), %0d of an unknown kind",
             vectors, skipped, unknown);
    $finish;
  end

endmodule
