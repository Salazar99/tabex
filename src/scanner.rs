use std::fs;
use std::path::Path;

use clap::Parser;
use stlcc::formula::Formula;
use stlcc::formula::parser::parse_formula;
use stlcc::node::Node;

const MLTL: bool = false;
//const SIMPLIFICATIONS: bool = true;
//const OPTIMIZATIONS: bool = true;

fn collect_stl_files(dir: &Path, files: &mut Vec<std::path::PathBuf>) {
    if dir.is_dir() {
        for entry in fs::read_dir(dir).unwrap() {
            let entry = entry.unwrap();
            let path = entry.path();
            if path.is_dir() {
                collect_stl_files(&path, files);
            } else if path.extension().and_then(|s| s.to_str()) == Some("stl") {
                files.push(path);
            }
        }
    }
}

#[derive(Parser)]
#[command(name = "scanner")]
#[command(about = "Scan STL files and output statistics")]
struct Args {
    /// Input directory containing STL files
    directory: String,

    /// Output CSV file (optional, defaults to stdout)
    #[arg(short, long)]
    output: Option<String>,
}

/// Returns the CSV header for formula statistics (depth, temporal_depth, horizon, nodes, temporal_nodes, propositional_nodes, f_nodes, g_nodes, u_nodes, r_nodes, bool_vars, real_vars).
#[must_use]
pub fn stats_header() -> &'static str {
    "depth,temporal_depth,horizon,nodes,temporal_nodes,propositional_nodes,f_nodes,g_nodes,u_nodes,r_nodes,bool_vars,real_vars,branching_factor"
}

/// Returns a closure that extracts formula statistics as a vector of strings.
#[must_use]
pub fn stats_extractor() -> impl Fn(&Formula) -> Vec<String> {
    |f: &Formula| {
        let nodes = f.nodes();
        let temporal_nodes = f.count_nodes(|form| matches!(form, Formula::F { .. } | Formula::G { .. } | Formula::U { .. } | Formula::R { .. }));
        let propositional_nodes = f.count_nodes(|form| matches!(form, Formula::Prop(_)));
        let f_nodes = f.count_nodes(|form| matches!(form, Formula::F { .. }));
        let g_nodes = f.count_nodes(|form| matches!(form, Formula::G { .. }));
        let u_nodes = f.count_nodes(|form| matches!(form, Formula::U { .. }));
        let r_nodes = f.count_nodes(|form| matches!(form, Formula::R { .. }));
        let branching_factor: f32 = f.branching_factor_avg();
        vec![
            f.depth().to_string(),
            f.temporal_operator_depth().to_string(),
            f.horizon().to_string(),
            nodes.to_string(),
            temporal_nodes.to_string(),
            propositional_nodes.to_string(),
            f_nodes.to_string(),
            g_nodes.to_string(),
            u_nodes.to_string(),
            r_nodes.to_string(),
            f.boolean_variables().to_string(),
            f.real_variables().to_string(),
            branching_factor.to_string(),
        ]
    }
}

fn main() {
    let args = Args::parse();

    let dir = Path::new(&args.directory);

    if !dir.is_dir() {
        eprintln!("Error: {} is not a directory", args.directory);
        std::process::exit(1);
    }

    // Collect all .stl files recursively
    let mut stl_files = Vec::new();
    collect_stl_files(dir, &mut stl_files);

    // Prepare CSV output
    let mut csv_output = Vec::new();
    let full_header = format!(
        "filename,operands,{}",
        stats_header()
    );
    csv_output.push(full_header);

    for file_path in stl_files {
        let filename = file_path
            .strip_prefix(dir)
            .unwrap_or(&file_path)
            .to_str()
            .unwrap();
        match fs::read_to_string(&file_path) {
            Ok(content) => {
                for (line_num, line) in content.lines().enumerate() {
                    let line = line.trim();
                    if line.is_empty() || line.starts_with('#') {
                        continue; // Skip empty lines and comments
                    }

                    match parse_formula(line) {
                        Ok((remaining, formula)) => {
                            if !remaining.is_empty() {
                                eprintln!(
                                    "Warning: remaining unparsed content in {} line {}: '{}'",
                                    filename,
                                    line_num + 1,
                                    remaining
                                );
                            }

                            let mut node = Node::from_operands(vec![formula]);

                            // Normalization Stage
                            node.negative_normal_form_rewrite();
                            node.flatten();

                            if !MLTL {
                                node.mltl_rewrite();
                            }

                            let operands = node.operands.len();

                            let formula = node.to_formula();
                            let stats = stats_extractor()(&formula);

                            csv_output.push(format!("{filename},{operands},{}", stats.join(",")));
                        }
                        Err(e) => {
                            eprintln!("Parse error in {} line {}: {:?}", filename, line_num + 1, e);
                        }
                    }
                }
            }
            Err(e) => {
                eprintln!("Error reading file {filename}: {e}");
            }
        }
    }

    // Output CSV to file
    let output_file = args.output.unwrap_or_else(|| "output.csv".to_string());
    let csv_content = csv_output.join("\n");
    if let Err(e) = fs::write(&output_file, csv_content) {
        eprintln!("Error writing to file {output_file}: {e}");
        std::process::exit(1);
    }
}
