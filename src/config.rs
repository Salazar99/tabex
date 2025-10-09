use clap::Parser;
use crate::tableau::TableauOptions;

#[derive(Parser)]
#[command(name = "stlcc")]
#[command(about = "STLCC - Signal Temporal Logic Consistency Checker")]
pub struct CliArgs {
    /// Input formula file
    pub formula_file: String,

    /// Maximum depth for tableau construction
    #[arg(long, default_value_t = 10000000)]
    pub max_depth: usize,

    /// Enable graph output
    #[arg(long, default_value_t = false)]
    pub graph_output: bool,

    /// Enable memoization
    #[arg(long, default_value_t = true)]
    pub memoization: bool,

    /// Process simple formulas first
    #[arg(long, default_value_t = true)]
    pub simple_first: bool,

    /// Enable formula syntactic optimizations
    #[arg(long, default_value_t = true)]
    pub formula_optimizations: bool,

    /// Enable jump rule
    #[arg(long, default_value_t = true)]
    pub jump_rule_enabled: bool,

    /// Use MLTL semantics
    #[arg(long, default_value_t = false)]
    pub mltl: bool,
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
            };
            (options, args.formula_file)
        }
    }
}