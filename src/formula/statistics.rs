use std::collections::HashSet;

use crate::formula::{AExpr, ExprKind, Formula, VariableName};

#[cfg(test)]
mod tests;

impl Formula {
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
            _ => { 1 }
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
}