use clap::Parser;

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum ExecutionMode {
    Tableau,
    Fol,
}

#[derive(Clone, Debug, Default)]
pub struct GeneralOptions {
    pub mltl: bool,
    pub smtlib_result: bool,
}

#[derive(Clone, Debug)]
pub struct TableauOptions {
    pub max_depth: usize,
    pub graph_output: Option<String>,
    pub memoization: bool,
    pub simple_first: bool,
    pub formula_optimizations: bool,
    pub jump_rule_enabled: bool,
    pub formula_simplifications: bool,
    pub unsat_core_extraction: bool,
    pub trace_extraction: bool,
}

impl Default for TableauOptions {
    fn default() -> Self {
        TableauOptions {
            max_depth: 1000000,
            graph_output: None,
            memoization: true,
            simple_first: true,
            formula_optimizations: true,
            jump_rule_enabled: true,
            formula_simplifications: true,
            unsat_core_extraction: false,
            trace_extraction: false,
        }
    }
}

#[derive(Parser)]
#[command(name = "stlsat")]
#[command(about = "STLSAT - Signal Temporal Logic Satisfiability Checker")]
pub struct CliArgs {
    /// Input formula file
    pub formula_file: String,

    /// Maximum depth for tableau construction
    #[arg(long, default_value_t = TableauOptions::default().max_depth)]
    pub max_depth: usize,

    /// Output graph to file
    #[arg(long)]
    pub graph_output: Option<String>,

    /// Disable memoization
    #[arg(long = "no-memoization", action = clap::ArgAction::SetFalse)]
    pub memoization: bool,

    /// Disable process simple formulas first
    #[arg(long = "no-simple-first", action = clap::ArgAction::SetFalse)]
    pub simple_first: bool,

    /// Disable formula syntactic optimizations
    #[arg(long = "no-formula-optimizations", action = clap::ArgAction::SetFalse)]
    pub formula_optimizations: bool,

    /// Disable jump rule
    #[arg(long = "no-jump-rule", action = clap::ArgAction::SetFalse)]
    pub jump_rule_enabled: bool,

    /// Disable formula syntactic simplifications
    #[arg(long = "no-formula-simplifications", action = clap::ArgAction::SetFalse)]
    pub formula_simplifications: bool,

    /// Use MLTL semantics
    #[arg(long, default_value_t = GeneralOptions::default().mltl)]
    pub mltl: bool,

    /// Print result in smtlib format
    #[arg(long, default_value_t = GeneralOptions::default().smtlib_result)]
    pub smtlib_result: bool,

    /// Enable unsat core extraction
    #[arg(long, default_value_t = TableauOptions::default().unsat_core_extraction)]
    pub unsat_core_extraction: bool,

    /// Enable trace extraction
    #[arg(long, default_value_t = TableauOptions::default().trace_extraction)]
    pub trace_extraction: bool,

    /// Enable FOL encoding
    #[arg(long, default_value_t = false)]
    pub fol: bool,
}

pub enum ConfigSource {
    Cli,
}

#[must_use]
pub fn get_config(source: ConfigSource) -> (ExecutionMode, GeneralOptions, TableauOptions, String) {
    match source {
        ConfigSource::Cli => {
            let args = CliArgs::parse();

            let mode = if args.fol {
                ExecutionMode::Fol
            } else {
                ExecutionMode::Tableau
            };

            let general = GeneralOptions {
                mltl: args.mltl,
                smtlib_result: args.smtlib_result,
            };

            let tableau = TableauOptions {
                max_depth: args.max_depth,
                graph_output: args.graph_output,
                memoization: args.memoization,
                simple_first: args.simple_first,
                formula_optimizations: args.formula_optimizations,
                jump_rule_enabled: args.jump_rule_enabled,
                formula_simplifications: args.formula_simplifications,
                unsat_core_extraction: args.unsat_core_extraction,
                trace_extraction: args.trace_extraction,
            };
            (mode, general, tableau, args.formula_file)
        }
    }
}
