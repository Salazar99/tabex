use clap::Parser;

pub struct TableauOptions {
    pub max_depth: usize,
    pub graph_output: bool,
    pub memoization: bool,
    pub simple_first: bool,
    pub formula_optimizations: bool,
    pub jump_rule_enabled: bool,
    pub formula_simplifications: bool,
    pub mltl: bool,
    pub smtlib_result: bool,
    pub unsat_core_extraction: bool,
}

impl Default for TableauOptions {
    fn default() -> Self {
        TableauOptions {
            max_depth: 1000000,
            graph_output: false,
            memoization: true,
            simple_first: true,
            formula_optimizations: true,
            jump_rule_enabled: true,
            formula_simplifications: true,
            mltl: false,
            smtlib_result: false,
            unsat_core_extraction: false,
        }
    }
}

#[derive(Parser)]
#[command(name = "stlcc")]
#[command(about = "STLCC - Signal Temporal Logic Consistency Checker")]
pub struct CliArgs {
    /// Input formula file
    pub formula_file: String,

    /// Maximum depth for tableau construction
    #[arg(long, default_value_t = TableauOptions::default().max_depth)]
    pub max_depth: usize,

    /// Enable graph output
    #[arg(long, default_value_t = TableauOptions::default().graph_output)]
    pub graph_output: bool,

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
    #[arg(long, default_value_t = TableauOptions::default().mltl)]
    pub mltl: bool,

    /// Print result in smtlib format
    #[arg(long, default_value_t = TableauOptions::default().smtlib_result)]
    pub smtlib_result: bool,

    /// Enable unsat core extraction
    #[arg(long, default_value_t = TableauOptions::default().unsat_core_extraction)]
    pub unsat_core_extraction: bool,
}

pub enum ConfigSource {
    Cli,
}

pub fn get_tableau_options(source: ConfigSource) -> (TableauOptions, String) {
    match source {
        ConfigSource::Cli => {
            let args = CliArgs::parse();
            let options = TableauOptions {
                max_depth: args.max_depth,
                graph_output: args.graph_output,
                memoization: args.memoization,
                simple_first: args.simple_first,
                formula_optimizations: args.formula_optimizations,
                jump_rule_enabled: args.jump_rule_enabled,
                mltl: args.mltl,
                smtlib_result: args.smtlib_result,
                unsat_core_extraction: args.unsat_core_extraction,
                formula_simplifications: args.formula_simplifications,
            };
            (options, args.formula_file)
        }
    }
}
