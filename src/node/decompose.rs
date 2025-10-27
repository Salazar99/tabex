use std::collections::BTreeSet;
use std::vec;

use crate::node::*;
use crate::tableau::Tableau;

#[cfg(test)]
mod tests;

impl Tableau {
    pub fn decompose(&self, node: &Node) -> Option<Vec<Node>> {
        if self.options.formula_optimizations
            && let Some(res) = node.rewrite_chain()
        {
            return Some(res);
        }

        if let Some(res) = self.decompose_and(node) {
            return Some(res);
        }

        if let Some(res) = self.decompose_g(node) {
            return Some(res);
        }

        for (i, operand) in node.operands.iter().enumerate() {
            match &operand {
                Formula::Or(_) => {
                    return Some(self.decompose_or_at(node, i));
                }
                Formula::Imply { .. } => {
                    return Some(self.decompose_imply_at(node, i));
                }
                _ => {}
            }
        }

        for (i, operand) in node.operands.iter().enumerate() {
            match &operand {
                Formula::F { .. } if operand.is_active_at(node.current_time) => {
                    return Some(self.decompose_f_at(node, i));
                }
                Formula::U { .. } if operand.is_active_at(node.current_time) => {
                    return Some(self.decompose_u_at(node, i));
                }
                Formula::R { .. } if operand.is_active_at(node.current_time) => {
                    return Some(self.decompose_r_at(node, i));
                }
                _ => {}
            }
        }

        self.decompose_jump(node)
    }

    pub fn decompose_and(&self, node: &Node) -> Option<Vec<Node>> {
        let mut changed = false;
        let flattened_operands: Vec<Formula> = node
            .operands
            .iter()
            .flat_map(|f| match &f {
                Formula::And(inner) => {
                    changed = true;
                    inner.clone()
                }
                _ => vec![f.clone()],
            })
            .collect();

        changed.then(|| {
            vec![Node {
                operands: flattened_operands,
                ..node.clone()
            }]
        })
    }

    pub fn decompose_g(&self, node: &Node) -> Option<Vec<Node>> {
        let mut changed = false;
        let flattened_operands: Vec<Formula> = node
            .operands
            .iter()
            .flat_map(|f| match &f {
                Formula::G { interval, phi, .. } if f.is_active_at(node.current_time) => {
                    changed = true;
                    if f.is_active_at(node.current_time + 1) {
                        vec![
                            Formula::o(f.clone()),
                            phi.temporal_expansion(node.current_time, Some(interval)),
                        ]
                    } else {
                        vec![phi.temporal_expansion(node.current_time, Some(interval))]
                    }
                }
                _ => vec![f.clone()],
            })
            .collect();

        changed.then(|| {
            vec![Node {
                operands: flattened_operands,
                ..node.clone()
            }]
        })
    }

    pub fn decompose_or_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let Formula::Or(or_operands) = &node.operands[i] else {
            panic!("decompose_or_at called on non-Or formula at index {}", i);
        };

        or_operands
            .iter()
            .map(|or_operand| {
                let mut new_operands = node.operands.clone();
                new_operands[i] = or_operand.clone();
                Node {
                    operands: new_operands,
                    ..node.clone()
                }
            })
            .collect()
    }

    pub fn decompose_imply_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let Formula::Imply {
            left,
            right,
            not_left,
        } = &node.operands[i]
        else {
            panic!(
                "decompose_imply_at called on non-Imply formula at index {}",
                i
            );
        };

        let mut new_node1 = node.clone();
        new_node1.operands[i] = (**not_left).clone();

        let mut new_node2 = node.clone();
        new_node2.operands[i] = (**right).clone();
        if self.options.formula_optimizations {
            new_node2.operands.insert(i, (**left).clone());
        }

        vec![new_node1, new_node2]
    }

    pub fn decompose_f_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let f_formula = &node.operands[i];

        let Formula::F { phi, interval, .. } = &f_formula else {
            panic!("decompose_f_at called on non-F formula at index {}", i);
        };

        if !node.operands[i].is_active_at(node.current_time) {
            panic!(
                "decompose_f_at called on F formula that is not active at current time {}",
                node.current_time
            );
        }

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
        let u_formula = &node.operands[i];

        let Formula::U {
            left,
            right,
            interval,
            ..
        } = &u_formula
        else {
            panic!("decompose_u_at called on non-U formula at index {}", i);
        };

        if !node.operands[i].is_active_at(node.current_time) {
            panic!(
                "decompose_u_at called on U formula that is not active at current time {}",
                node.current_time
            );
        }

        // Node where U is satisfied (q)
        let mut new_node1 = node.clone();
        new_node1.operands[i] = right.temporal_expansion(node.current_time, None);

        if node.current_time < interval.upper {
            // Node in which U is not satisfied (p, OU)
            let mut new_node2 = node.clone();
            new_node2.operands[i] = left.temporal_expansion(node.current_time, Some(interval));
            new_node2.operands.push(Formula::o(u_formula.clone()));

            return vec![new_node1, new_node2];
        }
        vec![new_node1]
    }

    pub fn decompose_r_at(&self, node: &Node, i: usize) -> Vec<Node> {
        let r_formula = &node.operands[i];

        let Formula::R {
            interval,
            left,
            right,
            ..
        } = &r_formula
        else {
            panic!("decompose_r_at called on non-R formula at index {}", i);
        };

        if !node.operands[i].is_active_at(node.current_time) {
            panic!(
                "decompose_r_at called on R formula that is not active at current time {}",
                node.current_time
            );
        }

        // Node where R is satisfied (p and q)
        let mut new_node1: Node = node.clone();
        new_node1.operands[i] = left.temporal_expansion(node.current_time, None);
        new_node1
            .operands
            .push(right.temporal_expansion(node.current_time, None));

        // Node in which R is not satisfied (q, OR)
        let mut new_node2 = node.clone();
        new_node2.operands[i] = right.temporal_expansion(node.current_time, Some(interval));
        new_node2.operands.push(Formula::o(r_formula.clone()));

        vec![new_node1, new_node2]
    }

    pub fn decompose_jump(&self, node: &Node) -> Option<Vec<Node>> {
        fn retime_poised(formula: &Formula, current_time: i32, jump: i32) -> Option<Formula> {
            let interval = formula.get_interval()?;
            if current_time >= interval.upper {
                return None;
            }

            if jump != 1 && formula.is_parent_active_at(current_time) {
                Some(formula.with_interval(interval.shift_right(jump)))
            } else {
                Some(formula.clone())
            }
        }

        fn sorted_time_instants(node: &Node) -> BTreeSet<i32> {
            fn top_level_interval(formula: &Formula, current_time: i32) -> Option<Vec<i32>> {
                match &formula {
                    Formula::O(inner) => top_level_interval(inner, current_time),
                    Formula::G { interval, .. }
                    | Formula::F { interval, .. }
                    | Formula::U { interval, .. }
                    | Formula::R { interval, .. }
                        if !formula.is_parent_active_at(current_time) =>
                    {
                        Some(vec![interval.lower - 1, interval.lower, interval.upper])
                    }
                    _ => None,
                }
            }
            node.operands
                .iter()
                .filter_map(|f| top_level_interval(f, node.current_time))
                .flatten()
                .collect()
        }

        pub fn get_max_upper(formula: &Formula) -> Option<i32> {
            match &formula {
                Formula::O(inner) | Formula::Not(inner) => get_max_upper(inner),
                Formula::And(operands) | Formula::Or(operands) => {
                    operands.iter().map(get_max_upper).max().unwrap_or(None)
                }
                Formula::Imply { left, right, .. } => get_max_upper(left).max(get_max_upper(right)),
                Formula::G { interval, .. }
                | Formula::F { interval, .. }
                | Formula::U { interval, .. }
                | Formula::R { interval, .. } => Some(interval.upper),
                _ => None,
            }
        }

        // Verify jump rule condition
        let step = !self.options.jump_rule_enabled
            || node
                .operands
                .iter()
                .filter_map(|f| {
                    if let Formula::O(inner) = &f
                        && !inner.is_parent_active_at(node.current_time)
                    {
                        return Some(&**inner);
                    }
                    None
                })
                .any(|f| {
                    f.upper_bound() == Some(node.current_time)
                        || match &f {
                            Formula::G { phi, interval, .. }
                            | Formula::U {
                                left: phi,
                                interval,
                                ..
                            }
                            | Formula::R {
                                right: phi,
                                interval,
                                ..
                            } => match get_max_upper(phi) {
                                None => false,
                                Some(max_upper) => node.current_time < interval.lower + max_upper,
                            },
                            _ => false,
                        }
                });

        // Select jump length
        let jump = if step {
            1
        } else if let Some(target_time) = sorted_time_instants(node)
            .into_iter()
            .find(|&t| t > node.current_time)
        {
            target_time - node.current_time
        } else {
            return None;
        };

        // Retain only temporal operators, and retimed O formulas
        let new_operands: Vec<Formula> = node
            .operands
            .iter()
            .filter_map(|op| match &op {
                Formula::G { .. } | Formula::F { .. } | Formula::U { .. } | Formula::R { .. } => {
                    retime_poised(op, node.current_time, jump)
                }
                Formula::O(inner) => retime_poised(inner, node.current_time, jump),
                _ => None,
            })
            .collect();

        // Construct return value
        if new_operands.is_empty() {
            return None;
        }

        let mut new_node = node.clone();
        new_node.operands = new_operands;
        new_node.current_time += jump;

        if self.options.simple_first {
            let simple_operands: Vec<Formula> = new_node
                .operands
                .iter()
                .filter(|f| !f.is_complex_temporal_operator())
                .cloned()
                .collect();
            if !simple_operands.is_empty() && simple_operands.len() < new_node.operands.len() {
                let mut simple_node = new_node.clone();
                simple_node.operands = simple_operands;
                simple_node.implies = Some(vec![new_node.id]);
                return Some(vec![simple_node, new_node]);
            }
        }
        Some(vec![new_node])
    }
}

impl Formula {
    fn temporal_expansion(&self, current_time: i32, parent_interval: Option<&Interval>) -> Formula {
        match &self {
            Formula::Prop(_) | Formula::Not(_) => self.clone(),
            Formula::F { interval, .. }
            | Formula::G { interval, .. }
            | Formula::U { interval, .. }
            | Formula::R { interval, .. } => self
                .with_interval(interval.shift_right(current_time))
                .with_parent_upper(parent_interval.map(|p| p.upper)),
            Formula::And(operands) | Formula::Or(operands) => self.with_operands(
                operands
                    .iter()
                    .map(|op| op.temporal_expansion(current_time, parent_interval))
                    .collect(),
            ),
            Formula::Imply {
                left,
                right,
                not_left,
            } => self.with_implication(
                left.temporal_expansion(current_time, parent_interval),
                right.temporal_expansion(current_time, parent_interval),
                not_left.temporal_expansion(current_time, parent_interval),
            ),
            _ => panic!(),
        }
    }
}
