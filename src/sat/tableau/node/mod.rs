use crate::{
    formula::{
        Formula, Interval,
        transform::{
            FlatTransformer, FormulaSimplifier, NegationNormalFormTransformer,
            RecursiveFormulaTransformer, STLTransformer, ShiftBoundsTransformer,
        },
    },
    util::join_with,
};
use std::{
    collections::HashSet,
    fmt::{self, Display},
    sync::atomic::{AtomicUsize, Ordering},
};

pub mod decompose;
pub mod rewrite;

pub static NODE_FORMULA_ID: AtomicUsize = AtomicUsize::new(0);
pub static NODE_ID: AtomicUsize = AtomicUsize::new(0);

#[derive(Clone, Debug, Eq)]
pub struct NodeFormula {
    pub kind: Formula,
    pub marked: bool,
    pub parent_id: Option<usize>,
    pub id: usize,
}

impl From<Formula> for NodeFormula {
    fn from(kind: Formula) -> Self {
        Self {
            kind,
            marked: false,
            parent_id: None,
            id: NODE_FORMULA_ID.fetch_add(1, Ordering::Relaxed),
        }
    }
}

impl NodeFormula {
    pub fn with_kind(mut self, kind: Formula) -> Self {
        self.kind = kind;
        self
    }

    pub fn with_marked(mut self, marked: bool) -> Self {
        self.marked = marked;
        self
    }

    pub fn with_parent_id(mut self, parent_id: Option<usize>) -> Self {
        self.parent_id = parent_id;
        self
    }

    #[must_use]
    pub fn is_active_at(&self, current_time: i32) -> bool {
        match &self.kind.get_interval() {
            Some(interval) => interval.active(current_time),
            _ => true,
        }
    }

    #[must_use]
    pub fn is_parent_active_in(&self, node: &Node) -> bool {
        match self.parent_id {
            None => false,
            Some(id) => node.operands.iter().any(|f| f.id == id),
        }
    }
}

impl PartialEq for NodeFormula {
    fn eq(&self, other: &Self) -> bool {
        self.kind == other.kind && self.parent_id == other.parent_id && self.marked == other.marked
    }
}

#[derive(Debug, PartialEq, Eq)]
pub struct Node {
    pub operands: Vec<NodeFormula>,
    pub current_time: i32,
    pub implies: Option<Vec<usize>>,
    pub id: usize,
}

impl Node {
    pub fn from_operands(operands: Vec<NodeFormula>) -> Self {
        Self {
            operands,
            current_time: 0,
            implies: None,
            id: NODE_ID.fetch_add(1, Ordering::Relaxed),
        }
    }

    #[must_use]
    pub fn is_poised(&self) -> bool {
        self.operands.iter().all(|f| {
            matches!(f.kind, Formula::Prop(_) | Formula::Not(_))
                || f.marked
                || !f.is_active_at(self.current_time)
        })
    }

    #[must_use]
    pub fn to_formula(&self) -> Formula {
        if self.operands.len() == 1 {
            self.operands[0].clone().kind
        } else {
            Formula::And(self.operands.iter().map(|f| f.kind.clone()).collect())
        }
    }

    pub fn mltl_rewrite(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            f.kind = STLTransformer.visit(&f.kind);
        });
    }

    pub fn negative_normal_form_rewrite(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            f.kind = NegationNormalFormTransformer.visit(&f.kind);
        });
    }

    pub fn flatten(&mut self) {
        let mut flattened: Vec<NodeFormula> = Vec::new();
        for f in &self.operands {
            let flat = FlatTransformer.visit(&f.kind);
            if let Formula::And(ops) = &flat {
                flattened.extend(ops.iter().cloned().map(NodeFormula::from));
            } else {
                flattened.push(NodeFormula::from(flat));
            }
        }
        self.operands = flattened;
    }

    pub fn shift_bounds(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            f.kind = ShiftBoundsTransformer.visit(&f.kind);
        });
    }

    pub fn simplify(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            f.kind = FormulaSimplifier.visit(&f.kind);
        });
    }

    fn compute_target_set(&self) -> HashSet<i32> {
        let mut targets = HashSet::new();

        for operand in &self.operands {
            if !operand.marked {
                continue;
            }

            match &operand.kind {
                Formula::U { right, .. } => {
                    targets.extend(right.calculate_m(self.current_time));
                }
                Formula::R { left, .. } => {
                    targets.extend(left.calculate_m(self.current_time));
                }
                Formula::F { phi, .. } => {
                    targets.extend(phi.calculate_m(self.current_time));
                }
                _ => {}
            }
        }
        targets
    }

    fn compute_obstacle_set(&self) -> HashSet<Interval> {
        let mut obstacles = HashSet::new();

        for operand in &self.operands {
            if operand.is_parent_active_in(self) {
                continue;
            }

            match &operand.kind {
                Formula::R {
                    right: phi_1,
                    interval,
                    ..
                }
                | Formula::U {
                    interval,
                    left: phi_1,
                    ..
                } => {
                    obstacles.extend(phi_1.calculate_s(interval.clone()));
                }
                Formula::G { interval, phi } => {
                    obstacles.extend(phi.calculate_s(Interval {
                        lower: interval.upper,
                        upper: interval.upper,
                    }));
                }
                Formula::Prop(_) | Formula::Not(_) => {
                    obstacles.insert(Interval {
                        lower: self.current_time,
                        upper: self.current_time,
                    });
                }
                _ => {}
            }
        }

        obstacles
    }

    pub fn calculate_k_star(&self, max_jump: i32) -> i32 {
        let targets = self.compute_target_set();
        let obstacles = self.compute_obstacle_set();
        //println!("Targets: {:?}, Obstacles: {:?}", targets, obstacles);

        let step = targets
            .iter()
            .any(|t| obstacles.iter().any(|o| &o.lower <= t && t <= &o.upper));
        if step {
            return 1;
        }
        let jump = targets
            .iter()
            .flat_map(|&t| obstacles.iter().map(move |o| o.lower - t + 1))
            .filter(|&k| k >= 1 && k <= max_jump)
            .min()
            .unwrap_or(max_jump);
        //println!("max jump {max_jump} real jump {jump}");
        jump
    }
}

impl Formula {
    fn calculate_m(&self, delta: i32) -> HashSet<i32> {
        pub fn inner_m(formula: &Formula, delta: i32, set: &mut HashSet<i32>) {
            match formula {
                Formula::Prop(_) => {
                    set.insert(delta);
                }
                Formula::Not(inner) => {
                    inner_m(inner, delta, set);
                }
                Formula::Or(operands) | Formula::And(operands) => {
                    for op in operands {
                        inner_m(op, delta, set);
                    }
                }
                Formula::U {
                    left,
                    right,
                    interval,
                } => {
                    inner_m(left, delta + interval.lower, set);
                    inner_m(right, delta + interval.upper, set);
                }
                Formula::R {
                    left,
                    right,
                    interval,
                } => {
                    inner_m(left, delta + interval.upper, set);
                    inner_m(right, delta + interval.lower, set);
                }
                Formula::Imply {
                    right, not_left, ..
                } => {
                    inner_m(&not_left, delta, set);
                    inner_m(&right, delta, set);
                }
                Formula::G { interval, phi } => {
                    inner_m(&phi, delta + interval.lower, set);
                }
                Formula::F { interval, phi } => {
                    inner_m(&phi, delta + interval.upper, set);
                }
            }
        }
        let mut set = HashSet::new();
        inner_m(&self, delta, &mut set);
        set
    }

    fn calculate_s(&self, interval: Interval) -> HashSet<Interval> {
        pub fn inner_s(formula: &Formula, delta: Interval, set: &mut HashSet<Interval>) {
            match formula {
                Formula::Prop(_) => {
                    set.insert(delta);
                }
                Formula::Not(inner) => {
                    inner_s(&inner, delta, set);
                }
                Formula::Or(operands) | Formula::And(operands) => {
                    for op in operands {
                        inner_s(op, delta.clone(), set);
                    }
                }
                Formula::Imply {
                    not_left, right, ..
                } => {
                    inner_s(&not_left, delta.clone(), set);
                    inner_s(&right, delta, set);
                }
                Formula::G { interval, phi } => {
                    inner_s(
                        &phi,
                        Interval {
                            lower: delta.lower + interval.upper,
                            upper: delta.upper + interval.upper,
                        },
                        set,
                    );
                }
                Formula::F { interval, phi } => {
                    inner_s(
                        &phi,
                        Interval {
                            lower: delta.lower + interval.lower,
                            upper: delta.upper + interval.upper,
                        },
                        set,
                    );
                }
                Formula::R {
                    interval,
                    left,
                    right,
                }
                | Formula::U {
                    interval,
                    left,
                    right,
                } => {
                    inner_s(
                        &left,
                        Interval {
                            lower: delta.lower + interval.lower,
                            upper: delta.upper + interval.upper,
                        },
                        set,
                    );
                    inner_s(
                        &right,
                        Interval {
                            lower: delta.lower + interval.lower,
                            upper: delta.upper + interval.upper,
                        },
                        set,
                    );
                }
            }
        }
        let mut set = HashSet::new();
        inner_s(self, interval, &mut set);
        set
    }
}

impl Clone for Node {
    fn clone(&self) -> Self {
        Self {
            operands: self.operands.clone(),
            current_time: self.current_time,
            implies: None,
            id: NODE_ID.fetch_add(1, Ordering::Relaxed),
        }
    }
}

impl Display for Node {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{} | {}",
            join_with(&self.operands, ", "),
            self.current_time
        )
    }
}

impl Display for NodeFormula {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.marked {
            write!(f, "O{}", self.kind)
        } else {
            write!(f, "{}", self.kind)
        }
    }
}
