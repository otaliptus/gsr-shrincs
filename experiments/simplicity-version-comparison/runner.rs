//! Standalone evaluator: all inputs are witness values, no transaction jets.
use simplicity::{BitMachine, dag::{DagLike, InternalSharing}, node::Inner};
use simplicityhl::{Arguments, CompiledProgram, WitnessValues, ast::ElementsJetHinter};
use serde_json::json;
use std::{fs, io::{self, BufRead}, time::Instant, collections::BTreeSet};
mod c_measure;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let source = fs::read_to_string(std::env::args().nth(1).ok_or("missing source path")?)?;
    let compiled = CompiledProgram::new(source, Arguments::default(), false, Box::new(ElementsJetHinter::new()))?;
    let env = simplicityhl::dummy_env::dummy();
    for line in io::stdin().lock().lines() {
        let request: serde_json::Value = serde_json::from_str(&line?)?;
        let witness_json = request["witness"].to_string();
        let witnesses: WitnessValues = serde_json::from_str(&witness_json)?;
        let satisfied = compiled.satisfy(witnesses)?;
        let redeem = satisfied.redeem();
        let mut machine = BitMachine::for_program(redeem)?;
        let accepted = machine.exec(redeem, &env).is_ok();
        if !accepted {
            println!("{}", json!({"success":false}));
            continue;
        }
        let pruned = redeem.prune(&env)?;
        let (program, witness) = pruned.to_vec_with_witness();
        let (unpruned, _) = redeem.to_vec_with_witness();
        let mut times = Vec::new();
        let repeats = request["repeats"].as_u64().unwrap_or(1).clamp(1, 100);
        for _ in 0..repeats {
            let mut machine = BitMachine::for_program(&pruned)?;
            let start = Instant::now();
            machine.exec(&pruned, &env)?;
            times.push(start.elapsed().as_nanos() as u64);
        }
        let mut jets = BTreeSet::new();
        for item in pruned.as_ref().post_order_iter::<InternalSharing>() {
            if let Inner::Jet(jet) = item.node.inner() { jets.insert(jet.to_string()); }
        }
        let hex = |bytes: &[u8]| bytes.iter().map(|x| format!("{x:02x}")).collect::<String>();
        let bounds = pruned.bounds();
        let (c_execution, c_validation) = c_measure::measure(&program, &witness, env.c_tx_env(), repeats)?;
        let analysis = simplicity::ffi::tests::run_program(&program, &witness,
            simplicity::ffi::tests::TestUpTo::ComputeCostBounded, None, Some(env.c_tx_env()))
            .map_err(|e| format!("C cost analysis: {e:?}"))?;
        println!("{}", json!({"success":true,"program_bytes":program.len(),
            "unpruned_program_bytes":unpruned.len(),"witness_bytes":witness.len(),
            "program_hex":hex(&program),"witness_hex":hex(&witness),
            "cmr":pruned.cmr().to_string(),"cost_bound":bounds.cost.to_string(),
            "extra_cells_bound":bounds.extra_cells,"extra_frames_bound":bounds.extra_frames,
            "execution_ns":times,"c_execution_ns":c_execution,"c_validation_ns":c_validation,
            "c_cost_bound":analysis.cost_bound,"jets":jets}));
    }
    Ok(())
}
