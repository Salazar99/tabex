use std::fs;

use stlcc::formula::join_with;
use stlcc::node::NODE_ID;
use stlcc::smt::SmtSolver;
use stlcc::tableau::Tableau;
use stlcc::tableau::config::{ConfigSource, get_tableau_options};

fn main() {
    let (options, filename) = get_tableau_options(ConfigSource::Cli);
    let file_content = fs::read_to_string(&filename).unwrap();
    let example = file_content.lines().next().unwrap();

    if options.fol {
        let start = std::time::Instant::now();
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
            println!("FOL result: {:?}", res);
            println!("DURATION_SEC: {:.6}", duration.as_secs_f64());
        }
    } else {
        let start = std::time::Instant::now();
        let mut tableau = Tableau::new(options);
        let res = tableau.make_tableau_from_str(example);
        let duration = start.elapsed();

        if tableau.options.smtlib_result {
            match res {
                Some(true) => println!("sat"),
                Some(false) => println!("unsat"),
                None => println!("unknown"),
            }
        } else {
            println!("Tableau result: {:?}", res);
            println!("DURATION_SEC: {:.6}", duration.as_secs_f64());
        }

        if tableau.options.graph_output
            && let Ok(graph) = tableau.graph.unwrap().to_dot_string()
        {
            println!("Node count: {:?}", NODE_ID);
            fs::write("resources/tmp/g.dot", &graph).expect("Unable to write file");
        }

        if let Some(core) = tableau.unsat_core
            && matches!(res, Some(false))
        {
            println!(
                "Unsat core: {}",
                join_with(core.get_unsat_core().as_slice(), " && ")
            );
        }
    }
}
