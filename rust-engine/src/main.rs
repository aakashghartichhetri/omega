//! OMEGA batch scheduler. It proposes assignments; Python independently verifies them.
//! Input lines: OMEGA1|machines, W|comma-separated durations,
//! C|id|order|order_arg|placement|placement_seed|passes|canary, END.
//! Output: S|id|workload_index|comma-separated machine numbers.

use std::cmp::Reverse;
use std::io::{self, Read, Write};

#[derive(Debug)]
struct Candidate {
    id: usize,
    order: String,
    order_arg: u64,
    placement: String,
    placement_seed: u64,
    passes: usize,
    canary: bool,
}

fn parse_number<T: std::str::FromStr>(text: &str) -> Result<T, String> {
    text.parse::<T>().map_err(|_| format!("invalid number: {text}"))
}

fn mix64(mut value: u64) -> u64 {
    // Stable integer mixing means the same inputs produce the same permutations.
    value = value.wrapping_add(0x9E3779B97F4A7C15);
    value = (value ^ (value >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94D049BB133111EB);
    value ^ (value >> 31)
}

fn job_order(durations: &[u64], order: &str, parameter: u64) -> Vec<usize> {
    let mut indices: Vec<usize> = (0..durations.len()).collect();
    indices.sort_by_key(|&i| (Reverse(durations[i]), i));
    match order {
        "longest" => {}
        "shortest" => indices.reverse(),
        "zigzag" => {
            let mut output = Vec::with_capacity(indices.len());
            let mut left = 0;
            let mut right = indices.len();
            while left < right {
                output.push(indices[left]);
                left += 1;
                if left < right {
                    right -= 1;
                    output.push(indices[right]);
                }
            }
            indices = output;
        }
        "windowed" => {
            let size = (parameter as usize).max(2);
            for (chunk_index, chunk) in indices.chunks_mut(size).enumerate() {
                if chunk_index % 2 == 1 {
                    chunk.reverse();
                }
            }
        }
        "shuffled" => {
            let mut state = mix64(parameter ^ 0xACED_1234);
            for i in (1..indices.len()).rev() {
                state = mix64(state);
                let j = (state % ((i + 1) as u64)) as usize;
                indices.swap(i, j);
            }
        }
        _ => {}
    }
    indices
}

fn choose_machine(
    loads: &[u64], placement: &str, salt: u64, step: usize, job: usize,
) -> usize {
    let count = loads.len();
    match placement {
        "round_robin" => step % count,
        "second_least" => {
            let mut machines: Vec<usize> = (0..count).collect();
            machines.sort_by_key(|&machine| (loads[machine], machine));
            machines[1.min(count - 1)]
        }
        "power_of_two" => {
            let first = (mix64(salt ^ (job as u64) ^ ((step as u64) << 32)) % (count as u64)) as usize;
            let offset = (mix64(salt ^ (step as u64) ^ 0x1234) % ((count - 1) as u64)) as usize;
            let second = (first + 1 + offset) % count;
            if (loads[first], first) <= (loads[second], second) { first } else { second }
        }
        _ => (0..count).min_by_key(|&machine| (loads[machine], machine)).unwrap_or(0),
    }
}

fn makespan(loads: &[u64]) -> u64 {
    *loads.iter().max().unwrap_or(&0)
}

fn improve_once(assignments: &mut [usize], durations: &[u64], machine_count: usize) -> bool {
    let mut loads = vec![0_u64; machine_count];
    for (job, &machine) in assignments.iter().enumerate() {
        loads[machine] += durations[job];
    }
    let previous = makespan(&loads);

    // First accept a strictly beneficial single-job move.
    for job in 0..assignments.len() {
        let source = assignments[job];
        for target in 0..machine_count {
            if source == target { continue; }
            loads[source] -= durations[job];
            loads[target] += durations[job];
            let improved = makespan(&loads) < previous;
            loads[source] += durations[job];
            loads[target] -= durations[job];
            if improved {
                assignments[job] = target;
                return true;
            }
        }
    }

    // If moving cannot help, a pairwise exchange sometimes can.
    for first in 0..assignments.len() {
        for second in (first + 1)..assignments.len() {
            let a = assignments[first];
            let b = assignments[second];
            if a == b { continue; }
            loads[a] = loads[a] - durations[first] + durations[second];
            loads[b] = loads[b] - durations[second] + durations[first];
            let improved = makespan(&loads) < previous;
            loads[a] = loads[a] - durations[second] + durations[first];
            loads[b] = loads[b] - durations[first] + durations[second];
            if improved {
                assignments[first] = b;
                assignments[second] = a;
                return true;
            }
        }
    }
    false
}

fn schedule(durations: &[u64], machine_count: usize, recipe: &Candidate) -> Vec<usize> {
    let mut loads = vec![0_u64; machine_count];
    let mut assignments = vec![0; durations.len()];
    let indices = job_order(durations, &recipe.order, recipe.order_arg);
    for (step, job) in indices.into_iter().enumerate() {
        let machine = choose_machine(&loads, &recipe.placement, recipe.placement_seed, step, job);
        loads[machine] += durations[job];
        assignments[job] = machine;
    }
    for _ in 0..recipe.passes {
        if !improve_once(&mut assignments, durations, machine_count) { break; }
    }
    if recipe.canary {
        // Deliberate negative control: verifies Python rejects an extra assignment.
        assignments.push(0);
    }
    assignments
}

fn run(input: &str, writer: &mut impl Write) -> Result<(), String> {
    let mut lines = input.lines();
    let header = lines.next().ok_or("missing header")?;
    let mut head = header.split('|');
    if head.next() != Some("OMEGA1") { return Err("unsupported protocol".into()); }
    let machines: usize = parse_number(head.next().ok_or("missing machine count")?)?;
    if machines < 2 || machines > 12 || head.next().is_some() {
        return Err("machine count out of range".into());
    }
    let mut workloads: Vec<Vec<u64>> = Vec::new();
    let mut candidates: Vec<Candidate> = Vec::new();
    let mut ended = false;
    for line in lines {
        if line == "END" { ended = true; break; }
        let parts: Vec<&str> = line.split('|').collect();
        match parts.as_slice() {
            ["W", values] => {
                let durations: Vec<u64> = values.split(',').map(parse_number).collect::<Result<_, _>>()?;
                if durations.len() < 2 || durations.len() > 60 || durations.iter().any(|&n| n == 0 || n > 1_000_000) {
                    return Err("invalid workload".into());
                }
                workloads.push(durations);
            }
            ["C", id, order, order_arg, placement, placement_seed, passes, canary] => {
                if !matches!(*order, "longest" | "shortest" | "zigzag" | "windowed" | "shuffled")
                    || !matches!(*placement, "least_loaded" | "round_robin" | "second_least" | "power_of_two") {
                    return Err("unknown strategy".into());
                }
                let passes: usize = parse_number(passes)?;
                if passes > 3 { return Err("too many improvement passes".into()); }
                candidates.push(Candidate {
                    id: parse_number(id)?, order: (*order).into(), order_arg: parse_number(order_arg)?,
                    placement: (*placement).into(), placement_seed: parse_number(placement_seed)?,
                    passes, canary: *canary == "1",
                });
            }
            _ => return Err(format!("unrecognized input: {line}")),
        }
    }
    if !ended || workloads.is_empty() || workloads.len() > 24 || candidates.is_empty() || candidates.len() > 2000 {
        return Err("missing END or invalid batch size".into());
    }
    for candidate in &candidates {
        for (case_index, workload) in workloads.iter().enumerate() {
            let assignments = schedule(workload, machines, candidate);
            let assignments = assignments.iter().map(usize::to_string).collect::<Vec<_>>().join(",");
            writeln!(writer, "S|{}|{}|{}", candidate.id, case_index, assignments)
                .map_err(|err| err.to_string())?;
        }
    }
    Ok(())
}

fn main() {
    let mut input = String::new();
    if let Err(error) = io::stdin().read_to_string(&mut input) {
        eprintln!("input error: {error}");
        std::process::exit(1);
    }
    let stdout = io::stdout();
    let mut writer = io::BufWriter::new(stdout.lock());
    if let Err(error) = run(&input, &mut writer) {
        eprintln!("engine error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn candidate(order: &str, placement: &str, passes: usize) -> Candidate {
        Candidate { id: 0, order: order.into(), order_arg: 3, placement: placement.into(),
                    placement_seed: 0, passes, canary: false }
    }

    #[test]
    fn lpt_balances_a_small_example() {
        let durations = [9, 8, 7, 6];
        let assignments = schedule(&durations, 2, &candidate("longest", "least_loaded", 0));
        let mut loads = [0, 0];
        for (job, machine) in assignments.iter().enumerate() { loads[*machine] += durations[job]; }
        assert_eq!(loads, [15, 15]);
    }

    #[test]
    fn all_heuristics_assign_each_job() {
        let jobs = [12, 11, 10, 3, 5, 4, 13, 7];
        for order in ["longest", "shortest", "zigzag", "windowed", "shuffled"] {
            for placement in ["least_loaded", "round_robin", "second_least", "power_of_two"] {
                let result = schedule(&jobs, 3, &candidate(order, placement, 3));
                assert_eq!(result.len(), jobs.len());
                assert!(result.iter().all(|&machine| machine < 3));
            }
        }
    }

    #[test]
    fn local_improvement_never_worsens_makespan() {
        let jobs = [15, 14, 13, 12, 11, 10, 9, 8];
        let before = schedule(&jobs, 3, &candidate("shortest", "round_robin", 0));
        let after = schedule(&jobs, 3, &candidate("shortest", "round_robin", 3));
        let score = |assignment: Vec<usize>| {
            let mut loads = [0, 0, 0];
            for (i, m) in assignment.iter().enumerate() { loads[*m] += jobs[i]; }
            *loads.iter().max().unwrap()
        };
        assert!(score(after) <= score(before));
    }

    #[test]
    fn invalid_canary_adds_an_extra_assignment() {
        let mut recipe = candidate("longest", "least_loaded", 0);
        recipe.canary = true;
        assert_eq!(schedule(&[4, 5, 6, 7], 2, &recipe).len(), 5);
    }

    #[test]
    fn accepts_two_job_playground_and_twenty_four_benchmark_cases() {
        let mut input = String::from("OMEGA1|2\n");
        for _ in 0..24 { input.push_str("W|1000000,1\n"); }
        input.push_str("C|0|longest|0|least_loaded|0|0|0\nEND\n");
        let mut output = Vec::new();
        run(&input, &mut output).unwrap();
        assert_eq!(String::from_utf8(output).unwrap().lines().count(), 24);
    }

    #[test]
    fn protocol_emits_expected_line() {
        let input = "OMEGA1|2\nW|9,8,7,6\nC|0|longest|0|least_loaded|0|0|0\nEND\n";
        let mut output = Vec::new();
        run(input, &mut output).unwrap();
        assert_eq!(String::from_utf8(output).unwrap(), "S|0|0|0,1,1,0\n");
    }
}
