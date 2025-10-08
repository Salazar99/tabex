use std::fmt::{self, Display};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

use num_rational::Ratio;

type VariableName = Arc<str>;

pub static FORMULA_ID: AtomicUsize = AtomicUsize::new(0);

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum ArithOp {
    Add,
    Sub
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum RelOp {
    Lt,
    Le,
    Gt,
    Ge,
    Eq,
    Ne,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum AExpr {
    Var(VariableName),
    Num(Ratio<i64>),
    Abs(Box<AExpr>),
    BinOp {
        op: ArithOp,
        left: Box<AExpr>,
        right: Box<AExpr>,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum Expr {
    Atom(VariableName),
    Rel {
        op: RelOp,
        left: AExpr,
        right: AExpr,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Interval {
    pub lower: i32,
    pub upper: i32,
}

impl Interval {
    pub fn contains(&self, other: &Interval) -> bool {
        self.lower <= other.lower && self.upper >= other.upper
    }

    pub fn intersects(&self, other: &Interval) -> bool {
        self.upper >= other.lower && other.upper >= self.lower
    }

    pub fn active(&self, current_time: i32) -> bool {
        current_time >= self.lower && current_time <= self.upper
    }

    pub fn contiguous(&self, other: &Interval) -> bool {
        self.upper + 1 == other.lower || other.upper + 1 == self.lower
    }

    pub fn union(&self, other: &Interval) -> Interval {
        Interval { lower: self.lower.min(other.lower), upper: self.upper.max(other.upper) }
    }

    pub fn intersection(&self, other: &Interval) -> Interval {
        Interval { lower: self.lower.max(other.lower), upper: self.upper.min(other.upper) }
    }

    pub fn shift_left(&self, time: i32) -> Option<Interval> {
        if time > self.upper {
            return None
        }

        Some(Interval {
            lower: (self.lower - time).max(0),
            upper: self.upper - time,
        })
    }

    pub fn shift_right(&self, time: i32) -> Interval {
        Interval {
            lower: self.lower + time,
            upper: self.upper + time,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum FormulaKind {
    // Propositions
    Prop(Expr),
    True,
    False,
    
    // Boolean/structural
    And(Vec<Formula>),
    Or(Vec<Formula>),
    Imply(Box<Formula>, Box<Formula>),
    Not(Box<Formula>),
    
    // Temporal
    G { interval: Interval, parent_upper: Option<i32>, phi: Box<Formula> },
    F { interval: Interval, parent_upper: Option<i32>, phi: Box<Formula> },
    U { interval: Interval, parent_upper: Option<i32>, left: Box<Formula>, right: Box<Formula> },
    R { interval: Interval, parent_upper: Option<i32>, left: Box<Formula>, right: Box<Formula> },
    O(Box<Formula>),
}

#[derive(Clone, Debug, Hash)]
pub struct Formula {
    pub id: usize,
    pub kind: FormulaKind
}

impl PartialEq for Formula {
    fn eq(&self, other: &Self) -> bool {
        self.kind == other.kind
    }
}

impl Eq for Formula {}

impl PartialOrd for Formula {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        self.kind.partial_cmp(&other.kind)
    }
}

impl Ord for Formula {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.kind.cmp(&other.kind)
    }
}

impl Formula {
    pub fn new(kind: FormulaKind) -> Self {
        Self { id: FORMULA_ID.fetch_add(1, Ordering::Relaxed), kind: kind }
    }

    pub fn prop(expr: Expr) -> Self {
        Self::new(FormulaKind::Prop(expr))
    }

    pub fn true_() -> Self {
        Self::new(FormulaKind::True)
    }

    pub fn false_() -> Self {
        Self::new(FormulaKind::False)
    }

    pub fn and(operands: Vec<Formula>) -> Self {
        Self::new(FormulaKind::And(operands))
    }

    pub fn or(operands: Vec<Formula>) -> Self {
        Self::new(FormulaKind::Or(operands))
    }

    pub fn imply(left: Formula, right: Formula) -> Self {
        Self::new(FormulaKind::Imply(Box::new(left), Box::new(right)))
    }

    pub fn not(inner: Formula) -> Self {
        Self::new(FormulaKind::Not(Box::new(inner)))
    }

    pub fn g(interval: Interval, parent_upper: Option<i32>, phi: Formula) -> Self {
        Self::new(FormulaKind::G {
            interval,
            parent_upper: parent_upper,
            phi: Box::new(phi),
        })
    }

    pub fn f(interval: Interval, parent_upper: Option<i32>, phi: Formula) -> Self {
        Self::new(FormulaKind::F {
            interval,
            parent_upper: parent_upper,
            phi: Box::new(phi),
        })
    }

    pub fn u(interval: Interval, parent_upper: Option<i32>, left: Formula, right: Formula) -> Self {
        Self::new(FormulaKind::U {
            interval,
            parent_upper: parent_upper,
            left: Box::new(left),
            right: Box::new(right),
        })
    }

    pub fn r(interval: Interval, parent_upper: Option<i32>, left: Formula, right: Formula) -> Self {
        Self::new(FormulaKind::R {
            interval,
            parent_upper: parent_upper,
            left: Box::new(left),
            right: Box::new(right),
        })
    }

    pub fn o(inner: Formula) -> Self {
        Self::new(FormulaKind::O(Box::new(inner)))
    }

    pub fn lower_bound(&self) -> Option<i32> {
        match &self.kind {
            FormulaKind::G { interval, .. } 
            | FormulaKind::F { interval, .. } 
            | FormulaKind::U { interval, .. }
            | FormulaKind::R { interval, .. } => Some(interval.lower),
            _ => None,
        }
    }

    pub fn upper_bound(&self) -> Option<i32> {
        match &self.kind {
            FormulaKind::G { interval, .. } 
            | FormulaKind::F { interval, .. } 
            | FormulaKind::U { interval, .. } 
            | FormulaKind::R { interval, .. } => Some(interval.upper),
            _ => None,
        }
    }

    pub fn has_temporal(&self) -> bool {
        match &self.kind {
            FormulaKind::G { .. } | FormulaKind::F { .. } | FormulaKind::U { .. } | FormulaKind::R { .. } => true,
            FormulaKind::And(v) | FormulaKind::Or(v) => v.iter().any(|f| f.has_temporal()),
            FormulaKind::Not(inner) => inner.has_temporal(),
            FormulaKind::Imply(left, right) => left.has_temporal() || right.has_temporal(),
            _ => false,
        }
    }

    pub fn complex_temporal_operator(&self) -> bool {
        match &self.kind {
            FormulaKind::G { phi, .. }
            | FormulaKind::U { left: phi, .. }
            | FormulaKind::R { right: phi, .. } => phi.has_temporal(),
            _ => false,
        }
    }

    pub fn get_max_upper(&self) -> Option<i32> {
        match &self.kind {
            FormulaKind::O(inner) 
            | FormulaKind::Not(inner) => inner.get_max_upper(),
            FormulaKind::And(operands) 
            | FormulaKind::Or(operands) => {
                operands.iter().map(|op| op.get_max_upper()).max().unwrap_or(None)
            },
            FormulaKind::Imply(left, right) => left.get_max_upper().max(right.get_max_upper()),
            FormulaKind::G { interval, .. } 
            | FormulaKind::F { interval, .. } 
            | FormulaKind::U { interval, .. }
            | FormulaKind::R { interval, .. } => Some(interval.upper),
            _ => None,
        }

    }

    pub fn active(&self, current_time: i32) -> bool {
        match &self.kind {
            FormulaKind::G { interval, .. } 
            | FormulaKind::F { interval, .. } 
            | FormulaKind::U { interval, .. }
            | FormulaKind::R { interval, .. } => interval.active(current_time),
            _ => false,
        }
    }

    pub fn parent_active(&self, current_time: i32) -> bool {
        match self.kind {
            FormulaKind::G { parent_upper: Some(upper), .. }
            | FormulaKind::F { parent_upper: Some(upper), .. }
            | FormulaKind::U { parent_upper: Some(upper), .. }
            | FormulaKind::R { parent_upper: Some(upper), .. } => current_time < upper,
            _ => false,
        }
    }

    pub fn with_interval(&self, interval: Interval) -> Self {
        let mut to_return = self.clone();
        match &mut to_return.kind {
            FormulaKind::G { interval: int, .. } 
            | FormulaKind::F { interval: int, .. }
            | FormulaKind::U { interval: int, .. }
            | FormulaKind::R { interval: int, .. } => *int = interval,
            _ => panic!("Cannot set interval on non-temporal formula"),
        }
        to_return
    }
}

pub fn join_with(v: &[Formula], sep: &str) -> String {
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

impl Display for FormulaKind {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            FormulaKind::And(v) => write!(f, "{}", join_with(v, " && ")),
            FormulaKind::Or(v) => write!(f, "{}", join_with(v, " || ")),
            FormulaKind::Not(inner) => write!(f, "!{}", inner),
            FormulaKind::Imply(left, right) => write!(f, "({}) -> ({})", left, right),
            FormulaKind::G { interval, phi, .. } => write!(f, "G[{},{}] ({})", interval.lower, interval.upper, phi),
            FormulaKind::F { interval, phi, .. } => write!(f, "F[{},{}] ({})", interval.lower, interval.upper, phi),
            FormulaKind::U { interval, left, right, .. } => {
                write!(f, "({}) U[{},{}] ({})", left, interval.lower, interval.upper, right)
            }
            FormulaKind::R { interval, left, right, .. } => {
                write!(f, "({}) R[{},{}] ({})", left, interval.lower, interval.upper, right)
            }
            FormulaKind::O(inner) => write!(f, "O ({})", inner),
            FormulaKind::Prop(p) => write!(f, "{}", p),
            FormulaKind::True => write!(f, "true"),
            FormulaKind::False => write!(f, "false"),
        }
    }
}

impl Display for Formula {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.kind)
    }
}