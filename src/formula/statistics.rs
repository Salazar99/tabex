use std::collections::HashSet;

use crate::formula::{AExpr, ExprKind, Formula, VariableName};

#[cfg(test)]
mod tests;

impl Formula {

    pub fn temporal_operator_depth(&self) -> i32 {
        match self {
            Formula::And(ops) | Formula::Or(ops) => {
                ops.iter().map(|f| f.temporal_operator_depth()).max().unwrap_or(0)
            }
            Formula::Not(f) => {
                f.temporal_operator_depth()
            }
            Formula::O(f) | Formula::F { phi: f, .. } | Formula::G { phi: f, .. } => {
                1 + f.temporal_operator_depth()
            }
            Formula::U { left, right, .. } | Formula::R { left, right, .. } => {
                1 + left.temporal_operator_depth().max(right.temporal_operator_depth())
            }
            Formula::Imply { left, right, .. } => {
                left.temporal_operator_depth().max(right.temporal_operator_depth())
            }
            _ => { 0 }
        }
    }

    pub fn depth(&self) -> i32 {
        match self {
            Formula::And(ops) | Formula::Or(ops) => {
                1 + ops.iter().map(|f| f.depth()).max().unwrap_or(0)
            }
            Formula::Not(f) | Formula::O(f) | Formula::F { phi: f, .. } | Formula::G { phi: f, .. } => {
                1 + f.depth()
            }
            Formula::U { left, right, .. } | Formula::R { left, right, .. } | Formula::Imply { left, right, .. } => {
                1 + left.depth().max(right.depth())
            }
            _ => { 0 }
        }
    }

    pub fn length(&self) -> i32 {
        match self {
            Formula::And(ops) | Formula::Or(ops) => {
                ops.iter().map(|f| f.length()).max().unwrap_or(0)
            }
            Formula::Not(f) | Formula::O(f) => {
                f.length()
            }
            Formula::Imply { left, right, .. } => {
                left.length().max(right.length())
            }
            Formula::F { phi, interval, .. } | Formula::G { phi, interval, .. } => {
                interval.upper + phi.length()
            }
            Formula::U { left, right, interval, .. } | Formula::R { left, right, interval, .. }  => {
                interval.upper + left.length().max(right.length())
            }
            _ => { 0 }
        }
    }
    
    pub fn boolean_variables(&self) -> i32 {
        fn inner_boolean_variables(formula: &Formula, boolean_vars: &mut HashSet<VariableName>) {
            match formula {
                Formula::And(ops) | Formula::Or(ops) => {
                    for f in ops {
                        inner_boolean_variables(f, boolean_vars);
                    }
                }
                Formula::Not(f) | Formula::O(f) | Formula::F { phi: f, .. } | Formula::G { phi: f, .. } => {
                    inner_boolean_variables(f, boolean_vars);
                }
                Formula::U { left, right, .. } | Formula::R { left, right, .. } | Formula::Imply { left, right, .. } => {
                    inner_boolean_variables(left, boolean_vars);
                    inner_boolean_variables(right, boolean_vars);
                }
                Formula::Prop(expr) => {
                    if let ExprKind::Atom(str) = &expr.kind {
                        boolean_vars.insert(str.clone());
                    }
                }
            }
        }
        let mut boolean_vars = HashSet::new();
        inner_boolean_variables(self, &mut boolean_vars);
        boolean_vars.len() as i32
    }

    pub fn real_variables(&self) -> i32 {
        fn inner_real_variables(formula: &Formula, real_vars: &mut HashSet<VariableName>) {
            match formula {
                Formula::And(ops) | Formula::Or(ops) => {
                    for f in ops {
                        inner_real_variables(f, real_vars);
                    }
                }
                Formula::Not(f) | Formula::O(f) | Formula::F { phi: f, .. } | Formula::G { phi: f, .. } => {
                    inner_real_variables(f, real_vars);
                }
                Formula::U { left, right, .. } | Formula::R { left, right, .. } | Formula::Imply { left, right, .. } => {
                    inner_real_variables(left, real_vars);
                    inner_real_variables(right, real_vars);
                }
                Formula::Prop(expr) => {
                    if let ExprKind::Rel {left, right, .. } = &expr.kind {
                        inner_real_variables_aexpr(left, real_vars);
                        inner_real_variables_aexpr(right, real_vars);
                    }
                }
            }
        }

        fn inner_real_variables_aexpr(aexpr: &crate::formula::AExpr, real_vars: &mut HashSet<VariableName>) {
            match aexpr {
                AExpr::Var(var_name) => {
                    real_vars.insert(var_name.clone());
                }
                AExpr::BinOp { left, right, .. } => {
                    inner_real_variables_aexpr(left, real_vars);
                    inner_real_variables_aexpr(right, real_vars);
                }
                AExpr::Abs(aexpr) => {
                    inner_real_variables_aexpr(aexpr, real_vars);
                }
                _ => {}
            }
        }

        let mut real_vars = HashSet::new();
        inner_real_variables(self, &mut real_vars);
        real_vars.len() as i32
    }

    pub fn variables(&self) -> i32 {
        self.boolean_variables() + self.real_variables()
    }

    pub fn boolean_constraints(&self) -> i32 {
        match self {
            Formula::And(ops) | Formula::Or(ops) => {
                ops.iter().map(|f| f.boolean_constraints()).sum()
            }
            Formula::Not(f) | Formula::O(f) => {
                f.boolean_constraints()
            }
            Formula::Imply { left, right, .. } => {
                left.boolean_constraints() + right.boolean_constraints()
            }
            Formula::F { phi, .. } | Formula::G { phi, .. } => {
                phi.boolean_constraints()
            }
            Formula::U { left, right, .. } | Formula::R { left, right, .. }  => {
                left.boolean_constraints() + right.boolean_constraints()
            }
            Formula::Prop(expr) => {
                if let ExprKind::Atom(_) = expr.kind {
                    1
                } else {
                    0
                }
            }
        }
    }

    pub fn real_constraints(&self) -> i32 {
        match self {
            Formula::And(ops) | Formula::Or(ops) => {
                ops.iter().map(|f| f.real_constraints()).sum()
            }
            Formula::Not(f) | Formula::O(f) => {
                f.real_constraints()
            }
            Formula::Imply { left, right, .. } => {
                left.real_constraints() + right.real_constraints()
            }
            Formula::F { phi, .. } | Formula::G { phi, .. } => {
                phi.real_constraints()
            }
            Formula::U { left, right, .. } | Formula::R { left, right, .. }  => {
                left.real_constraints() + right.real_constraints()
            }
            Formula::Prop(expr) => {
                if let ExprKind::Rel {..} = expr.kind {
                    1
                } else {
                    0
                }
            }
        }
    }

    pub fn constraints(&self) -> i32 {
        self.boolean_constraints() + self.real_constraints()
    }

    pub fn disjunction_max_width(&self) -> usize {
        debug_assert!(self.is_flat());
        match self {
            Formula::Or(ops) => {
                let inner = ops.iter().map(|f| f.disjunction_max_width()).max().unwrap_or(0);
                ops.len().max(inner)
            }
            Formula::And(ops) => ops.iter().map(|f| f.disjunction_max_width()).max().unwrap_or(0),
            Formula::Not(f) => f.disjunction_max_width(),
            Formula::O(f) | Formula::F { phi: f, .. } | Formula::G { phi: f, .. } => f.disjunction_max_width(),
            Formula::U { left, right, .. }
            | Formula::R { left, right, .. }
            | Formula::Imply { left, right, .. } => {
                left.disjunction_max_width().max(right.disjunction_max_width())
            }
            _ => 0,
        }
    }

    pub fn disjunction_total_width(&self) -> usize {
        debug_assert!(self.is_flat());
        match self {
            Formula::Or(ops) => {
                let inner_sum: usize = ops.iter().map(|f| f.disjunction_total_width()).sum();
                ops.len() + inner_sum
            }
            Formula::And(ops) => ops.iter().map(|f| f.disjunction_total_width()).sum(),
            Formula::Not(f) => f.disjunction_total_width(),
            Formula::O(f) | Formula::F { phi: f, .. } | Formula::G { phi: f, .. } => f.disjunction_total_width(),
            Formula::U { left, right, .. }
            | Formula::R { left, right, .. }
            | Formula::Imply { left, right, .. } => {
                left.disjunction_total_width() + right.disjunction_total_width()
            }
            _ => 0,
        }
    }

    pub fn combinatorial_branching_count(&self) -> i32 {
        debug_assert!(self.is_flat());
        match self {
            Formula::Or(ops) => {
                ops.iter().map(|f| f.combinatorial_branching_count()).sum()
            }
            Formula::And(ops) => {
                ops.iter().map(|f| f.combinatorial_branching_count()).product()
            }
            Formula::Not(f)
            | Formula::O(f)
            | Formula::F { phi: f, .. }
            | Formula::G { phi: f, .. } => f.combinatorial_branching_count(),
            Formula::U { left, right, .. }
            | Formula::R { left, right, .. } => {
                left.combinatorial_branching_count() * right.combinatorial_branching_count()
            }
            Formula::Imply { not_left, right, .. } => {
                not_left.combinatorial_branching_count() + right.combinatorial_branching_count()
            }
            _ => 1,
        }
    }
}