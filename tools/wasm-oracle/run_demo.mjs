// Minimal host for the M1.5 oracle smoke program: instantiate the module
// CertiRocq emits (import-free), call main_function, and decode the boolean
// result. Constructor encoding per CertiCoq-Wasm: nullary constructors are
// unboxed odd-tagged scalars, ordered by declaration, so bool's true is the
// first constructor and false the second.
import { readFileSync } from "fs";

const path = process.argv[2];
if (!path) {
  console.error("usage: node run_demo.js <file.wasm>");
  process.exit(2);
}

const bytes = readFileSync(path);
const { instance } = await WebAssembly.instantiate(new Uint8Array(bytes), {
  env: {},
});

instance.exports.main_function();
if (instance.exports.out_of_mem.value === 1) {
  console.error("out of memory");
  process.exit(1);
}

// bool per tests/wasm/js/modules/pp.js print_bool: odd-tagged unboxed
// scalar, payload in the upper bits — 1 is true, 0 is false.
const raw = instance.exports.result.value;
if (raw & 1) {
  const b = raw >> 1 === 1;
  console.log(b ? "true" : "false");
  process.exit(b ? 0 : 1);
}
console.error(`unexpected boxed result: ${raw}`);
process.exit(1);
