use std::sync::Arc;

use clap::Parser;
use num_rational::Ratio;
use rand::{Rng, seq::IndexedRandom};
use stlcc::formula::{AExpr, Expr, ExprKind, Formula, Interval, RelOp, VariableName};

#[derive(Parser, Debug)]
pub struct GeneratorArgs {
    /// Output folder for generated .stl files
    #[arg(short = 'o', long)]
    pub output_folder: String,

    /// Number of formulas to generate
    #[arg(short = 'n', long, default_value_t = 5)]
    pub num_formulas: usize,

    /// Number of boolean variables (atoms a0, a1, …)
    #[arg(short = 'b', long, default_value_t = 0)]
    pub num_bool_vars: usize,

    /// Number of real-valued variables (x0, x1, …)
    #[arg(short = 'r', long, default_value_t = 3)]
    pub num_real_vars: usize,

    /// Maximum number of real constraints per formula
    #[arg(short = 'c', long, default_value_t = 5)]
    pub max_real_constraints: usize,

    /// Maximum temporal horizon (upper bound of intervals)
    #[arg(short = 'l', long, default_value_t = 100)]
    pub max_horizon: i32,

    /// Base probability of stopping recursion (approx inverse of expected depth)
    #[arg(long, default_value_t = 0.1)]
    pub p_stop_base: f64,

    /// Probability that a chosen operator is temporal (G,F,U,R)
    #[arg(long, default_value_t = 0.3)]
    pub p_temporal: f64,

    /// Probability that a chosen operator is unary (¬, F, G)
    #[arg(long, default_value_t = 0.2)]
    pub p_unary: f64,

    /// Maximum recursion depth hard cap
    #[arg(long, default_value_t = 20)]
    pub max_depth: usize,
}

pub struct RandomGenerator {
    bool_vars: Vec<VariableName>,
    real_constraints: Vec<ExprKind>,
    max_horizon: i32,
    p_stop_base: f64,
    p_temporal: f64,
    p_unary: f64,
    max_depth: usize,
}

impl RandomGenerator {
    pub fn new(args: &GeneratorArgs) -> Self {
        pub fn random_rel(real_vars: &Vec<VariableName>) -> ExprKind {
            let mut rng = rand::rng();

            let op = [
                RelOp::Lt,
                RelOp::Le,
                RelOp::Gt,
                RelOp::Ge,
                RelOp::Eq,
                RelOp::Ne,
            ]
            .choose(&mut rng)
            .unwrap()
            .clone();
            let left = AExpr::Var(real_vars.choose(&mut rng).unwrap().clone());
            let right = AExpr::Num(Ratio::new(
                rng.random_range(-10..10),
                rng.random_range(1..10),
            ));
            ExprKind::Rel { op, left, right }
        }

        let bool_vars: Vec<VariableName> = (0..args.num_bool_vars)
            .map(|i| Arc::from(format!("a{}", i)))
            .collect();
        let real_vars: Vec<VariableName> = (0..args.num_real_vars)
            .map(|i| Arc::from(format!("x{}", i)))
            .collect();

        if bool_vars.is_empty() && real_vars.is_empty() {
            panic!("At least one boolean or real variable must be defined.");
        }

        let real_constraints = (0..args.max_real_constraints)
            .map(|_| random_rel(&real_vars))
            .collect();
        Self {
            bool_vars,
            real_constraints: real_constraints,
            max_horizon: args.max_horizon,

            p_stop_base: args.p_stop_base,
            p_temporal: args.p_temporal,
            p_unary: args.p_unary,
            max_depth: args.max_depth,
        }
    }

    fn random_interval(&self, horizon: i32) -> Interval {
        let mut rng = rand::rng();
        let a = rng.random_range(0..=self.max_horizon - horizon);
        let b = rng.random_range(a..=self.max_horizon - horizon);
        Interval { lower: a, upper: b }
    }

    fn random_proposition(&self) -> Formula {
        let mut rng = rand::rng();

        // if both available → 50/50 split, otherwise whichever exists
        if !self.bool_vars.is_empty() && (self.real_constraints.is_empty() || rng.random_bool(0.5))
        {
            let v = self.bool_vars.choose(&mut rng).unwrap().clone();
            Formula::Prop(Expr::bool(v))
        } else {
            let ExprKind::Rel { op, left, right } =
                self.real_constraints.choose(&mut rng).unwrap().clone()
            else {
                unreachable!()
            };
            Formula::Prop(Expr::real(op, left, right))
        }
    }

    pub fn generate_formula(&self, depth: usize, horizon: i32) -> Formula {
        let mut rng = rand::rng();

        // stop condition
        if depth >= self.max_depth || horizon >= self.max_horizon || rng.random::<f64>() < self.p_stop_base * (depth as f64)
        {
            return self.random_proposition();
        }

        let p = rng.random::<f64>();

        if p < self.p_unary {
            // unary operator
            if rng.random::<f64>() < self.p_temporal {
                let interval = self.random_interval(horizon);
                let phi = self.generate_formula(depth + 1, horizon + interval.upper);
                if rng.random_bool(0.5) {
                    Formula::g(interval, None, phi)
                } else {
                    Formula::f(interval, None, phi)
                }
            } else {
                let phi = self.generate_formula(depth + 1, horizon);
                Formula::Not(Box::new(phi))
            }
        } else {
            // binary operator
            
            if rng.random::<f64>() < self.p_temporal {
                let interval = self.random_interval(horizon);
                let left = self.generate_formula(depth + 1, horizon + interval.upper);
                let right = self.generate_formula(depth + 1, horizon + interval.upper);
                if rng.random_bool(0.5) {
                    Formula::u(interval, None, left, right)
                } else {
                    Formula::r(interval, None, left, right)
                }
            } else if rng.random_bool(0.5) {
                let left = self.generate_formula(depth + 1, horizon);
                let right = self.generate_formula(depth + 1, horizon);
                Formula::And(vec![left, right])
            } else {
                let left = self.generate_formula(depth + 1, horizon);
                let right = self.generate_formula(depth + 1, horizon);
                Formula::Or(vec![left, right])
            }
        }
    }
}

fn main() {
    let args = GeneratorArgs::parse();
    let rng = RandomGenerator::new(&args);

    // Create output folder if it doesn't exist
    std::fs::create_dir_all(&args.output_folder).expect("Failed to create output folder");

    println!("Args: {args:#?}");
    println!("Generating {} formulas to folder: {}", args.num_formulas, args.output_folder);

    for i in 0..args.num_formulas {
        let formula = rng.generate_formula(0, 0);
        let filename = format!("{}/formula_{:03}.stl", args.output_folder, i + 1);
        std::fs::write(&filename, format!("{}", formula)).expect("Failed to write formula to file");
        println!("Generated: {}", filename);
    }

    println!("Done!");
}
