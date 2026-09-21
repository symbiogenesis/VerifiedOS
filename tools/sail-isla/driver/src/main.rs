// SPDX-License-Identifier: Apache-2.0
//! Concrete replay using isla-testgen's public helper-execution API.
//! The caller supplies SMT-generated code witnesses, never expected outputs.
use isla::opts;
use isla_lib::bitvector::{b129::B129, BV};
use isla_lib::executor::LocalFrame;
use isla_lib::init::initialize_architecture;
use isla_lib::ir::{AssertionMode, Val};
use isla_lib::{smt, zencode};
use isla_testgen::execution::run_function;
use sha2::{Digest, Sha256};

fn bits(value: Val<B129>, width: u32) -> u64 {
    match value {
        Val::Bits(b) if b.len() == width => b.lower_u64(),
        _ => panic!("expected a concrete {width}-bit helper result"),
    }
}

fn main() {
    let options = opts::common_opts();
    let mut hash = Sha256::new();
    let (matches, architecture) = opts::parse::<B129>(&mut hash, &options);
    let parsed = opts::parse_with_arch(&mut hash, &options, &matches, &architecture);
    let mut architecture = parsed.arch;
    let initialized = initialize_architecture(
        &mut architecture, parsed.symtab, parsed.type_info,
        &parsed.isa_config, AssertionMode::Pessimistic, false,
    );
    let state = &initialized.shared_state;
    let function = state.symtab.lookup(&zencode::encode("vos_expand_local"));
    let (arguments, result, instructions) = state.functions.get(&function).unwrap();
    for input in &matches.free {
        let code: u64 = input.parse().expect("permission code must be decimal");
        assert!(code < 32, "permission code exceeds five bits");
        let mut frame = LocalFrame::new(function, arguments, result, None, instructions);
        frame.add_lets(&initialized.lets).add_regs(&initialized.regs);
        let context = smt::Context::new(smt::Config::new());
        let mut solver = smt::Solver::new(&context);
        let wrapper = if code < 16 { "vos_expand_local" } else { "vos_expand_global" };
        let (expanded, mut after, checkpoint) = run_function(
            state, &mut frame, smt::checkpoint(&mut solver), wrapper,
            vec![Val::Bits(B129::new(code & 15, 4))],
        );
        let packed = bits(expanded, 17);
        assert_eq!(packed >> 12, code, "wrapper lost its input witness");
        let expanded = packed & 4095;
        let (narrowed, _, _) = run_function(
            state, &mut after, checkpoint, "perms_narrow",
            vec![Val::Bits(B129::new(expanded, 12))],
        );
        println!("case {code} {expanded} {}", bits(narrowed, 5));
    }
}
