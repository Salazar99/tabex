use std::collections::BTreeSet;
use std::vec;

use crate::formula::*;
use crate::node::*;
use crate::tableau::Tableau;

#[cfg(test)]
mod tests;

impl Tableau {
    pub fn decompose(&self, node: &Node) -> Vec<Node> {
        if self.options.formula_optimizations {
            if let Some(res) = node.rewrite_chain() {
                return res;
            }
        }

        if let Some(res) = self.decompose_and(node) {
            return res;
        }

        if let Some(res) = self.decompose_g(node) {
            return res;
        }

        for (i, operand) in node.operands.iter().enumerate() {
            match &operand.kind {
                FormulaKind::Or(_) => {
                    return self.decompose_or_at(node, i);
                }
                FormulaKind::Imply( .. ) => {
                    return self.decompose_imply_at(node, i);
                }
                _ => {}
            }
        }

        for (i, operand) in node.operands.iter().enumerate() {
            match &operand.kind {
                FormulaKind::F { .. } if operand.is_active_at(node.current_time) => {
                    return self.decompose_f_at(node, i);
                }
                FormulaKind::U { .. } if operand.is_active_at(node.current_time) => {
                    return self.decompose_u_at(node, i);
                }
                FormulaKind::R { .. } if operand.is_active_at(node.current_time) => {
                    return self.decompose_r_at(node, i);
                }
                _ => {}
            }
        }

        if let Some(res) = self.decompose_jump(node) {
            return res;
        }

        vec![]
    }

    pub fn decompose_and(&self, node: &Node) -> Option<Vec<Node>> {
        let mut flattened_operands = Vec::with_capacity(node.operands.len() * 2);
        let mut changed = false;
        
        for operand in &node.operands {
            match &operand.kind {
                FormulaKind::And(inner) => {
                    flattened_operands.extend_from_slice(inner);
                    changed = true;
                }
                _ => flattened_operands.push(operand.clone()),
            }
        }

        if changed { 
            let mut new_node = node.clone();
            new_node.operands = flattened_operands;
            Some(vec![new_node]) 
        } else {
            None
        }
    }

    pub fn decompose_g(&self, node: &Node) -> Option<Vec<Node>> {
        let mut old_nodes: Vec<Formula> = Vec::new();
        let mut g_nodes: Vec<Formula> = Vec::new();

        for operand in &node.operands {
            match &operand.kind {
                FormulaKind::G { interval, .. } if operand.is_active_at(node.current_time) => {
                    g_nodes.push(operand.clone());
                    if node.current_time < interval.upper {
                        old_nodes.push(Formula::o(operand.clone()));
                    }
                }
                _ => old_nodes.push(operand.clone()),
            }
        }
        
        if g_nodes.len() == 0 {
            return None;
        }

        for formula in g_nodes {
            if let FormulaKind::G { interval, phi, .. } = &formula.kind {
                old_nodes.push(phi.temporal_expansion(node.current_time, Some(&interval)));
            }
        }

        let mut new_node = node.clone();
        new_node.operands = old_nodes;

        Some(vec![new_node])
    } 

    pub fn decompose_or_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let FormulaKind::Or(operands) = &node.operands[i].kind else {
            panic!("decompose_or_at called on non-Or formula at index {}", i);
        };
        
        let mut res = Vec::with_capacity(operands.len());
        for op in operands {
            let mut new_node = node.clone();
            new_node.operands[i] = op.clone();
            res.push(new_node);
        }
        res
    }

    pub fn decompose_imply_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let FormulaKind::Imply(left, right) = &node.operands[i].kind else {
            panic!("decompose_imply_at called on non-Imply formula at index {}", i);
        };
        
        let mut new_node1 = node.clone();
        new_node1.operands[i] = Formula::not((**left).clone());
        new_node1.push_negation();

        let mut new_node2 = node.clone();
        new_node2.operands[i] = (**right).clone();
        if self.options.formula_optimizations {
            new_node2.operands.push((**left).clone());
        }

        vec![new_node1, new_node2]
    }

    pub fn decompose_f_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let FormulaKind::F { phi, interval,  .. } = &node.operands[i].kind else {
            panic!("decompose_f_at called on non-F formula at index {}", i);
        };

        if !node.operands[i].is_active_at(node.current_time) {
            panic!("decompose_f_at called on F formula that is not active at current time {}", node.current_time);
        }
        
        let f_formula = &node.operands[i];

        // Node where F is satisfied (p)
        let mut new_node1 = node.clone();
        new_node1.operands[i] = phi.temporal_expansion(node.current_time, None);

        // Node in which F is not satisfied (OF)
        if node.current_time < interval.upper {
            let mut new_node2 = node.clone();
            new_node2.operands[i] = Formula::o(f_formula.clone());
    
            vec![new_node1, new_node2]
        } else {
            vec![new_node1]
        }
    }

    pub fn decompose_u_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let FormulaKind::U { left, right, interval, .. } = &node.operands[i].kind else {
            panic!("decompose_u_at called on non-U formula at index {}", i);
        };

        if !node.operands[i].is_active_at(node.current_time) {
            panic!("decompose_u_at called on U formula that is not active at current time {}", node.current_time);
        }
        
        let u_formula = &node.operands[i];

        // Node where U is satisfied (q)
        let mut new_node1 = node.clone();
        new_node1.operands[i] = right.temporal_expansion(node.current_time, None);

        if node.current_time < interval.upper {
            // Node in which U is not satisfied (p, OU)
            let mut new_node2 = node.clone();
            new_node2.operands[i] = left.temporal_expansion(node.current_time, Some(&interval));
            new_node2.operands.push(Formula::o(u_formula.clone()));
            
            return vec![new_node1, new_node2]
        }
        return vec![new_node1]
    }

    pub fn decompose_r_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let FormulaKind::R { interval, left, right, .. } = &node.operands[i].kind else {
            panic!("decompose_r_at called on non-R formula at index {}", i);
        };

        if !node.operands[i].is_active_at(node.current_time) {
            panic!("decompose_r_at called on R formula that is not active at current time {}", node.current_time);
        }
        
        let r_formula = &node.operands[i];

        // Node where R is satisfied (p and q)
        let mut new_node1: Node = node.clone();
        new_node1.operands[i] = left.temporal_expansion(node.current_time, None);
        new_node1.operands.push(right.temporal_expansion(node.current_time, None));

        // Node in which R is not satisfied (q, OR)
        let mut new_node2 = node.clone();
        new_node2.operands[i] = right.temporal_expansion(node.current_time, Some(interval));
        new_node2.operands.push(Formula::o(r_formula.clone()));

        vec![new_node1, new_node2]
    }

    pub fn decompose_jump(&self, node: &Node) -> Option<Vec<Node>> {
        fn retime_poised(formula: &Formula, current_time: i32, jump: i32) -> Option<Formula> {
            let Some(interval) = formula.get_interval() else {
                return None;
            };
            if current_time >= interval.upper {
                return None;
            }

            if jump != 1 && formula.is_parent_active_at(current_time) {
                Some(formula.with_interval(interval.shift_right(jump)) )
            } else {
                Some(formula.clone())
            }
        }

        fn sorted_time_instants(node: &Node) -> BTreeSet<i32> {
            fn top_level_interval(formula: &Formula, current_time: i32) -> Option<&Interval> {
                match &formula.kind {
                    FormulaKind::O(inner) => top_level_interval(inner, current_time),
                    FormulaKind::G { interval, .. } 
                    | FormulaKind::F { interval, .. } 
                    | FormulaKind::U { interval, .. }
                    | FormulaKind::R { interval, .. } if !formula.is_parent_active_at(current_time) => Some(interval),
                    _ => None
                }
            }
            node.operands.iter().filter_map(|f| top_level_interval(f, node.current_time)).flat_map(|i| 
                [i.lower - 1, i.upper]).collect()
        }

        // Verify jump rule condition
        let step = !self.options.jump_rule_enabled || node.operands.iter().filter_map(|f| {
            if let FormulaKind::O(inner) = &f.kind && !inner.is_parent_active_at(node.current_time) {
                return Some(&**inner);
            }
            None
        }).any(|f| {
            f.upper_bound() == Some(node.current_time) || match &f.kind {
                FormulaKind::G { phi, interval, .. } 
                    | FormulaKind::U { left: phi, interval, .. }
                    | FormulaKind::R { right: phi, interval, .. } => {
                        match phi.get_max_upper() {
                            None => false,
                            Some(max_upper) => node.current_time < interval.lower + max_upper
                        }
                    }
                    _ => false
                }
            });
            
        // Select jump length
        let jump = if step {
            1
        } else {
            if let Some(target_time) = sorted_time_instants(node).into_iter().find(|&t| t > node.current_time) {
                target_time - node.current_time
            } else {
                return None
            }
        };

        // Retain only temporal operators, and retimed O formulas
        let new_operands: Vec<Formula> = node.operands.iter().filter_map(|op| match &op.kind {
            FormulaKind::G {..} | FormulaKind::F {..} | FormulaKind::U {..} | FormulaKind::R {..} => retime_poised(op, node.current_time, jump),
            FormulaKind::O(inner) => retime_poised(inner, node.current_time, jump),
            _ => None,
        }).collect();

        // Construct return value
        if new_operands.is_empty() {
            return None;
        }
        
        let mut new_node = node.clone();
        new_node.operands = new_operands;
        new_node.current_time += jump;
        
        if self.options.simple_first {
            let simple_operands: Vec<Formula> = new_node.operands.iter().filter(|f| !f.is_complex_temporal_operator()).cloned().collect();
            if !simple_operands.is_empty() && simple_operands.len() < new_node.operands.len(){
                let mut simple_node = new_node.clone();
                simple_node.operands = simple_operands;
                simple_node.implies_siblings = true;
                return Some(vec![simple_node, new_node])
            }
        }
        return Some(vec![new_node])
    }
}

impl Formula {
    fn temporal_expansion(&self, current_time: i32, parent_interval: Option<&Interval>) -> Formula {
        match &self.kind {
            FormulaKind::Prop(_) | FormulaKind::Not(_) | FormulaKind::True | FormulaKind::False => self.clone(),
            FormulaKind::F { interval, .. } | FormulaKind::G { interval, .. }
            | FormulaKind::U { interval, .. } | FormulaKind::R { interval, .. } => {
                self.with_interval(interval.shift_right(current_time)).with_parent_upper(parent_interval.map(|p| p.upper))
            }
            FormulaKind::And(operands) | FormulaKind::Or(operands) => {
                self.with_operands(operands.iter().map(|op| op.temporal_expansion(current_time, parent_interval)).collect())
            }
            FormulaKind::Imply(left, right) => {
                self.with_implications(
                    left.temporal_expansion(current_time, parent_interval), 
                    right.temporal_expansion(current_time, parent_interval)
                )
            }
            _ => panic!()
        }
    }
}