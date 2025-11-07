use std::fs;
use std::time::Instant;

use stlcc::formula::join_with;
use stlcc::sat::config::{ConfigSource, ExecutionMode, GeneralOptions, TableauOptions, get_config};
use stlcc::sat::smt::SmtSolver;
use stlcc::sat::tableau::Tableau;
use stlcc::sat::tableau::node::NODE_ID;

fn main() {
    let (mode, options, tableau_options, filename) = get_config(ConfigSource::Cli);
    let file_content = fs::read_to_string(&filename).unwrap();
    let formula = file_content.lines().next().unwrap();

    match mode {
        ExecutionMode::Fol => run_fol(formula, options),
        ExecutionMode::Tableau => run_tableau(formula, options, tableau_options),
    }
}

fn run_fol(example: &str, options: GeneralOptions) {
    let start = Instant::now();
    let mut smt_solver = SmtSolver::new(options);
    let res = smt_solver.make_smt_from_str(example);
    let duration = start.elapsed();

    if smt_solver.options.smtlib_result {
        match res {
            Some(true) => println!("sat"),
            Some(false) => println!("unsat"),
            None => println!("unknown"),
        }
    } else {
        println!("FOL result: {res:?}");
        println!("DURATION_SEC: {:.6}", duration.as_secs_f64());
    }
}

fn run_tableau(example: &str, options: GeneralOptions, tableau_options: TableauOptions) {
    let start = Instant::now();
    let mut tableau = Tableau::new(options, tableau_options);
    let res = tableau.make_tableau_from_str(example);
    let duration = start.elapsed();

    if tableau.options.smtlib_result {
        match res {
            Some(true) => println!("sat"),
            Some(false) => println!("unsat"),
            None => println!("unknown"),
        }
    } else {
        println!("Tableau result: {res:?}");
        println!("DURATION_SEC: {:.6}", duration.as_secs_f64());
    }

    if tableau.tableau_options.graph_output
        && let Some(graph) = &tableau.graph
        && let Ok(dot) = graph.to_dot_string()
    {
        println!("Node count: {NODE_ID:?}");
        fs::write("resources/tmp/g.dot", &dot).expect("Unable to write file");
    }

    if let Some(core) = &tableau.unsat_core
        && matches!(res, Some(false))
    {
        println!(
            "Unsat core: {}",
            join_with(core.get_unsat_core().as_slice(), " && ")
        );
    }

    if let Some(trace) = &tableau.trace {
        println!("Trace length: {}", trace.length());
        println!("[");
        for (i, seq) in trace.full_trace().iter().enumerate() {
            let inner = seq
                .iter()
                .map(std::string::ToString::to_string)
                .collect::<Vec<_>>()
                .join(", ");
            let comma = if i + 1 < trace.full_trace().len() {
                ","
            } else {
                ""
            };
            println!("  [{inner}]{comma}");
        }
        println!("]");
    }
}
