// SPDX-License-Identifier: Apache-2.0
// Authored adapter; the external coreba dependency retains its upstream MIT license.
use coreba::{algo, Job, JobSet};
use std::{env, fs, sync::Arc};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 4 { return Err("expected input, output, iterations".into()); }
    let iterations: u32 = args[3].parse()?;
    if !(1..=100).contains(&iterations) { return Err("invalid iteration bound".into()); }
    let mut jobs: JobSet = Vec::new();
    for (index, line) in fs::read_to_string(&args[1])?.lines().enumerate() {
        let fields: Vec<usize> = line.split('\t').map(str::parse).collect::<Result<_, _>>()?;
        if fields.len() != 3 || fields[0] == 0 || fields[2] < fields[1] + 2 {
            return Err("invalid positive-size open-interval job".into());
        }
        let mut job = Job::new();
        job.id = index.try_into()?;
        job.size = fields[0];
        job.req_size = fields[0];
        job.birth = fields[1];
        job.death = fields[2];
        jobs.push(Arc::new(job));
    }
    if jobs.is_empty() { return Err("empty instance".into()); }
    let (placement, _untrusted_height) = algo::idealloc(jobs, 1.0, 0, iterations);
    let mut rows: Vec<_> = placement.iter().collect();
    rows.sort_by_key(|(id, _)| **id);
    let mut output = String::new();
    for (id, placed) in rows {
        output.push_str(&format!("{}\t{}\n", id, placed.offset.get()));
    }
    // Python validates every identity and offset against the original instance.
    fs::write(&args[2], output)?;
    Ok(())
}
