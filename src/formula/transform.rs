use crate::{formula::{Formula, Interval}, node::Node};

#[cfg(test)]
mod tests;

pub trait RecursiveFormulaTransformer {
    fn visit(&self, formula: &Formula) -> Formula {
        match &formula {
            Formula::And(ops) => self.visit_and(formula, ops),
            Formula::Or(ops) => self.visit_or(formula, ops),
            Formula::Not(inner) => self.visit_not(formula, inner),
            Formula::O(inner) => self.visit_next(formula, inner),
            Formula::G { interval, phi, parent_upper } => self.visit_globally(formula, interval, phi, parent_upper),
            Formula::F { interval, phi, parent_upper } => self.visit_finally(formula, interval, phi, parent_upper),
            Formula::U { interval, left, right, parent_upper } => self.visit_until(formula, interval, left, right, parent_upper),
            Formula::R { interval, left, right, parent_upper } => self.visit_release(formula, interval, left, right, parent_upper),
            Formula::Imply { left, right, not_left } => self.visit_imply(formula, left, right, not_left),
            Formula::Prop(_) => self.visit_leaf(formula),
        }
    }

    fn visit_and(&self, formula: &Formula, ops: &Vec<Formula>) -> Formula {
        formula.with_operands(ops.iter().map(|op| self.visit(op)).collect())
    }

    fn visit_or(&self, formula: &Formula, ops: &Vec<Formula>) -> Formula {
        formula.with_operands(ops.iter().map(|op| self.visit(op)).collect())
    }

    fn visit_not(&self, formula: &Formula, inner: &Formula) -> Formula {
        formula.with_operand(self.visit(inner))
    }

    fn visit_next(&self, formula: &Formula, inner: &Formula) -> Formula {
        formula.with_operand(self.visit(inner))
    }

    fn visit_globally(&self, formula: &Formula, interval: &Interval, phi: &Formula, parent_upper: &Option<i32>) -> Formula {
        formula.with_interval(interval.clone()).with_parent_upper(*parent_upper).with_operand(self.visit(phi))
    }

    fn visit_finally(&self, formula: &Formula, interval: &Interval, phi: &Formula, parent_upper: &Option<i32>) -> Formula {
        formula.with_interval(interval.clone()).with_parent_upper(*parent_upper).with_operand(self.visit(phi))
    }

    fn visit_until(&self, formula: &Formula, interval: &Interval, left: &Formula, right: &Formula, parent_upper: &Option<i32>) -> Formula {
        formula.with_interval(interval.clone()).with_parent_upper(*parent_upper).with_operand_couple(self.visit(left), self.visit(right))
    }

    fn visit_release(&self, formula: &Formula, interval: &Interval, left: &Formula, right: &Formula, parent_upper: &Option<i32>) -> Formula {
        formula.with_interval(interval.clone()).with_parent_upper(*parent_upper).with_operand_couple(self.visit(left), self.visit(right))
    }

    fn visit_imply(&self, formula: &Formula, left: &Formula, right: &Formula, not_left: &Formula) -> Formula {
        formula.with_implication(self.visit(left), self.visit(right), self.visit(not_left))
    }

    fn visit_leaf(&self, formula: &Formula) -> Formula {
        formula.clone()
    }
}

pub struct NegationNormalFormTransformer;
impl RecursiveFormulaTransformer for NegationNormalFormTransformer {
    fn visit_not(&self, formula: &Formula, inner: &Formula) -> Formula {
        match &inner {
            Formula::Not(i) => self.visit(i),
            Formula::And(ops) => Formula::or(ops.iter().map(|f| self.visit(&Formula::not(f.clone()))).collect()),
            Formula::Or(ops) => Formula::and(ops.iter().map(|f| self.visit(&Formula::not(f.clone()))).collect()),
            Formula::Imply { left, right, .. } => Formula::and(vec![*left.clone(), self.visit(&Formula::not(*right.clone()))]),
            Formula::G { phi, interval, parent_upper } => 
                Formula::f(interval.clone(), *parent_upper, self.visit(&Formula::not(*phi.clone()))),
            Formula::F { phi, interval, parent_upper } => 
                Formula::g(interval.clone(), *parent_upper, self.visit(&Formula::not(*phi.clone()))),
            Formula::U { interval, left, right, parent_upper } => 
                Formula::r(interval.clone(), *parent_upper, self.visit(&Formula::not(*left.clone())), self.visit(&Formula::not(*right.clone()))),
            Formula::R { interval, left, right, parent_upper } => 
                Formula::u(Interval { lower: 0, upper: interval.lower }, *parent_upper, self.visit(&Formula::not(*left.clone())), self.visit(&Formula::not(*right.clone()))),
            Formula::O(i) => Formula::o(self.visit(&Formula::not(*i.clone()))),
            _ => formula.clone()
        }
    }
}

struct MLTLTransformer;
impl RecursiveFormulaTransformer for MLTLTransformer {
    fn visit_until(&self, formula: &Formula, interval: &Interval, left: &Formula, right: &Formula, parent_upper: &Option<i32>) -> Formula {
        let g_part = Formula::g(Interval { lower: 0, upper: interval.lower }, None, self.visit(left));
        Formula::and(vec![g_part, formula.with_interval(interval.clone()).with_parent_upper(*parent_upper).with_operand_couple(self.visit(left), self.visit(right))])
    }

    fn visit_release(&self, formula: &Formula, interval: &Interval, left: &Formula, right: &Formula, parent_upper: &Option<i32>) -> Formula {
        let f_part = Formula::f(Interval { lower: 0, upper: interval.lower }, None, self.visit(left));
        Formula::or(vec![f_part, formula.with_interval(interval.clone()).with_parent_upper(*parent_upper).with_operand_couple(self.visit(left), self.visit(right))])
    }
}

struct FlatTransformer;
impl RecursiveFormulaTransformer for FlatTransformer {
    fn visit_and(&self, formula: &Formula, ops: &Vec<Formula>) -> Formula {
        formula.with_operands(
            ops.iter().map(|op| self.visit(op)).flat_map(|flat_op| {
                if let Formula::And(inner_ops) = &flat_op { 
                    inner_ops.clone() 
                } else { 
                    vec![flat_op] 
                }
            }).collect()
        )
    }

    fn visit_or(&self, formula: &Formula, ops: &Vec<Formula>) -> Formula {
        formula.with_operands(
            ops.iter().map(|op| self.visit(op)).flat_map(|flat_op| {
                if let Formula::Or(inner_ops) = &flat_op { 
                    inner_ops.clone() 
                } else { 
                    vec![flat_op] 
                }
            }).collect()
        )
    }
}

struct ShiftBoundsTransformer;
impl RecursiveFormulaTransformer for ShiftBoundsTransformer {

    fn visit_globally(&self, formula: &Formula, interval: &Interval, phi: &Formula, _parent_upper: &Option<i32>) -> Formula {
        let new_phi = self.visit(phi);
        if let Some(shift) = new_phi.get_shift() {
            formula.with_interval(interval.shift_right(shift)).with_operand(ShiftBackwardTransformer(shift).visit(&new_phi))
        } else {
            formula.with_operand(new_phi)
        }
    }
    
    fn visit_finally(&self, formula: &Formula, interval: &Interval, phi: &Formula, _parent_upper: &Option<i32>) -> Formula {
        let new_phi = self.visit(phi);
        if let Some(shift) = new_phi.get_shift() {
            formula.with_interval(interval.shift_right(shift)).with_operand(ShiftBackwardTransformer(shift).visit(&new_phi))
        } else {
            formula.with_operand(new_phi)
        }
    }

    fn visit_until(&self, formula: &Formula, interval: &Interval, left: &Formula, right: &Formula, _parent_upper: &Option<i32>) -> Formula {
        let new_left = self.visit(left);
        let new_right = self.visit(right);
        if let Some(shift) = new_left.get_shift().min(new_right.get_shift()) {
            formula.with_interval(interval.shift_right(shift))
                .with_operand_couple(ShiftBackwardTransformer(shift).visit(&new_left), ShiftBackwardTransformer(shift).visit(&new_right))
        } else {
            formula.with_operand_couple(new_left, new_right)
        }
    }

    fn visit_release(&self, formula: &Formula, interval: &Interval, left: &Formula, right: &Formula, _parent_upper: &Option<i32>) -> Formula {
        let new_left = self.visit(left);
        let new_right = self.visit(right);
        if let Some(shift) = new_left.get_shift().min(new_right.get_shift()) {
            formula.with_interval(interval.shift_right(shift))
                .with_operand_couple(ShiftBackwardTransformer(shift).visit(&new_left), ShiftBackwardTransformer(shift).visit(&new_right))
        } else {
            formula.with_operand_couple(new_left, new_right)
        }
    }
}

struct ShiftBackwardTransformer(i32);
impl RecursiveFormulaTransformer for ShiftBackwardTransformer {
    fn visit_globally(&self, formula: &Formula, interval: &Interval, _phi: &Formula, _parent_upper: &Option<i32>) -> Formula {
        formula.with_interval(interval.shift_left(self.0).unwrap())
    }

    fn visit_finally(&self, formula: &Formula, interval: &Interval, _phi: &Formula, _parent_upper: &Option<i32>) -> Formula {
        formula.with_interval(interval.shift_left(self.0).unwrap())
    }

    fn visit_until(&self, formula: &Formula, interval: &Interval, _left: &Formula, _right: &Formula, _parent_upper: &Option<i32>) -> Formula {
        formula.with_interval(interval.shift_left(self.0).unwrap())
    }

    fn visit_release(&self, formula: &Formula, interval: &Interval, _left: &Formula, _right: &Formula, _parent_upper: &Option<i32>) -> Formula {
        formula.with_interval(interval.shift_left(self.0).unwrap())
    }
}

impl Formula {
    fn get_shift(&self) -> Option<i32> {
        match &self {
            Formula::And(operands) | Formula::Or(operands) => {
                operands.iter().map(|op| op.get_shift()).min().unwrap_or(None)
            }
            Formula::Imply { left, right, not_left } => {
                left.get_shift().min(right.get_shift()).min(not_left.get_shift())
            }
            _ => self.lower_bound(),
        }
    }
}

impl Node {
    pub fn mltl_rewrite(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            *f = MLTLTransformer.visit(f);
        });
    }

    pub fn negative_normal_form_rewrite(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            *f = NegationNormalFormTransformer.visit(f);
        });
    }

    pub fn flatten(&mut self) {
        let mut flattened: Vec<Formula> = Vec::new();
        for f in &self.operands {
            let flat = FlatTransformer.visit(f);
            if let Formula::And(ops) = &flat {
                flattened.extend(ops.iter().cloned());
            } else {
                flattened.push(flat);
            }
        }
        self.operands = flattened;
    }

    pub fn shift_bounds(&mut self) {
        self.operands.iter_mut().for_each(|f| {
            *f = ShiftBoundsTransformer.visit(f);
        });
    }
}