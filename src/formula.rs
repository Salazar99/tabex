#![allow(unused)]
use std::fmt::{self, Display};

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum ArithOp {
    Add,
    Sub
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum RelOp {
    Lt,
    Le,
    Gt,
    Ge,
    Eq,
    Ne,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum AExpr {
    Var(String),
    Num(i64),
    Abs(Box<AExpr>),
    BinOp {
        op: ArithOp,
        left: Box<AExpr>,
        right: Box<AExpr>,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Expr {
    Atom(String),
    Rel {
        op: RelOp,
        left: AExpr,
        right: AExpr,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Formula {
    // Boolean/structural
    And(Vec<Formula>),
    Or(Vec<Formula>),
    Not(Box<Formula>),
    
    // Temporal
    G { lower: i64, upper: i64, phi: Box<Formula> },
    F { lower: i64, upper: i64, phi: Box<Formula> },
    U { lower: i64, upper: i64, left: Box<Formula>, right: Box<Formula> },
    O(Box<Formula>),

    // Proposition
    Prop(Expr),
    True,
    False
}

fn join_with(v: &[Formula], sep: &str) -> String {
    v.iter().map(|n| n.to_string()).collect::<Vec<_>>().join(sep)
}

impl Display for AExpr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AExpr::Var(s) => write!(f, "{}", s),
            AExpr::Num(n) => write!(f, "{}", n),
            AExpr::Abs(inner) => write!(f, "|{}|", inner),
            AExpr::BinOp { op, left, right } => {
                let sym = match op {
                    ArithOp::Add => "+",
                    ArithOp::Sub => "-",
                };
                write!(f, "({} {} {})", left, sym, right)
            }
        }
    }
}

impl Display for Expr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Expr::Atom(s) => write!(f, "{}", s),
            Expr::Rel { op, left, right } => {
                let sym = match op {
                    RelOp::Lt => "<",
                    RelOp::Le => "<=",
                    RelOp::Gt => ">",
                    RelOp::Ge => ">=",
                    RelOp::Eq => "==",
                    RelOp::Ne => "!=",
                };
                write!(f, "{} {} {}", left, sym, right)
            }
        }
    }
}

impl Display for Formula {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Formula::And(v) => write!(f, "({})", join_with(v, " && ")),
            Formula::Or(v) => write!(f, "({})", join_with(v, " || ")),
            Formula::Not(inner) => write!(f, "!({})", inner),
            Formula::G { lower, upper, phi } => write!(f, "G[{},{}] {}", lower, upper, phi),
            Formula::F { lower, upper, phi } => write!(f, "F[{},{}] {}", lower, upper, phi),
            Formula::U { lower, upper, left, right } => {
                        write!(f, "({}) U[{},{}] ({})", left, lower, upper, right)
                    }
            Formula::O(inner) => write!(f, "O {}", inner),
            Formula::Prop(p) => write!(f, "{}", p),
            Formula::True => write!(f, "true"),
            Formula::False => write!(f, "false"),
        }
    }
}

impl Formula {
    pub fn lower_bound(&self) -> Option<i64> {
        match self {
            Formula::G { lower, .. } | Formula::F { lower, .. } | Formula::U { lower, .. } => Some(*lower),
            _ => None,
        }
    }

    pub fn upper_bound(&self) -> Option<i64> {
        match self {
            Formula::G { upper, .. } | Formula::F { upper, .. } | Formula::U { upper, .. } => Some(*upper),
            _ => None,
        }
    }

    pub fn has_temporal(&self) -> bool {
        match self {
            Formula::G { .. } | Formula::F { .. } | Formula::U { .. } => true,
            Formula::And(v) | Formula::Or(v) => v.iter().any(|f| f.has_temporal()),
            Formula::Not(inner) => inner.has_temporal(),
            _ => false,
        }
    }

    pub fn jump_problematic(&self) -> bool {
        match self {
            Formula::O(inner) => {
                match &**inner {
                    Formula::G { lower, upper, phi } => phi.has_temporal(),
                    _ => false,
                }
            }
            Formula::And(v) | Formula::Or(v) => v.iter().any(|f| f.jump_problematic()),
            Formula::Not(inner) => inner.jump_problematic(),
            _ => false,
        }
    }

    pub fn get_max_upper(&self) -> i64 {
        match self {
            Formula::And(operands) | Formula::Or(operands) => {
                operands.iter().map(|op| op.get_max_upper()).max().unwrap_or(-1)
            }
            Formula::Not(inner) => inner.get_max_upper(),
            Formula::G { upper, .. } | Formula::F { upper, .. } | Formula::U { upper, .. } => *upper,
            Formula::O(inner) => inner.get_max_upper(),
            _ => -1, // Prop, True, False
        }
    }

}
