use std::env;
use std::fs;
use std::path::Path;

use stlcc::formula::parser::parse_formula;
use stlcc::node::Node;

const MLTL: bool = true;
const SIMPLIFICATIONS: bool = true;
const OPTIMIZATIONS: bool = true;

fn collect_stl_files(dir: &Path, files: &mut Vec<std::path::PathBuf>) {
    if dir.is_dir() {
        for entry in fs::read_dir(dir).unwrap() {
            let entry = entry.unwrap();
            let path = entry.path();
            if path.is_dir() {
                collect_stl_files(&path, files);
            } else if path.extension().and_then(|s| s.to_str()) == Some("mltl") {
                files.push(path);
            }
        }
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!("Usage: {} <directory>", args[0]);
        std::process::exit(1);
    }

    let dir_path = &args[1];
    let dir = Path::new(dir_path);

    if !dir.is_dir() {
        eprintln!("Error: {dir_path} is not a directory");
        std::process::exit(1);
    }

    // Collect all .stl files recursively
    let mut stl_files = Vec::new();
    collect_stl_files(dir, &mut stl_files);

    // Prepare CSV output
    let mut csv_output = Vec::new();
    csv_output
        .push("filename,depth,temporal_depth,length,bool_vars,real_vars,disjunctions".to_string());

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

                            if !MLTL {
                                node.mltl_rewrite();
                            }

                            // Formula Optimization Stage
                            if SIMPLIFICATIONS {
                                node.simplify();
                            }

                            node.flatten();

                            if OPTIMIZATIONS {
                                node.shift_bounds();
                            }

                            let operands = node.operands.len();

                            let formula = node.to_formula();

                            let depth = formula.depth();
                            let temporal_depth = formula.temporal_operator_depth();
                            let length = formula.length();
                            let bool_vars = formula.boolean_variables();
                            let real_vars = formula.real_variables();
                            let disjunction = formula.combinatorial_branching_count();

                            csv_output.push(format!(
                                "{filename},{operands},{depth},{temporal_depth},{length},{bool_vars},{real_vars},{disjunction}"
                            ));
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
    let output_file = &args[2];
    let csv_content = csv_output.join("\n");
    if let Err(e) = fs::write(output_file, csv_content) {
        eprintln!("Error writing to file {output_file}: {e}");
        std::process::exit(1);
    }
}
