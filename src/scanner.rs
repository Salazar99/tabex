use std::fs;
use std::path::Path;

use clap::Parser;
use stlcc::formula::parser::parse_formula;
use stlcc::node::Node;

const MLTL: bool = false;
const SIMPLIFICATIONS: bool = true;
const OPTIMIZATIONS: bool = true;

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
    csv_output.push(
        "filename,operands,depth,temporal_depth,length,bool_vars,real_vars"
            .to_string(),
    );

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

                            csv_output.push(format!(
                                "{filename},{operands},{depth},{temporal_depth},{length},{bool_vars},{real_vars}"
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
    let output_file = args.output.unwrap_or_else(|| "output.csv".to_string());
    let csv_content = csv_output.join("\n");
    if let Err(e) = fs::write(&output_file, csv_content) {
        eprintln!("Error writing to file {output_file}: {e}");
        std::process::exit(1);
    }
}
