#![allow(unused)]
use std::fs::OpenOptions;

use crate::formula::*;
use crate::node::*;

impl Node {
    pub fn decompose(&self) -> Result<Vec<Node>, String> {
        if let Some(res) = self.decompose_and() {
            return Ok(res);
        }

        if let Some(res) = self.decompose_g() {
            return Ok(res);
        }

        if let Some(res) = self.decompose_or() {
            return Ok(res);
        }

        if let Some(res) = self.decompose_f() {
            return Ok(res);
        }

        if let Some(res) = self.decompose_jump() {
            return Ok(res);
        }

        Err("No decomposition found".into())
    }

    pub fn decompose_and(&self) -> Option<Vec<Node>> {
        let mut new_node = self.clone();
        let mut changed = false;

        let mut out = Vec::new();
        for child in &mut new_node.operands.drain(..) {
            match child {
                Formula::And(mut inner) => {
                    out.append(&mut inner);
                    changed = true;
                }
                other => out.push(other),
            }
        }
        new_node.operands = out;
        if changed { Some(vec![new_node]) } else { None }
    }

    pub fn decompose_g(&self) -> Option<Vec<Node>> {
        let mut new_node = self.clone();
        let mut g_nodes: Vec<Formula> = Vec::new();

        for i in 0..new_node.operands.len() {
            if let Formula::G { interval, phi, .. } = &new_node.operands[i] && interval.lower == self.current_time {
                let new_operand = new_node.operands[i].clone();
                g_nodes.push(new_operand.clone());
                if interval.lower < interval.upper {
                    new_node.operands[i] = Formula::O(Box::new(new_operand));
                } else {
                    if new_node.operands[i].check_boolean_closure() &&
                    new_node.operands.iter().enumerate().any(|(j, other)| 
                    j != i && other.lower_bound() == Some(interval.lower)
                ) {
                    new_node.jump1 = true;
                }
                new_node.operands[i] = Formula::True;
            }
            }
        }
        new_node.operands.retain(|f| !matches!(f, Formula::True));

        for node in &g_nodes {
            if let Formula::G { interval, phi, parent_interval } = node {
                new_node.operands.push(phi.temporal_expansion(self.current_time, parent_interval));
            }
        }

        if !g_nodes.is_empty() {
            Some(vec![new_node])
        } else {
            None
        }
    }

    pub fn decompose_or(&self) -> Option<Vec<Node>> {
        for i in 0..self.operands.len() {
            if let Formula::Or(operands) = &self.operands[i] {
                let mut res = Vec::new();
                for op in operands {
                    let mut new_node = self.clone();
                    new_node.operands[i] = op.clone();
                    res.push(new_node);
                }
                return Some(res);
            }
        }
        None
    }

    pub fn decompose_f(&self) -> Option<Vec<Node>> {
        for i in 0..self.operands.len() {
            if let Formula::F { interval, phi, parent_interval } = &self.operands[i] {
                if interval.lower == self.current_time {
                    let f_formula = &self.operands[i];

                    let mut new_node1 = self.clone();
                    new_node1.operands[i] = Formula::O(Box::new(f_formula.clone()));

                    let mut new_node2 = self.clone();
                    new_node2.operands[i] = phi.temporal_expansion(interval.lower, parent_interval);

                    // Check condition for jump1
                    if interval.lower == interval.upper {
                        if new_node2.operands[i].check_boolean_closure() &&
                            new_node2.operands.iter().enumerate().any(|(j, other)| 
                                j != i && other.lower_bound() == Some(interval.lower)
                            ) {
                            new_node2.jump1 = true;
                        }
                    }

                    return Some(vec![new_node2, new_node1]);
                }
            }
        }
        None
    }

    pub fn decompose_jump(&self) -> Option<Vec<Node>> {

        let problematic: bool = self.operands.iter().any(|f| f.jump_problematic());
        let time_instants = self.sorted_time_instants();
        if !problematic {
            if time_instants.is_empty() {
                return None;
            } 

            // Determine the new time
            let new_time = if self.jump1 {
                self.current_time + 1
            } else {
                time_instants
                    .iter()
                    .find(|&&t| t > self.current_time)
                    .copied()
                    .unwrap_or(self.current_time)
            };

            // Construct new operands
            let mut new_operands = Vec::new();
            for operand in &self.operands {
                match operand {
                    Formula::Not(_) 
                        | Formula::Prop(_) 
                        | Formula::True 
                        | Formula::False 
                        | Formula::And(_) 
                        | Formula::Or(_) => (),
                    Formula::O(inner) => {
                        if let (Some(lb), Some(ub)) = (inner.lower_bound(), inner.upper_bound()) && lb < ub {
                            let mut sub_formula = (**inner).clone();
                            if let Formula::F { ref mut interval, .. }
                                | Formula::G { ref mut interval, .. }
                                | Formula::U { ref mut interval, .. } = sub_formula {
                                interval.lower = new_time;
                            }
                            new_operands.push(sub_formula);
                        }
                    }
                    _ => {
                        new_operands.push(operand.clone());
                    }
                }
            }

            if !new_operands.is_empty() {
                let mut new_node = self.clone();
                new_node.jump1 = false;
                new_node.operands = new_operands;
                new_node.current_time = new_time;
                Some(vec![new_node])
            } else {
                None
            }
        } else {
            // Compute time jump
            let mut jump = 1;

            // Build Node
            let mut new_operands = Vec::new();
            for operand in &self.operands {
                match operand {
                    Formula::G {..} 
                    | Formula::F {..} 
                    | Formula::U {..} => {
                        new_operands.push(operand.clone());
                    }
                    Formula::O(inner) => {
                        if let (Some(lb), Some(ub)) = (inner.lower_bound(), inner.upper_bound()) && lb < ub {
                            let mut sub_formula = (**inner).clone();
                            if let Formula::F { ref mut interval, .. }
                                | Formula::G { ref mut interval, .. }
                                | Formula::U { ref mut interval, .. } = sub_formula {
                                interval.lower = self.current_time + 1;
                            }
                            new_operands.push(sub_formula);
                        }
                    }
                    _ => {}
                }
            }

            if !new_operands.is_empty() {
                let mut new_node = self.clone();
                new_node.jump1 = false;
                new_node.operands = new_operands;
                new_node.current_time += jump;
                Some(vec![new_node])
            } else {
                None
            }
        }
    }
}

impl Formula {
    fn temporal_expansion(&self, current_time: i64, formula_interval: &Option<Interval>) ->  Formula {
        match self {
            Formula::Prop(_) | Formula::Not(_) | Formula::True | Formula::False => self.clone(),
            Formula::F { interval, .. } | Formula::G { interval, .. } => {
                let mut extract = self.clone();
                if let Formula::F { interval: ref mut int, parent_interval: ref mut par_int, .. }
                    | Formula::G { interval: ref mut int, parent_interval: ref mut par_int, .. } = extract
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

    fn check_boolean_closure(&self) -> bool {
        match self {
            Formula::Not(inner) => inner.check_boolean_closure(),
            Formula::And(v) | Formula::Or(v) => v.iter().all(|f| f.check_boolean_closure()),
            _ => matches!(self, Formula::Prop(_)),
        }
    }
}