#![allow(unused)]
use std::fs::OpenOptions;

use crate::formula::*;
use crate::node::*;
use crate::tableau::TableauData;
use crate::solver::Solver;

impl Node {
    pub fn decompose(&self) -> Vec<Node> {
        if let Some(res) = self.decompose_and() {
            return res;
        }

        if let Some(res) = self.decompose_g() {
            return res;
        }

        for (i, operand) in self.operands.iter().enumerate() {
            match operand {
                Formula::Or(_) => {
                    return self.decompose_or_at(i);
                }
                Formula::Imply(left, right) => {
                    return self.decompose_imply_at(i);
                }
                Formula::F { interval, .. } if interval.lower == self.current_time => {
                    return self.decompose_f_at(i);
                }
                Formula::U { interval, .. } if interval.lower == self.current_time => {
                    return self.decompose_u_at(i);
                }
                Formula::R { interval, .. } if interval.lower == self.current_time => {
                    return self.decompose_r_at(i);
                }
                _ => {}
            }
        }

        if let Some(res) = self.decompose_jump() {
            return res;
        }

        vec![]
    }

    pub fn decompose_and(&self) -> Option<Vec<Node>> {
        let mut out = Vec::with_capacity(self.operands.len() * 2);
        let mut changed = false;
        
        for operand in &self.operands {
            match operand {
                Formula::And(inner) => {
                    changed = true;
                    out.extend_from_slice(inner);
                }
                other => out.push(other.clone()),
            }
        }

        if changed { 
            let mut new_node = self.clone();
            new_node.operands = out;
            Some(vec![new_node]) 
        } else {
            None
        }
    }

    pub fn decompose_g(&self) -> Option<Vec<Node>> {
        let mut g_nodes: Vec<Formula> = Vec::new();
        let mut old_nodes: Vec<Formula> = Vec::new();
        let mut changed = false;
        let mut jump1 = false;

        for operand in &self.operands {
            match operand {
                Formula::G { interval, phi, .. } if interval.lower == self.current_time => {
                    changed = true;
                    g_nodes.push(operand.clone());
                    if interval.lower < interval.upper {
                        old_nodes.push(Formula::O(Box::new(operand.clone())));
                    } else {
                        if operand.check_boolean_closure() &&
                        self.operands.iter().any(|other| 
                        other != operand && other.lower_bound() == Some(interval.lower)) {
                            jump1 = true;
                        }
                    }
                }
                _ => old_nodes.push(operand.clone()),
            }
        }

        if !changed {
            return None;
        }

        let mut new_node = self.clone();
        new_node.operands = old_nodes;
        new_node.jump1 = jump1;

        for formula in &g_nodes {
            if let Formula::G { interval, phi, parent_interval } = formula {
                new_node.operands.push(phi.temporal_expansion(self.current_time, parent_interval));
            }
        }
        Some(vec![new_node])
    }

    pub fn decompose_or_at(&self, i: usize) -> Vec<Node> {
        let Formula::Or(operands) = &self.operands[i] else {
            panic!("decompose_or_at called on non-Or formula at index {}", i);
        };
        
        let mut res = Vec::with_capacity(operands.len());
        for op in operands {
            let mut new_node = self.clone();
            new_node.operands[i] = op.clone();
            res.push(new_node);
        }
        res
    }

    pub fn decompose_imply_at(&self, i: usize) -> Vec<Node> {
        let Formula::Imply(left, right) = &self.operands[i] else {
            panic!("decompose_imply_at called on non-Imply formula at index {}", i);
        };
        
        let mut new_node1 = self.clone();
        new_node1.operands[i] = Formula::Not(Box::new((**left).clone()));

        let mut new_node2 = self.clone();
        new_node2.operands[i] = (**left).clone();
        new_node2.operands.push((**right).clone());

        vec![new_node1, new_node2]
    }

    pub fn decompose_f_at(&self, i: usize) -> Vec<Node> {
        let Formula::F { interval, phi, parent_interval } = &self.operands[i] else {
            panic!("decompose_f_at called on non-F formula at index {}", i);
        };
        
        if interval.lower != self.current_time {
            panic!("decompose_f_at called with interval.lower ({}) != current_time ({})", interval.lower, self.current_time);
        }
        
        let f_formula = &self.operands[i];

        // Node where F is satisfied (p)
        let mut new_node1 = self.clone();
        new_node1.operands[i] = phi.temporal_expansion(interval.lower, parent_interval);

        // Check condition for jump1
        if interval.lower == interval.upper {
            if new_node1.operands[i].check_boolean_closure() &&
                new_node1.operands.iter().enumerate().any(|(j, other)| 
                    j != i && other.lower_bound() == Some(interval.lower)
                ) {
                new_node1.jump1 = true;
            }
        }

        // Node in which F is not satisfied (OF)
        let mut new_node2 = self.clone();
        new_node2.operands[i] = Formula::O(Box::new(f_formula.clone()));

        vec![new_node1, new_node2]
    }

    pub fn decompose_u_at(&self, i: usize) -> Vec<Node> {
        let Formula::U { interval, left, right, parent_interval } = &self.operands[i] else {
            panic!("decompose_u_at called on non-U formula at index {}", i);
        };
        
        if interval.lower != self.current_time {
            panic!("decompose_u_at called with interval.lower ({}) != current_time ({})", interval.lower, self.current_time);
        }
        
        let u_formula = &self.operands[i];

        // Node in which U is not satisfied (p, OU)
        let mut new_node1 = self.clone();
        new_node1.operands[i] = left.temporal_expansion(interval.lower, parent_interval);
        new_node1.operands.push(Formula::O(Box::new(u_formula.clone())));
        
        // Node where U is satisfied (q)
        let mut new_node2 = self.clone();
        new_node2.operands[i] = right.temporal_expansion(interval.lower, parent_interval);
        // Check condition for jump1
        if interval.lower == interval.upper {
            if right.check_boolean_closure() &&
                new_node2.operands.iter().enumerate().any(|(j, other)| 
                    j != i && other.lower_bound() == Some(interval.lower)
                ) {
                new_node2.jump1 = true;
            }
        }

        vec![new_node1, new_node2]
    }

    pub fn decompose_r_at(&self, i: usize) -> Vec<Node> {
        let Formula::R { interval, left, right, parent_interval } = &self.operands[i] else {
            panic!("decompose_r_at called on non-R formula at index {}", i);
        };
        
        if interval.lower != self.current_time {
            panic!("decompose_r_at called with interval.lower ({}) != current_time ({})", interval.lower, self.current_time);
        }
        
        let r_formula = &self.operands[i];

        // Node where R is satisfied (p and q)
        let mut new_node1: Node = self.clone();
        new_node1.operands[i] = left.temporal_expansion(interval.lower, parent_interval);
        new_node1.operands.push(right.temporal_expansion(interval.lower, parent_interval));

        // Node in which R is not satisfied (q, OR)
        let mut new_node2 = self.clone();
        new_node2.operands[i] = right.temporal_expansion(interval.lower, parent_interval);
        if interval.lower < interval.upper {
            new_node2.operands.push(Formula::O(Box::new(r_formula.clone())));
        } else {
            if right.check_boolean_closure() &&
                new_node2.operands.iter().enumerate().any(
                    |(j, other)| 
                    j != i && other.lower_bound() == Some(interval.lower)
                ) {
                new_node2.jump1 = true;
            }
        }

        vec![new_node1, new_node2]
    }

    pub fn decompose_jump(&self) -> Option<Vec<Node>> {
        fn retime_poised(formula: &Formula, target_time: i64) -> Option<Formula> {
            let (Some(lb), Some(ub)) = (formula.lower_bound(), formula.upper_bound()) else {
              return None
            };
            if lb >= ub {
                return None;
            }
            let mut sub_formula = formula.clone();
            if let Formula::F { ref mut interval, .. }
                | Formula::G { ref mut interval, .. }
                | Formula::U { ref mut interval, .. }
                | Formula::R { ref mut interval, .. } = sub_formula {
                interval.lower = target_time;
            }
            Some(sub_formula)
        }

        let problematic: bool = self.operands.iter().any(|f| f.jump_problematic());
        let next_time = self.sorted_time_instants().into_iter().find(|&t| t > self.current_time);
        
        if !problematic && !self.jump1 && next_time.is_none() {
            return None;
        }

        // Determine target_time
        let target_time = if problematic || self.jump1 {
            self.current_time + 1
        } else {
            next_time.unwrap()
        };

        // Retain only temporal operators, and retimed O formulas
        let new_operands: Vec<Formula> = self.operands.iter().filter_map(|op| match op {
            f @ (Formula::G {..} | Formula::F {..} | Formula::U {..} | Formula::R {..}) => Some(f.clone()),
            Formula::O(inner) => retime_poised(inner, target_time),
            _ => None,
        }).collect();

        // Construct return value
        if new_operands.is_empty() {
            None
        } else {
            let mut new_node = self.clone();
            new_node.jump1 = false;
            new_node.operands = new_operands;
            new_node.current_time = target_time;
            Some(vec![new_node])
        } 
    }
}

impl Formula {
    fn temporal_expansion(&self, current_time: i64, formula_interval: &Option<Interval>) ->  Formula {
        match self {
            Formula::Prop(_) | Formula::Not(_) | Formula::True | Formula::False => self.clone(),
            Formula::F { interval, .. } 
            | Formula::G { interval, .. }
            | Formula::U { interval, .. }
            | Formula::R { interval, .. } => {
                let mut extract = self.clone();
                if let Formula::F { interval: ref mut int, parent_interval: ref mut par_int, .. }
                    | Formula::G { interval: ref mut int, parent_interval: ref mut par_int, .. }
                    | Formula::U { interval: ref mut int, parent_interval: ref mut par_int, .. }
                    | Formula::R { interval: ref mut int, parent_interval: ref mut par_int, .. } = extract
                {
                    int.lower = interval.lower + current_time;
                    int.upper = interval.upper + current_time;
                    *par_int = formula_interval.clone();
                }
                extract
            }
            Formula::And(operands) => {
                let new_operands = operands.iter().map(|op| op.temporal_expansion(current_time, formula_interval)).collect();
                Formula::And(new_operands)
            }
            Formula::Or(operands) => {
                let new_operands = operands.iter().map(|op| op.temporal_expansion(current_time, formula_interval)).collect();
                Formula::Or(new_operands)
            }
            _ => self.clone(), // For other cases, return as is
        }
    }

    pub fn check_boolean_closure(&self) -> bool {
        match self {
            Formula::Not(inner) => inner.check_boolean_closure(),
            Formula::And(v) | Formula::Or(v) => v.iter().all(|f| f.check_boolean_closure()),
            Formula::Prop(_) | Formula::True | Formula::False => true,
            _ => false,
        }
    }
}