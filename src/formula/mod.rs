use std::fmt::{self, Display};
use std::hash::{Hash, Hasher};
use std::cmp::Ordering as CmpOrdering;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

use num_rational::Ratio;

use crate::formula::transform::{RecursiveFormulaTransformer, NegationNormalFormTransformer};

pub mod parser;
pub mod transform;

pub type VariableName = Arc<str>;

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

#[derive(Clone, Debug)]
pub enum Formula {
    // Propositions
    Prop(usize, Expr),
    True(usize),
    False(usize),
    
    // Boolean/structural
    And(Vec<Formula>),
    Or(Vec<Formula>),
    Imply {left: Box<Formula>, right: Box<Formula>, not_left: Box<Formula> },
    Not(Box<Formula>),
    
    // Temporal
    G { interval: Interval, parent_upper: Option<i32>, phi: Box<Formula> },
    F { interval: Interval, parent_upper: Option<i32>, phi: Box<Formula> },
    U { interval: Interval, parent_upper: Option<i32>, left: Box<Formula>, right: Box<Formula> },
    R { interval: Interval, parent_upper: Option<i32>, left: Box<Formula>, right: Box<Formula> },
    O(Box<Formula>),
}

impl PartialEq for Formula {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (Formula::Prop(_, a), Formula::Prop(_, b)) => a == b,
            (Formula::True(_), Formula::True(_)) => true,
            (Formula::False(_), Formula::False(_)) => true,
            (Formula::And(a), Formula::And(b)) => a == b,
            (Formula::Or(a), Formula::Or(b)) => a == b,
            (Formula::Imply { left: la, right: ra, not_left: nla }, Formula::Imply { left: lb, right: rb, not_left: nlb }) => la == lb && ra == rb && nla == nlb,
            (Formula::Not(a), Formula::Not(b)) => a == b,
            (Formula::G { interval: ia, parent_upper: pa, phi: phia }, Formula::G { interval: ib, parent_upper: pb, phi: phib }) => ia == ib && pa == pb && phia == phib,
            (Formula::F { interval: ia, parent_upper: pa, phi: phia }, Formula::F { interval: ib, parent_upper: pb, phi: phib }) => ia == ib && pa == pb && phia == phib,
            (Formula::U { interval: ia, parent_upper: pa, left: la, right: ra }, Formula::U { interval: ib, parent_upper: pb, left: lb, right: rb }) => ia == ib && pa == pb && la == lb && ra == rb,
            (Formula::R { interval: ia, parent_upper: pa, left: la, right: ra }, Formula::R { interval: ib, parent_upper: pb, left: lb, right: rb }) => ia == ib && pa == pb && la == lb && ra == rb,
            (Formula::O(a), Formula::O(b)) => a == b,
            _ => false,
        }
    }
}

impl Eq for Formula {}

impl Hash for Formula {
    fn hash<H: Hasher>(&self, state: &mut H) {
        match self {
            Formula::Prop(_, expr) => {
                0u8.hash(state);
                expr.hash(state);
            }
            Formula::True(_) => 1u8.hash(state),
            Formula::False(_) => 2u8.hash(state),
            Formula::And(v) => {
                3u8.hash(state);
                v.hash(state);
            }
            Formula::Or(v) => {
                4u8.hash(state);
                v.hash(state);
            }
            Formula::Imply { left, right, not_left } => {
                5u8.hash(state);
                left.hash(state);
                right.hash(state);
                not_left.hash(state);
            }
            Formula::Not(inner) => {
                6u8.hash(state);
                inner.hash(state);
            }
            Formula::G { interval, parent_upper, phi } => {
                7u8.hash(state);
                interval.hash(state);
                parent_upper.hash(state);
                phi.hash(state);
            }
            Formula::F { interval, parent_upper, phi } => {
                8u8.hash(state);
                interval.hash(state);
                parent_upper.hash(state);
                phi.hash(state);
            }
            Formula::U { interval, parent_upper, left, right } => {
                9u8.hash(state);
                interval.hash(state);
                parent_upper.hash(state);
                left.hash(state);
                right.hash(state);
            }
            Formula::R { interval, parent_upper, left, right } => {
                10u8.hash(state);
                interval.hash(state);
                parent_upper.hash(state);
                left.hash(state);
                right.hash(state);
            }
            Formula::O(inner) => {
                11u8.hash(state);
                inner.hash(state);
            }
        }
    }
}

fn discriminant_value(f: &Formula) -> u8 {
    match f {
        Formula::Prop(..) => 0,
        Formula::True(..) => 1,
        Formula::False(..) => 2,
        Formula::And(..) => 3,
        Formula::Or(..) => 4,
        Formula::Imply {..} => 5,
        Formula::Not(..) => 6,
        Formula::G {..} => 7,
        Formula::F {..} => 8,
        Formula::U {..} => 9,
        Formula::R {..} => 10,
        Formula::O(..) => 11,
    }
}

impl PartialOrd for Formula {
    fn partial_cmp(&self, other: &Self) -> Option<CmpOrdering> {
        match (self, other) {
            (Formula::Prop(_, a), Formula::Prop(_, b)) => a.partial_cmp(b),
            (Formula::True(_), Formula::True(_)) => Some(CmpOrdering::Equal),
            (Formula::False(_), Formula::False(_)) => Some(CmpOrdering::Equal),
            (Formula::Prop(_, _), _) => Some(CmpOrdering::Less),
            (_, Formula::Prop(_, _)) => Some(CmpOrdering::Greater),
            (Formula::True(_), _) => Some(CmpOrdering::Less),
            (_, Formula::True(_)) => Some(CmpOrdering::Greater),
            (Formula::False(_), _) => Some(CmpOrdering::Less),
            (_, Formula::False(_)) => Some(CmpOrdering::Greater),
            (Formula::And(a), Formula::And(b)) => a.partial_cmp(b),
            (Formula::Or(a), Formula::Or(b)) => a.partial_cmp(b),
            (Formula::Imply { left: la, right: ra, not_left: nla }, Formula::Imply { left: lb, right: rb, not_left: nlb }) => {
                match la.partial_cmp(lb) {
                    Some(CmpOrdering::Equal) => match ra.partial_cmp(rb) {
                        Some(CmpOrdering::Equal) => nla.partial_cmp(nlb),
                        other => other,
                    },
                    other => other,
                }
            }
            (Formula::Not(a), Formula::Not(b)) => a.partial_cmp(b),
            (Formula::G { interval: ia, parent_upper: pa, phi: phia }, Formula::G { interval: ib, parent_upper: pb, phi: phib }) => {
                match ia.partial_cmp(ib) {
                    Some(CmpOrdering::Equal) => match pa.partial_cmp(pb) {
                        Some(CmpOrdering::Equal) => phia.partial_cmp(phib),
                        other => other,
                    },
                    other => other,
                }
            }
            (Formula::F { interval: ia, parent_upper: pa, phi: phia }, Formula::F { interval: ib, parent_upper: pb, phi: phib }) => {
                match ia.partial_cmp(ib) {
                    Some(CmpOrdering::Equal) => match pa.partial_cmp(pb) {
                        Some(CmpOrdering::Equal) => phia.partial_cmp(phib),
                        other => other,
                    },
                    other => other,
                }
            }
            (Formula::U { interval: ia, parent_upper: pa, left: la, right: ra }, Formula::U { interval: ib, parent_upper: pb, left: lb, right: rb }) => {
                match ia.partial_cmp(ib) {
                    Some(CmpOrdering::Equal) => match pa.partial_cmp(pb) {
                        Some(CmpOrdering::Equal) => match la.partial_cmp(lb) {
                            Some(CmpOrdering::Equal) => ra.partial_cmp(rb),
                            other => other,
                        },
                        other => other,
                    },
                    other => other,
                }
            }
            (Formula::R { interval: ia, parent_upper: pa, left: la, right: ra }, Formula::R { interval: ib, parent_upper: pb, left: lb, right: rb }) => {
                match ia.partial_cmp(ib) {
                    Some(CmpOrdering::Equal) => match pa.partial_cmp(pb) {
                        Some(CmpOrdering::Equal) => match la.partial_cmp(lb) {
                            Some(CmpOrdering::Equal) => ra.partial_cmp(rb),
                            other => other,
                        },
                        other => other,
                    },
                    other => other,
                }
            }
            (Formula::O(a), Formula::O(b)) => a.partial_cmp(b),
            (a, b) => {
                let da = discriminant_value(a);
                let db = discriminant_value(b);
                da.partial_cmp(&db)
            }
        }
    }
}

impl Ord for Formula {
    fn cmp(&self, other: &Self) -> CmpOrdering {
        self.partial_cmp(other).unwrap()
    }
}

pub static FORMULA_ID: AtomicUsize = AtomicUsize::new(0);

impl Formula {
    pub fn prop(expr: Expr) -> Self {
        Formula::Prop(FORMULA_ID.fetch_add(1, Ordering::Relaxed), expr)
    }

    pub fn true_() -> Self {
        Formula::True(FORMULA_ID.fetch_add(1, Ordering::Relaxed))
    }

    pub fn false_() -> Self {
        Formula::False(FORMULA_ID.fetch_add(1, Ordering::Relaxed))
    }

    pub fn and(operands: Vec<Formula>) -> Self {
        Formula::And(operands)
    }

    pub fn or(operands: Vec<Formula>) -> Self {
        Formula::Or(operands)
    }

    pub fn imply(left: Formula, right: Formula) -> Self {
        Formula::Imply {
            left: Box::new(left.clone()),
            right: Box::new(right),
            not_left: Box::new(NegationNormalFormTransformer.visit(&Formula::not(left)))
        }
    }

    pub fn not(inner: Formula) -> Self {
        Formula::Not(Box::new(inner))
    }

    pub fn g(interval: Interval, parent_upper: Option<i32>, phi: Formula) -> Self {
        Formula::G {
            interval,
            parent_upper: parent_upper,
            phi: Box::new(phi),
        }
    }

    pub fn f(interval: Interval, parent_upper: Option<i32>, phi: Formula) -> Self {
        Formula::F {
            interval,
            parent_upper: parent_upper,
            phi: Box::new(phi),
        }
    }

    pub fn u(interval: Interval, parent_upper: Option<i32>, left: Formula, right: Formula) -> Self {
        Formula::U {
            interval,
            parent_upper: parent_upper,
            left: Box::new(left),
            right: Box::new(right),
        }
    }

    pub fn r(interval: Interval, parent_upper: Option<i32>, left: Formula, right: Formula) -> Self {
        Formula::R {
            interval,
            parent_upper: parent_upper,
            left: Box::new(left),
            right: Box::new(right),
        }
    }

    pub fn o(inner: Formula) -> Self {
        Formula::O(Box::new(inner))
    }

    pub fn with_operand(&self, operand: Formula) -> Self {
        let mut to_return = self.clone();
        match &mut to_return {
            Formula::Not(inner) | Formula::O(inner) => *inner = Box::new(operand),
            Formula::G { phi, .. } | Formula::F { phi, .. } => *phi = Box::new(operand),
            _ => panic!("Cannot set operand on formula without a single inner operand"),
        }
        to_return
    }

    pub fn with_operand_couple(&self, left: Formula, right: Formula) -> Self {
        let mut to_return = self.clone();
        match &mut to_return {
            Formula::U { left: l, right: r, .. } | Formula::R { left: l, right: r, .. } => {
                *l = Box::new(left);
                *r = Box::new(right);
            }
            _ => panic!("Cannot set operands on formula without two inner operands"),
        }
        to_return
    }
    
    pub fn with_interval(&self, interval: Interval) -> Self {
        let mut to_return = self.clone();
        match &mut to_return {
            Formula::G { interval: int, .. } 
            | Formula::F { interval: int, .. }
            | Formula::U { interval: int, .. }
            | Formula::R { interval: int, .. } => *int = interval,
            _ => panic!("Cannot set interval on non-temporal formula"),
        }
        to_return
    }

    pub fn with_parent_upper(&self, parent_upper: Option<i32>) -> Self {
        let mut to_return = self.clone();
        match &mut to_return {
            Formula::G { parent_upper: pu, .. } 
            | Formula::F { parent_upper: pu, .. }
            | Formula::U { parent_upper: pu, .. }
            | Formula::R { parent_upper: pu, .. } => *pu = parent_upper,
            _ => panic!("Cannot set parent_upper on non-temporal formula"),
        }
        to_return
    }

    pub fn with_operands(&self, operands: Vec<Formula>) -> Self {
        let mut to_return = self.clone();
        match &mut to_return {
            Formula::And(ops) | Formula::Or(ops) => *ops = operands,
            _ => panic!("Cannot set operands on formulas different from And/Or"),
        }
        to_return
    }

    pub fn with_implication(&self, left: Formula, right: Formula, not_left: Formula) -> Self {
        let mut to_return = self.clone();
        match &mut to_return {
            Formula::Imply { left: l, right: r, not_left: nl } => {
                *l = Box::new(left);
                *r = Box::new(right);
                *nl = Box::new(not_left);
            }
            _ => panic!("Cannot set implications on formulas different from Imply"),
        }
        to_return
    }

    pub fn get_interval(&self) -> Option<Interval> {
        match &self {
            Formula::G { interval, .. } 
            | Formula::F { interval, .. } 
            | Formula::U { interval, .. }
            | Formula::R { interval, .. } => Some(interval.clone()),
            _ => None,
        }
    }

    pub fn lower_bound(&self) -> Option<i32> {
        self.get_interval().map(|i| i.lower)
    }

    pub fn upper_bound(&self) -> Option<i32> {
        self.get_interval().map(|i| i.upper)
    }

    pub fn has_temporal(&self) -> bool {
        match &self {
            Formula::G { .. } | Formula::F { .. } | Formula::U { .. } | Formula::R { .. } => true,
            Formula::And(v) | Formula::Or(v) => v.iter().any(|f| f.has_temporal()),
            Formula::Not(inner) => inner.has_temporal(),
            Formula::Imply { left, right, .. } => left.has_temporal() || right.has_temporal(),
            _ => false,
        }
    }

    pub fn is_complex_temporal_operator(&self) -> bool {
        match &self {
            Formula::G { phi, .. }
            | Formula::U { left: phi, .. }
            | Formula::R { right: phi, .. } => phi.has_temporal(),
            _ => false,
        }
    }

    pub fn is_active_at(&self, current_time: i32) -> bool {
        match &self {
            Formula::G { interval, .. } 
            | Formula::F { interval, .. } 
            | Formula::U { interval, .. }
            | Formula::R { interval, .. } => interval.active(current_time),
            _ => false,
        }
    }

    pub fn is_parent_active_at(&self, current_time: i32) -> bool {
        match self {
            Formula::G { parent_upper: Some(upper), .. }
            | Formula::F { parent_upper: Some(upper), .. }
            | Formula::U { parent_upper: Some(upper), .. }
            | Formula::R { parent_upper: Some(upper), .. } => current_time < *upper,
            _ => false,
        }
    }

    pub fn is_negation_normal_form(&self) -> bool {
        match &self {
            Formula::Not(inner) => matches!(**inner, Formula::Prop(_, _) | Formula::True(_) | Formula::False(_)),
            Formula::And(ops) | Formula::Or(ops) => ops.iter().all(|f| f.is_negation_normal_form()),
            Formula::Imply { left, right, not_left } => left.is_negation_normal_form() && right.is_negation_normal_form() && not_left.is_negation_normal_form(),
            Formula::G { phi, .. } | Formula::F { phi, .. } => phi.is_negation_normal_form(),
            Formula::U { left, right, .. } | Formula::R { left, right, .. } => left.is_negation_normal_form() && right.is_negation_normal_form(),
            _ => true,
        }
    }

    pub fn is_flat(&self) -> bool {
        match &self {
            Formula::And(ops) => !ops.iter().any(|f| matches!(f, Formula::And(_))),
            Formula::Or(ops) => !ops.iter().any(|f| matches!(f, Formula::Or(_))),
            Formula::Imply { left, right, not_left } => left.is_flat() && right.is_flat() && not_left.is_flat(),
            Formula::G { phi, .. } | Formula::F { phi, .. } => phi.is_flat(),
            Formula::U { left, right, .. } | Formula::R { left, right, .. } => left.is_flat() && right.is_flat(),
            _ => true,
        }
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

impl Display for Interval {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "[{},{}]", self.lower, self.upper)
    }
}

impl Display for Formula {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Formula::And(v) => write!(f, "{}", join_with(v, " && ")),
            Formula::Or(v) => write!(f, "{}", join_with(v, " || ")),
            Formula::Not(inner) => write!(f, "!{}", inner),
            Formula::Imply { left, right, .. } => write!(f, "({}) -> ({})", left, right),
            Formula::G { interval, phi, .. } => write!(f, "G{} ({})", interval, phi),
            Formula::F { interval, phi, .. } => write!(f, "F{} ({})", interval, phi),
            Formula::U { interval, left, right, .. } => {
                write!(f, "({}) U{} ({})", left, interval, right)
            }
            Formula::R { interval, left, right, .. } => {
                write!(f, "({}) R{} ({})", left, interval, right)
            }
            Formula::O(inner) => write!(f, "O ({})", inner),
            Formula::Prop(id, p) => write!(f, "{}_{}", p, id),
            Formula::True(id) => write!(f, "true_{}", id),
            Formula::False(id) => write!(f, "false_{}", id),
        }
    }
}