// SPDX-License-Identifier: Apache-2.0
// CertiRocq CodegenWasm/LambdaANF_to_Wasm.v: constructors use 32-bit cells,
// boxed ordinal followed by fields; nil is 1 and bool uses false=1/true=3.
import { readFileSync } from "fs";

const [modulePath, populationPath] = process.argv.slice(2);
const ids = JSON.parse(readFileSync(populationPath, "utf8"));
if (!Array.isArray(ids) || !ids.length || new Set(ids).size !== ids.length)
  throw new Error("missing or duplicated observation identities");
const { instance } = await WebAssembly.instantiate(readFileSync(modulePath), { env: {} });
instance.exports.main_function();
if (instance.exports.out_of_mem.value !== 0) throw new Error("Wasm allocation failed");
const memory = new DataView(instance.exports.memory.buffer);
let pointer = instance.exports.result.value >>> 0;
const seen = new Set();
const checks = [];
while (pointer !== 1) {
  if (pointer % 4 !== 0 || pointer + 12 > memory.byteLength || seen.has(pointer)
      || checks.length >= ids.length || memory.getUint32(pointer, true) !== 0)
    throw new Error("malformed, cyclic or oversized Boolean list");
  seen.add(pointer);
  const value = memory.getUint32(pointer + 4, true);
  if (value !== 1 && value !== 3) throw new Error("non-Boolean list element");
  checks.push([ids[checks.length], value === 3]);
  pointer = memory.getUint32(pointer + 8, true);
}
if (checks.length !== ids.length) throw new Error("truncated Boolean list");
const failure = checks.findIndex(([, value]) => !value);
console.log(JSON.stringify({ schema: "vos-component-vector/1", checks,
                             first_failure: failure < 0 ? 0 : failure + 1 }));
