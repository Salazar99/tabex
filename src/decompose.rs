use crate::formula::*;
use crate::node::*;
use crate::rewrite::rewrite_chain;
use crate::tableau::TableauData;

#[cfg(test)]
mod tests;

impl TableauData {
    pub fn decompose(&self, node: &Node) -> Vec<Node> {
        if self.options.formula_optimizations {
            if let Some(res) = rewrite_chain(&node.operands, node.current_time) {
                let mut new_node = node.clone();
                new_node.operands = res;
                return vec![new_node]
            }
        }

        if let Some(res) = node.decompose_and() {
            return res;
        }

        if let Some(res) = node.decompose_g() {
            return res;
        }

        for (i, operand) in node.operands.iter().enumerate() {
            match operand {
                Formula::Or(_) => {
                    return node.decompose_or_at(i);
                }
                Formula::Imply( .. ) => {
                    return node.decompose_imply_at(i, self.options.formula_optimizations);
                }
                Formula::F { .. } if operand.active(node.current_time) => {
                    return node.decompose_f_at(i);
                }
                Formula::U { .. } if operand.active(node.current_time) => {
                    return node.decompose_u_at(i);
                }
                Formula::R { .. } if operand.active(node.current_time) => {
                    return node.decompose_r_at(i);
                }
                _ => {}
            }
        }

        if let Some(res) = node.decompose_jump(self.options.simple_first, self.options.jump_rule_enabled) {  
            return res;
        }

        vec![]
    }
}

impl Node {
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
        let mut old_nodes: Vec<Formula> = Vec::new();
        let mut changed = false;

        for operand in &self.operands {
            match operand {
                Formula::G { interval, phi, .. } if operand.active(self.current_time) => {
                    changed = true;
                    old_nodes.push(phi.temporal_expansion(self.current_time, Some(&interval)));
                    if self.current_time < interval.upper {
                        old_nodes.push(Formula::O(Box::new(operand.clone())));
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

    pub fn decompose_imply_at(&self, i: usize, formula_optimizations: bool) -> Vec<Node> {
        let Formula::Imply(left, right) = &self.operands[i] else {
            panic!("decompose_imply_at called on non-Imply formula at index {}", i);
        };
        
        let mut new_node1 = self.clone();
        new_node1.operands[i] = Formula::Not(Box::new((**left).clone()));
        new_node1.push_negation();

        let mut new_node2 = self.clone();
        new_node2.operands[i] = (**right).clone();
        if formula_optimizations {
            new_node2.operands.push((**left).clone());
        }

        vec![new_node1, new_node2]
    }

    pub fn decompose_f_at(&self, i: usize) -> Vec<Node> {
        let Formula::F { phi, .. } = &self.operands[i] else {
            panic!("decompose_f_at called on non-F formula at index {}", i);
        };

        if !self.operands[i].active(self.current_time) {
            panic!("decompose_f_at called on F formula that is not active at current time {}", self.current_time);
        }
        
        let f_formula = &self.operands[i];

        // Node where F is satisfied (p)
        let mut new_node1 = self.clone();
        new_node1.operands[i] = phi.temporal_expansion(self.current_time, None);

        // Node in which F is not satisfied (OF)
        let mut new_node2 = self.clone();
        new_node2.operands[i] = Formula::O(Box::new(f_formula.clone()));

        vec![new_node1, new_node2]
    }

    pub fn decompose_u_at(&self, i: usize) -> Vec<Node> {
        let Formula::U { left, right, interval, .. } = &self.operands[i] else {
            panic!("decompose_u_at called on non-U formula at index {}", i);
        };

        if !self.operands[i].active(self.current_time) {
            panic!("decompose_u_at called on U formula that is not active at current time {}", self.current_time);
        }
        
        let u_formula = &self.operands[i];

        // Node where U is satisfied (q)
        let mut new_node1 = self.clone();
        new_node1.operands[i] = right.temporal_expansion(self.current_time, None);

        // Node in which U is not satisfied (p, OU)
        let mut new_node2 = self.clone();
        new_node2.operands[i] = left.temporal_expansion(self.current_time, Some(&interval));
        new_node2.operands.push(Formula::O(Box::new(u_formula.clone())));
        

        vec![new_node1, new_node2]
    }

    pub fn decompose_r_at(&self, i: usize) -> Vec<Node> {
        let Formula::R { interval, left, right, .. } = &self.operands[i] else {
            panic!("decompose_r_at called on non-R formula at index {}", i);
        };

        if !self.operands[i].active(self.current_time) {
            panic!("decompose_r_at called on R formula that is not active at current time {}", self.current_time);
        }
        
        let r_formula = &self.operands[i];

        // Node where R is satisfied (p and q)
        let mut new_node1: Node = self.clone();
        new_node1.operands[i] = left.temporal_expansion(self.current_time, None);
        new_node1.operands.push(right.temporal_expansion(self.current_time, None));

        // Node in which R is not satisfied (q, OR)
        let mut new_node2 = self.clone();
        new_node2.operands[i] = right.temporal_expansion(self.current_time, Some(interval));
        new_node2.operands.push(Formula::O(Box::new(r_formula.clone())));

        vec![new_node1, new_node2]
    }

    pub fn decompose_jump(&self, simple_first: bool, jump_enabled: bool) -> Option<Vec<Node>> {
        fn retime_poised(formula: &Formula, current_time: i32, jump: i32) -> Option<Formula> {
            let Some(ub) = formula.upper_bound() else {
              return None
            };
            if current_time >= ub {
                return None;
            }

            let mut sub_formula = formula.clone();
            match &mut sub_formula {
                Formula::G { interval, .. }
                | Formula::F { interval, .. }
                | Formula::U { interval, .. }
                | Formula::R { interval, .. } if jump != 1 && formula.parent_active(current_time) => {
                    interval.lower += jump;
                    interval.upper += jump;
                }
                _ => {}
            }
            Some(sub_formula)
        }

        fn sorted_time_instants(node: &Node) -> Vec<i32> {
            fn top_level_interval(formula: &Formula, current_time: i32) -> Option<&Interval> {
                match formula {
                    Formula::O(inner) => top_level_interval(inner, current_time),
                    Formula::G { interval, .. } 
                    | Formula::F { interval, .. } 
                    | Formula::U { interval, .. }
                    | Formula::R { interval, .. } if !formula.parent_active(current_time) => Some(interval),
                    _ => None
                }
            }

            let mut times: Vec<i32> = node.operands.iter().filter_map(|f| top_level_interval(f, node.current_time)).flat_map(|i| 
                [i.lower - 1, i.upper]).collect();

            times.sort_unstable();
            times.dedup();
            times
        }

        let step = !jump_enabled || self.operands.iter().filter_map(|f| {
            if let Formula::O(inner) = f && !inner.parent_active(self.current_time) {
                return Some(&**inner);
            }
            None
        }).any(|f| {
            f.upper_bound() == Some(self.current_time) || match f {
                Formula::G { phi, interval, .. } 
                    | Formula::U { left: phi, interval, .. }
                    | Formula::R { right: phi, interval, .. } => {
                        match phi.get_max_upper() {
                            None => false,
                            Some(max_upper) => self.current_time < interval.lower + max_upper
                        }
                    }
                    _ => false
                }
            });
            
        let jump = if step {
            1
        } else {
            if let Some(target_time) = sorted_time_instants(self).into_iter().find(|&t| t > self.current_time) {
                target_time - self.current_time
            } else {
                return None
            }
        };

        // Retain only temporal operators, and retimed O formulas
        let new_operands: Vec<Formula> = self.operands.iter().filter_map(|op| match op {
            f @ (Formula::G {..} | Formula::F {..} | Formula::U {..} | Formula::R {..}) => retime_poised(f, self.current_time, jump),
            Formula::O(inner) => retime_poised(inner, self.current_time, jump),
            _ => None,
        }).collect();

        // Construct return value
        if new_operands.is_empty() {
            return None;
        }
        
        let mut new_node = self.clone();
        new_node.operands = new_operands;
        new_node.current_time += jump;
        
        if simple_first {
            let simple_operands: Vec<Formula> = new_node.operands.iter().filter(|f| !f.complex_temporal_operator()).cloned().collect();
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
    fn temporal_expansion(&self, current_time: i32, parent_interval: Option<&Interval>) ->  Formula {
        match self {
            Formula::Prop(_) | Formula::Not(_) | Formula::True | Formula::False => self.clone(),
            Formula::F { .. } 
            | Formula::G { .. }
            | Formula::U { .. }
            | Formula::R { .. } => {
                let mut extract = self.clone();
                if let Formula::F { interval: ref mut int, ref mut parent_upper, .. }
                    | Formula::G { interval: ref mut int, ref mut parent_upper, .. }
                    | Formula::U { interval: ref mut int, ref mut parent_upper, .. }
                    | Formula::R { interval: ref mut int, ref mut parent_upper, .. } = extract {
                    int.lower += current_time;
                    int.upper += current_time;
                    *parent_upper = if parent_interval.is_some() {Some(parent_interval.unwrap().upper)} else { None };
                }
                extract
            }
            Formula::And(operands) => {
                let new_operands = operands.iter().map(|op| op.temporal_expansion(current_time, parent_interval)).collect();
                Formula::And(new_operands)
            }
            Formula::Or(operands) => {
                let new_operands = operands.iter().map(|op| op.temporal_expansion(current_time, parent_interval)).collect();
                Formula::Or(new_operands)
            }
            Formula::Imply(left, right) => {
                let new_left = left.temporal_expansion(current_time, parent_interval);
                let new_right = right.temporal_expansion(current_time, parent_interval);
                Formula::Imply(Box::new(new_left), Box::new(new_right))
            }
            _ => panic!()
        }
    }
}